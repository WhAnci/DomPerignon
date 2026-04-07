import json
import pymysql
import os
import uuid
from datetime import datetime

# ===========================================================
# ★ 수정 포인트 ★  — 아래 설정만 바꾸면 됩니다.
# ===========================================================

# RDS 연결 정보 (Lambda 환경 변수로 주입)
RDS_HOST     = os.getenv("RDS_HOST")
RDS_PORT     = int(os.getenv("RDS_PORT", 3306))
RDS_USER     = os.getenv("RDS_USER")
RDS_PASSWORD = os.getenv("RDS_PASSWORD")
RDS_DB       = os.getenv("RDS_DB")

# 대상 테이블 이름
TABLE_NAME = "item"

# POST 시 허용 필드
CREATE_ALLOWED_FIELDS = ["name", "category", "price"]

# PUT / PATCH 시 허용 필드 (id, created_at 은 항상 수정 불가)
UPDATE_ALLOWED_FIELDS = ["name", "category", "price"]
IMMUTABLE_FIELDS      = {"id", "created_at"}

# created_at 컬럼이 없으면 False 로 바꾸세요
USE_CREATED_AT = True

# ----------------------------------------------------------
# ID 추출 방식: "query" 또는 "path" 중 하나를 선택하세요.
#   "query" → GET/PUT/PATCH /item?id=<id>   (쿼리 파라미터 방식)
#   "path"  → GET/PUT/PATCH /item/<id>      (패스 파라미터 방식)
#
# ⚠️  "path" 사용 시 API Gateway 리소스를 /item/{id} 로 설정해야 합니다.
# ----------------------------------------------------------
ID_SOURCE = "query"   # ← "query" 또는 "path"

# ===========================================================
# 내부 유틸
# ===========================================================

def _get_connection():
    return pymysql.connect(
        host=RDS_HOST, port=RDS_PORT,
        user=RDS_USER, password=RDS_PASSWORD,
        database=RDS_DB,
        cursorclass=pymysql.cursors.DictCursor,
    )


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def _extract_id(event):
    """ID_SOURCE 설정에 따라 Query 또는 Path 에서 id 추출"""
    if ID_SOURCE == "path":
        parts = event.get("path", "").strip("/").split("/")
        return parts[1] if len(parts) == 2 else None
    else:  # "query"
        params = event.get("queryStringParameters") or {}
        return params.get("id")


# ===========================================================
# 핸들러 — GET + POST + PUT + PATCH
# ===========================================================
# 지원 엔드포인트
#   GET   /item           → 전체 조회
#   GET   /item?id=<id>   → 단건 조회  (ID_SOURCE="query")
#   GET   /item/<id>      → 단건 조회  (ID_SOURCE="path")
#   POST  /item           → 생성
#   PUT   /item?id=<id>   → 전체 수정  (ID_SOURCE="query")
#   PUT   /item/<id>      → 전체 수정  (ID_SOURCE="path")
#   PATCH /item?id=<id>   → 부분 수정  (ID_SOURCE="query")
#   PATCH /item/<id>      → 부분 수정  (ID_SOURCE="path")
# ===========================================================

def lambda_handler(event, context):
    http_method = event.get("httpMethod", "")
    path        = event.get("path", "")
    path_base   = path.strip("/").split("/")[0]

    if http_method == "GET"   and path_base == TABLE_NAME:
        return _handle_get(event)
    if http_method == "POST"  and path == f"/{TABLE_NAME}":
        return _handle_post(event)
    if http_method == "PUT"   and path_base == TABLE_NAME:
        return _handle_update(event, full=True)
    if http_method == "PATCH" and path_base == TABLE_NAME:
        return _handle_update(event, full=False)

    return _response(405, {"message": "Method Not Allowed"})


# ===========================================================
# GET 처리
# ===========================================================

def _handle_get(event):
    item_id = _extract_id(event)
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            if item_id:
                cur.execute(f"SELECT * FROM {TABLE_NAME} WHERE id = %s", (item_id,))
                result = cur.fetchone()
                if not result:
                    conn.close()
                    return _response(404, {"message": "Item not found"})
            else:
                cur.execute(f"SELECT * FROM {TABLE_NAME}")
                result = cur.fetchall()
        conn.close()
        return _response(200, result)
    except Exception as e:
        return _response(500, {"message": str(e)})


# ===========================================================
# POST 처리
# ===========================================================

def _handle_post(event):
    try:
        body = json.loads(event.get("body") or "{}")
        data = {k: body[k] for k in CREATE_ALLOWED_FIELDS if k in body}
        if not data:
            return _response(400, {"message": f"Request body must contain at least one of: {CREATE_ALLOWED_FIELDS}"})

        data["id"] = str(uuid.uuid4())
        if USE_CREATED_AT:
            data["created_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        columns      = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))

        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(f"INSERT INTO {TABLE_NAME} ({columns}) VALUES ({placeholders})", list(data.values()))
        conn.commit()
        conn.close()
        return _response(201, {"message": "Item created", "id": data["id"]})
    except Exception as e:
        return _response(500, {"message": str(e)})


# ===========================================================
# PUT / PATCH 처리  (full=True → PUT, full=False → PATCH)
# ===========================================================
# PUT   : body 의 UPDATE_ALLOWED_FIELDS 를 모두 덮어씁니다.
# PATCH : body 에 포함된 필드만 선택적으로 수정합니다.
# 두 메서드 모두 IMMUTABLE_FIELDS(id, created_at)는 수정 불가입니다.
# ===========================================================

def _handle_update(event, full: bool):
    item_id = _extract_id(event)
    if not item_id:
        return _response(400, {"message": "'id' is required (query param or path segment)"})
    try:
        body = json.loads(event.get("body") or "{}")
        data = {
            k: body[k]
            for k in UPDATE_ALLOWED_FIELDS
            if k in body and k not in IMMUTABLE_FIELDS
        }
        if not data:
            return _response(400, {"message": f"Request body must contain at least one of: {UPDATE_ALLOWED_FIELDS}"})

        set_clause = ", ".join([f"{k} = %s" for k in data])
        values     = list(data.values()) + [item_id]

        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(f"UPDATE {TABLE_NAME} SET {set_clause} WHERE id = %s", values)
            if cur.rowcount == 0:
                conn.close()
                return _response(404, {"message": "Item not found"})
        conn.commit()
        conn.close()
        action = "updated" if full else "patched"
        return _response(200, {"message": f"Item {action}", "id": item_id})
    except Exception as e:
        return _response(500, {"message": str(e)})
