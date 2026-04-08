import json
import pymysql
import boto3
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ===========================================================
# ★ 수정 포인트 ★  — 아래 설정만 바꾸면 됩니다.
# ===========================================================

# RDS Proxy 엔드포인트
DB_HOST   = os.getenv("DB_HOST")
DB_PORT   = int(os.getenv("DB_PORT", 3306))
DB_USER   = os.getenv("DB_USER")
DB_NAME   = os.getenv("DB_NAME")
REGION    = os.getenv("AWS_REGION", "ap-northeast-2")

# ===========================================================
# 커넥션 재사용 — Lambda 컨테이너가 살아있으면 재사용 (warm start)
# 매 호출마다 새 연결을 맺지 않아 지연 감소
# ===========================================================
_conn = None

# 대상 테이블
TABLE_NAME = "item"

# ===========================================================
# 내부 유틸
# ===========================================================

def _get_auth_token() -> str:
    """RDS Proxy IAM 인증 토큰 생성 (패스워드 대체)"""
    client = boto3.client("rds", region_name=REGION)
    return client.generate_db_auth_token(
        DBHostname=DB_HOST,
        Port=DB_PORT,
        DBUsername=DB_USER,
    )


def _get_connection():
    global _conn
    # 기존 연결이 살아있으면 재사용 (warm start 최적화)
    try:
        if _conn and _conn.open:
            _conn.ping(reconnect=False)
            return _conn
    except Exception:
        pass

    _conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=_get_auth_token(),
        database=DB_NAME,
        ssl={"ssl": True},
        connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor,
    )
    return _conn


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def _parse_event(event):
    """Lambda Function URL 이벤트에서 method / querystring / body 추출"""
    ctx    = event.get("requestContext", {}).get("http", {})
    method = ctx.get("method", "GET").upper()
    qs     = event.get("queryStringParameters") or {}
    raw    = event.get("body", "") or ""
    try:
        body = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        body = {}
    return method, qs, body


# ===========================================================
# 핸들러 — Lambda Function URL 기준
# ===========================================================
# 지원 엔드포인트
#   GET    /?id=<id>          → 단건 조회
#   GET    /                  → 전체 조회
#   POST   /  body:{name,value}  → 생성
#   PUT    /?id=<id>  body:{name,value}  → 수정
#   DELETE /?id=<id>          → 삭제
# ===========================================================

def lambda_handler(event, context):
    method, qs, body = _parse_event(event)

    try:
        conn = _get_connection()
    except Exception as e:
        logger.error("DB connection failed: %s", e)
        return _response(500, {"message": "Database connection failed"})

    try:
        with conn.cursor() as cur:
            # ── GET ──────────────────────────────────────────────
            if method == "GET":
                item_id = qs.get("id")
                if item_id:
                    cur.execute(f"SELECT * FROM {TABLE_NAME} WHERE id = %s", (item_id,))
                    row = cur.fetchone()
                    if not row:
                        return _response(404, {"message": "Item not found"})
                    return _response(200, row)
                else:
                    cur.execute(f"SELECT * FROM {TABLE_NAME} ORDER BY id DESC LIMIT 100")
                    return _response(200, {"count": cur.rowcount, "data": cur.fetchall()})

            # ── POST ─────────────────────────────────────────────
            elif method == "POST":
                name  = body.get("name")
                value = body.get("value")
                if not name:
                    return _response(400, {"message": "name is required"})
                cur.execute(
                    f"INSERT INTO {TABLE_NAME} (name, value) VALUES (%s, %s)",
                    (name, value),
                )
                conn.commit()
                return _response(201, {"id": cur.lastrowid, "name": name, "value": value})

            # ── PUT ──────────────────────────────────────────────
            elif method == "PUT":
                item_id = qs.get("id") or body.get("id")
                if not item_id:
                    return _response(400, {"message": "id is required"})
                name  = body.get("name")
                value = body.get("value")
                cur.execute(
                    f"UPDATE {TABLE_NAME} SET name = %s, value = %s WHERE id = %s",
                    (name, value, item_id),
                )
                conn.commit()
                return _response(200, {"updated": cur.rowcount})

            # ── DELETE ───────────────────────────────────────────
            elif method == "DELETE":
                item_id = qs.get("id")
                if not item_id:
                    return _response(400, {"message": "id is required"})
                cur.execute(f"DELETE FROM {TABLE_NAME} WHERE id = %s", (item_id,))
                conn.commit()
                return _response(200, {"deleted": cur.rowcount})

            return _response(405, {"message": "Method Not Allowed"})

    except Exception as e:
        logger.error("Query error: %s", e)
        conn.rollback()
        return _response(500, {"message": "Internal server error"})

    finally:
        conn.close()
