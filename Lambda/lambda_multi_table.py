import json
import pymysql
import os
import logging
import time

# ===========================================================
# ★ 수정 포인트 ★
# ===========================================================

RDS_HOST     = os.getenv("RDS_HOST")       # RDS Proxy 엔드포인트
RDS_PORT     = int(os.getenv("RDS_PORT", 3306))
RDS_USER     = os.getenv("RDS_USER")
RDS_PASSWORD = os.getenv("RDS_PASSWORD")
RDS_DB       = os.getenv("RDS_DB")

# ----------------------------------------------------------
# Secrets Manager 사용 시 아래 주석 해제
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

# 헬스체크 주기 (초)
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", 60))

# ===========================================================
# 테이블 정의
# ===========================================================
# 라우팅 키(path 첫 번째 세그먼트) → 실제 테이블명 매핑
# 예) GET /item/1  → TABLE_MAP["item"] = "item"
#      GET /order/5 → TABLE_MAP["order"] = "order"
#
# 다른 이름으로 매핑하고 싶으면:
# TABLE_MAP = {"products": "item", "orders": "order"}
TABLE_MAP = {
    "item":  "item",
    "order": "order",
}

# ID 추출 방식: "query" 또는 "path"
# "query" → GET /item?id=<id>
# "path"  → GET /item/<id>  (API Gateway 리소스: /item/{id} 필요)
ID_SOURCE = "query"

# ===========================================================
# 모듈 레벨 커넥션 (웹 스타트 재사용 + 헬스체크)
# ===========================================================

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_conn = None
_last_checked = 0.0


def _get_connection():
    global _conn, _last_checked
    now = time.time()

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
        # /item/<id>  → parts = ["item", "<id>"]
        return parts[1] if len(parts) >= 2 and parts[1] else None
    params = event.get("queryStringParameters") or {}
    return params.get("id")


def _normalize_event(event: dict) -> dict:
    """API Gateway Proxy 이벤트와 Function URL 이벤트를 통일된 형태로 변환"""
    if "requestContext" in event and "http" in event.get("requestContext", {}):
        http_ctx = event["requestContext"]["http"]
        event = dict(event)
        event["httpMethod"] = http_ctx.get("method", "")
        event["path"] = event.get("rawPath", "/")
    return event


# ===========================================================
# 라우터
# ===========================================================
# URL 구조
#   /item          → table="item"
#   /item?id=1     → table="item",  id=1
#   /item/1        → table="item",  id=1  (ID_SOURCE="path")
#   /order         → table="order"
#   /order?id=5    → table="order", id=5
# ===========================================================

def lambda_handler(event, context):
    event  = _normalize_event(event)
    method = event.get("httpMethod", "")
    path   = event.get("path", "")

    # CORS preflight
    if method == "OPTIONS":
        return _response(200, {})

    # path 첫 번째 세그먼트로 테이블 결정
    path_base = path.strip("/").split("/")[0]  # "item" 또는 "order"
    table = TABLE_MAP.get(path_base)

    if table is None:
        return _response(404, {"message": f"Unknown resource: /{path_base}"})

    if method == "GET":
        return _handle_get(event, table)
    if method == "POST":
        return _handle_post(event, table)

    return _response(405, {"message": "Method Not Allowed"})


# ===========================================================
# GET — 전체 조회 / 단건 조회
# ===========================================================

def _handle_get(event: dict, table: str):
    item_id = _extract_id(event)
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            if item_id:
                cur.execute(f"SELECT * FROM `{table}` WHERE id = %s", (item_id,))
                result = cur.fetchone()
                if not result:
                    return _response(404, {"message": f"{table} id={item_id} not found"})
            else:
                cur.execute(f"SELECT * FROM `{table}`")
                result = cur.fetchall()
        return _response(200, result)
    except Exception as e:
        logger.error(f"[GET/{table}] 오류: {e}")
        return _response(500, {"message": str(e)})


# ===========================================================
# POST — 테이블별 생성
# ===========================================================
# [item] 요청 Body
# {
#   "name": "아메리카노",
#   "category": "음료",
#   "price": 4500
# }
#
# [order] 요청 Body
# {
#   "item_id": 1,
#   "quantity": 2,
#   "user_id": "user-abc"
# }
# ===========================================================

# 테이블별 필수/옵션 필드 정의
# required: 없으면 400 반환
# insert_fields: INSERT에 쓸 필드 목록
TABLE_SCHEMA = {
    "item": {
        "required": ["name", "price"],
        "insert_fields": ["name", "category", "price"],
    },
    "order": {
        "required": ["item_id", "quantity"],
        "insert_fields": ["item_id", "quantity", "user_id"],
    },
}


def _handle_post(event: dict, table: str):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"message": "Invalid JSON body"})

    schema = TABLE_SCHEMA.get(table)
    if schema is None:
        return _response(400, {"message": f"{table} 에 대한 스키마가 정의되지 않았습니다"})

    # 필수 필드 검사
    for field in schema["required"]:
        if body.get(field) is None:
            return _response(400, {"message": f"필수 필드 누락: {field}"})

    # INSERT 필드 및 값 추출
    fields = schema["insert_fields"]
    values = [body.get(f) for f in fields]

    placeholders = ", ".join(["%s"] * len(fields))
    col_names    = ", ".join([f"`{f}`" for f in fields])
    sql = f"INSERT INTO `{table}` ({col_names}) VALUES ({placeholders})"

    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(sql, values)
        conn.commit()
        new_id = cur.lastrowid
        logger.info(f"[POST/{table}] 생성 완료 id={new_id}")
        return _response(201, {"message": "created", "id": new_id})
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"[POST/{table}] 오류: {e}")
        return _response(500, {"message": str(e)})


# ===========================================================
# 테이블 JOIN 조회 예시
# ===========================================================
# GET /order?id=<id> 시 item 정보까지 함께 반환하고 싶으면
# _handle_get 대신 아래 함수를 사용하세요.
#
# 사용법: lambda_handler 의 GET + table=="order" 분기에서
#   return _handle_get_order_with_item(event)
# 로 교체하면 됩니다.
# ===========================================================

def _handle_get_order_with_item(event: dict):
    """
    order 테이블과 item 테이블을 JOIN하여 반환합니다.

    단건 조회: GET /order?id=<id>
    전체 조회: GET /order

    응답 예시:
    {
      "order_id": 5,
      "quantity": 2,
      "user_id": "user-abc",
      "item_name": "아메리카노",
      "item_price": 4500,
      "item_category": "음료"
    }
    """
    order_id = _extract_id(event)
    sql_all = """
        SELECT
            o.id         AS order_id,
            o.quantity,
            o.user_id,
            i.name       AS item_name,
            i.price      AS item_price,
            i.category   AS item_category
        FROM `order` o
        JOIN `item`  i ON o.item_id = i.id
    """
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            if order_id:
                cur.execute(sql_all + " WHERE o.id = %s", (order_id,))
                result = cur.fetchone()
                if not result:
                    return _response(404, {"message": f"order id={order_id} not found"})
            else:
                cur.execute(sql_all)
                result = cur.fetchall()
        return _response(200, result)
    except Exception as e:
        logger.error(f"[GET/order+item JOIN] 오류: {e}")
        return _response(500, {"message": str(e)})
