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

# GET 필터: 동등(=) 조건 컬럼 목록
# 예) category → GET /item?category=food
FILTER_FIELDS       = ["category"]

# GET 필터: 범위 조건 컬럼 목록
# 예) price → GET /item?price_lt=5000&price_gt=1000
FILTER_RANGE_FIELDS = ["price"]

# 페이지당 기본 조회 건수
DEFAULT_LIMIT = 20

# created_at 컬럼이 없으면 False 로 바꾸세요
USE_CREATED_AT = True

# ----------------------------------------------------------
# ID 추출 방식: "query" 또는 "path" 중 하나를 선택하세요.
#   "query" → GET/PUT /item?id=<id>   (쿼리 파라미터 방식)
#   "path"  → GET/PUT /item/<id>      (패스 파라미터 방식)
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


def _build_filter_clause(params):
    """Query Parameter → WHERE 절 + 바인딩 값 생성"""
    conditions, values = [], []
    for col in FILTER_FIELDS:
        if col in params:
            conditions.append(f"{col} = %s")
            values.append(params[col])
    for col in FILTER_RANGE_FIELDS:
        if f"{col}_lt" in params:
            conditions.append(f"{col} < %s")
            values.append(params[f"{col}_lt"])
        if f"{col}_gt" in params:
            conditions.append(f"{col} > %s")
            values.append(params[f"{col}_gt"])
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    return where, values


# ===========================================================
# 핸들러 — GET + POST + PUT
# ===========================================================
# 지원 엔드포인트
#   GET  /item                     → 전체 조회 (Filter + Pagination)
#   GET  /item?id=<id>             → 단건 조회  (ID_SOURCE="query")
#   GET  /item/<id>                → 단건 조회  (ID_SOURCE="path")
#   GET  /item?category=food       → 필터 조회
#   GET  /item?price_lt=5000       → 범위 필터 조회
#   GET  /item?limit=10&offset=0   → 페이지네이션
#   POST /item                     → 생성
#   PUT  /item?id=<id>             → 수정  (ID_SOURCE="query")
#   PUT  /item/<id>                → 수정  (ID_SOURCE="path")
# ===========================================================

def lambda_handler(event, context):
    http_method = event.get("httpMethod", "")
    path        = event.get("path", "")
    path_base   = path.strip("/").split("/")[0]

    if http_method == "GET"  and path_base == TABLE_NAME:
        return _handle_get(event)
    if http_method == "POST" and path == f"/{TABLE_NAME}":
        return _handle_post(event)
    if http_method == "PUT"  and path_base == TABLE_NAME:
        return _handle_update(event, full=True)

    return _response(405, {"message": "Method Not Allowed"})


# ===========================================================
# GET 처리 (Filter + Pagination 포함)
# ===========================================================

def _handle_get(event):
    item_id = _extract_id(event)
    params  = event.get("queryStringParameters") or {}
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
                limit  = int(params.get("limit",  DEFAULT_LIMIT))
                offset = int(params.get("offset", 0))
                where, fv = _build_filter_clause(params)

                cur.execute(f"SELECT * FROM {TABLE_NAME} {where} LIMIT %s OFFSET %s", fv + [limit, offset])
                items = cur.fetchall()

                cur.execute(f"SELECT COUNT(*) AS total FROM {TABLE_NAME} {where}", fv)
                total  = cur.fetchone()["total"]
                result = {"total": total, "limit": limit, "offset": offset, "items": items}
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
# PUT 처리
# ===========================================================
# IMMUTABLE_FIELDS(id, created_at)는 수정 불가입니다.
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
