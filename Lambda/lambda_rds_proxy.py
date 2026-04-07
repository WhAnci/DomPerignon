import json
import pymysql
import os
import logging
import time

# ===========================================================
# ★ 수정 포인트 ★  — 아래 설정만 바꾸면 됩니다.
# ===========================================================

# RDS Proxy 엔드포인트를 RDS_HOST 에 설정합니다.
# 예) xxxx.proxy-xxxxxx.ap-northeast-2.rds.amazonaws.com
RDS_HOST     = os.getenv("RDS_HOST")       # RDS Proxy 엔드포인트
RDS_PORT     = int(os.getenv("RDS_PORT", 3306))
RDS_USER     = os.getenv("RDS_USER")
RDS_PASSWORD = os.getenv("RDS_PASSWORD")
RDS_DB       = os.getenv("RDS_DB")

# ----------------------------------------------------------
# Secrets Manager 사용 시 아래 주석을 해제하고
# os.getenv 방식의 RDS_* 변수는 제거하세요.
# ----------------------------------------------------------
# import boto3
#
# SECRET_ID = os.getenv("SECRET_ID", "prod/myapp/mysql")
# _SECRET_CACHE = None
#
# def _get_secret() -> dict:
#     global _SECRET_CACHE
#     if _SECRET_CACHE is not None:
#         return _SECRET_CACHE
#     client = boto3.client("secretsmanager", region_name="ap-northeast-2")
#     response = client.get_secret_value(SecretId=SECRET_ID)
#     _SECRET_CACHE = json.loads(response["SecretString"])
#     return _SECRET_CACHE
#
# _secret = _get_secret()
# RDS_HOST     = _secret["host"]
# RDS_PORT     = int(_secret.get("port", 3306))
# RDS_USER     = _secret["username"]
# RDS_PASSWORD = _secret["password"]
# RDS_DB       = _secret["dbname"]
# ----------------------------------------------------------

# 대상 테이블 이름
TABLE_NAME = "item"

# ID 추출 방식: "query" 또는 "path"
# "query" → GET /item?id=<id>
# "path"  → GET /item/<id>  (API Gateway 리소스: /item/{id} 필요)
ID_SOURCE = "query"

# 헬스체크 주기 (초) — 웜 스타트 시 마지막 연결로부터 이 시간이 지나면 재연결
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", 60))

# ===========================================================
# 모듈 레벨 커넥션 (웜 스타트 재사용 + 주기적 헬스체크)
# ===========================================================

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_conn = None
_last_checked = 0.0


def _get_connection():
    """
    RDS Proxy 커넥션을 반환합니다.
    - 웜 스타트 시 기존 커넥션을 재사용합니다.
    - HEALTH_CHECK_INTERVAL 초가 지났거나 커넥션이 끊겼으면 재연결합니다.
    - RDS Proxy는 커넥션 풀링을 담당하므로 Lambda 쪽은 단일 커넥션으로 충분합니다.
    """
    global _conn, _last_checked
    now = time.time()

    # 헬스체크 주기가 지났으면 ping으로 생존 확인
    if _conn is not None and (now - _last_checked) >= HEALTH_CHECK_INTERVAL:
        try:
            _conn.ping(reconnect=False)
            _last_checked = now
            logger.info("[DB] ping ok — 기존 커넥션 재사용")
        except Exception:
            logger.warning("[DB] ping 실패 — 재연결 시도")
            _conn = None

    if _conn is None:
        _conn = pymysql.connect(
            host=RDS_HOST,
            port=RDS_PORT,
            user=RDS_USER,
            password=RDS_PASSWORD,
            database=RDS_DB,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
            autocommit=False,
        )
        _last_checked = time.time()
        logger.info("[DB] 새 커넥션 생성 완료")

    return _conn


# ===========================================================
# 내부 유틸
# ===========================================================

def _response(status_code: int, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
        },
        "body": json.dumps(body, default=str),
    }


def _extract_id(event: dict):
    """ID_SOURCE 설정에 따라 query 또는 path 에서 id 추출"""
    if ID_SOURCE == "path":
        parts = event.get("path", "").strip("/").split("/")
        return parts[1] if len(parts) >= 2 else None
    params = event.get("queryStringParameters") or {}
    return params.get("id")


# ===========================================================
# Lambda Function URL 지원
# ===========================================================
# Lambda Function URL 호출 시 event 구조가 API Gateway 와 다릅니다.
# - API Gateway : event["httpMethod"], event["path"]
# - Function URL: event["requestContext"]["http"]["method"], event["rawPath"]
#
# 아래 _normalize_event() 가 두 방식을 통일합니다.
# ===========================================================

def _normalize_event(event: dict) -> dict:
    """API Gateway Proxy 이벤트와 Function URL 이벤트를 통일된 형태로 변환"""
    # Function URL 이벤트 감지
    if "requestContext" in event and "http" in event.get("requestContext", {}):
        http_ctx = event["requestContext"]["http"]
        event = dict(event)  # 원본 불변 유지
        event["httpMethod"] = http_ctx.get("method", "")
        event["path"] = event.get("rawPath", "/")
        # Function URL 쿼리스트링은 queryStringParameters 로 동일하게 전달됨
    return event


# ===========================================================
# 핸들러
# ===========================================================

def lambda_handler(event, context):
    event = _normalize_event(event)
    method = event.get("httpMethod", "")
    path   = event.get("path", "")
    path_base = path.strip("/").split("/")[0]

    # CORS preflight
    if method == "OPTIONS":
        return _response(200, {})

    if path_base != TABLE_NAME:
        return _response(404, {"message": "Not Found"})

    if method == "GET":
        return _handle_get(event)
    if method == "POST":
        return _handle_post(event)

    return _response(405, {"message": "Method Not Allowed"})


# ===========================================================
# GET — 전체 조회 / 단건 조회
# ===========================================================

def _handle_get(event: dict):
    item_id = _extract_id(event)
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            if item_id:
                cur.execute(f"SELECT * FROM {TABLE_NAME} WHERE id = %s", (item_id,))
                result = cur.fetchone()
                if not result:
                    return _response(404, {"message": "Item not found"})
            else:
                cur.execute(f"SELECT * FROM {TABLE_NAME}")
                result = cur.fetchall()
        return _response(200, result)
    except Exception as e:
        logger.error(f"[GET] 오류: {e}")
        return _response(500, {"message": str(e)})


# ===========================================================
# POST — 단건 생성
# ===========================================================
# 요청 Body 예시:
# {
#   "name": "아메리카노",
#   "category": "음료",
#   "price": 4500
# }
# ===========================================================

def _handle_post(event: dict):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"message": "Invalid JSON body"})

    name     = body.get("name")
    category = body.get("category")
    price    = body.get("price")

    if not name or price is None:
        return _response(400, {"message": "name, price 는 필수입니다"})

    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {TABLE_NAME} (name, category, price) VALUES (%s, %s, %s)",
                (name, category, price),
            )
        conn.commit()
        new_id = cur.lastrowid
        logger.info(f"[POST] 생성 완료 id={new_id}")
        return _response(201, {"message": "created", "id": new_id})
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"[POST] 오류: {e}")
        return _response(500, {"message": str(e)})
