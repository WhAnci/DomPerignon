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

# POST(bulk) 시 허용 필드
CREATE_ALLOWED_FIELDS = ["name", "category", "price"]

# GET 필터
FILTER_FIELDS       = ["category"]
FILTER_RANGE_FIELDS = ["price"]

# 페이지당 기본 조회 건수
DEFAULT_LIMIT = 20

# 한 번에 처리 가능한 최대 bulk 건수 (Lambda 타임아웃·DB 부하 고려)
BULK_MAX = 100

# 타임스탬프 컬럼 사용 여부
USE_CREATED_AT = True

# ----------------------------------------------------------
# ID 추출 방식: "query" 또는 "path" 중 하나를 선택하세요.
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
    if ID_SOURCE == "path":
        parts = event.get("path", "").strip("/").split("/")
        return parts[1] if len(parts) == 2 else None
    else:
        params = event.get("queryStringParameters") or {}
        return params.get("id")


def _build_filter_clause(params):
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
# 핸들러 — GET + POST(단건/Bulk) + DELETE(단건/Bulk)
# ===========================================================
# 지원 엔드포인트
#   GET    /item                          → 전체 조회 (Filter + Pagination)
#   GET    /item?id=<id>                  → 단건 조회
#   POST   /item                          → 단건 생성  (body: object)
#   POST   /item/bulk                     → 배치 생성  (body: {"items": [...]}, 최대 BULK_MAX 건)
#   DELETE /item?id=<id>                  → 단건 삭제
#   DELETE /item/bulk                     → 배치 삭제  (body: {"ids": ["id1", "id2", ...]}, 최대 BULK_MAX 건)
# ===========================================================

def lambda_handler(event, context):
    http_method = event.get("httpMethod", "")
    path        = event.get("path", "")
    path_base   = path.strip("/").split("/")[0]
    path_sub    = path.strip("/").split("/")[1] if len(path.strip("/").split("/")) > 1 else ""

    if http_method == "GET"    and path_base == TABLE_NAME:
        return _handle_get(event)
    if http_method == "POST"   and path == f"/{TABLE_NAME}":
        return _handle_post(event)
    if http_method == "POST"   and path_base == TABLE_NAME and path_sub == "bulk":
        return _handle_post_bulk(event)
    if http_method == "DELETE" and path_base == TABLE_NAME and path_sub == "bulk":
        return _handle_delete_bulk(event)
    if http_method == "DELETE" and path_base == TABLE_NAME:
        return _handle_delete(event)

    return _response(405, {"message": "Method Not Allowed"})


# ===========================================================
# GET 처리
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
# POST 처리 — 단건 생성
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
# POST /item/bulk — 배치 생성
# ===========================================================
# Request body: {"items": [{"name": "...", "category": "...", "price": 0}, ...]}
# 성공한 항목과 실패한 항목을 각각 반환합니다.
# ===========================================================

def _handle_post_bulk(event):
    try:
        body  = json.loads(event.get("body") or "{}")
        items = body.get("items", [])
        if not items or not isinstance(items, list):
            return _response(400, {"message": "'items' array is required"})
        if len(items) > BULK_MAX:
            return _response(400, {"message": f"Too many items. Max {BULK_MAX} per request."})

        now      = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        created  = []
        failed   = []

        conn = _get_connection()
        try:
            with conn.cursor() as cur:
                for i, item in enumerate(items):
                    data = {k: item[k] for k in CREATE_ALLOWED_FIELDS if k in item}
                    if not data:
                        failed.append({"index": i, "reason": "no valid fields"})
                        continue
                    data["id"] = str(uuid.uuid4())
                    if USE_CREATED_AT:
                        data["created_at"] = now

                    columns      = ", ".join(data.keys())
                    placeholders = ", ".join(["%s"] * len(data))
                    try:
                        cur.execute(f"INSERT INTO {TABLE_NAME} ({columns}) VALUES ({placeholders})", list(data.values()))
                        created.append(data["id"])
                    except Exception as e:
                        failed.append({"index": i, "reason": str(e)})
            conn.commit()
        finally:
            conn.close()

        return _response(
            207 if failed else 201,
            {"created": created, "failed": failed, "total_created": len(created), "total_failed": len(failed)}
        )
    except Exception as e:
        return _response(500, {"message": str(e)})


# ===========================================================
# DELETE 처리 — 단건 삭제
# ===========================================================

def _handle_delete(event):
    item_id = _extract_id(event)
    if not item_id:
        return _response(400, {"message": "'id' is required"})
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {TABLE_NAME} WHERE id = %s", (item_id,))
            if cur.rowcount == 0:
                conn.close()
                return _response(404, {"message": "Item not found"})
        conn.commit()
        conn.close()
        return _response(200, {"message": "Item deleted", "id": item_id})
    except Exception as e:
        return _response(500, {"message": str(e)})


# ===========================================================
# DELETE /item/bulk — 배치 삭제
# ===========================================================
# Request body: {"ids": ["id1", "id2", ...]}
# IN 절을 사용한 단일 쿼리로 처리합니다.
# ===========================================================

def _handle_delete_bulk(event):
    try:
        body = json.loads(event.get("body") or "{}")
        ids  = body.get("ids", [])
        if not ids or not isinstance(ids, list):
            return _response(400, {"message": "'ids' array is required"})
        if len(ids) > BULK_MAX:
            return _response(400, {"message": f"Too many ids. Max {BULK_MAX} per request."})

        placeholders = ", ".join(["%s"] * len(ids))
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {TABLE_NAME} WHERE id IN ({placeholders})", ids)
            deleted_count = cur.rowcount
        conn.commit()
        conn.close()
        return _response(200, {"message": f"{deleted_count} item(s) deleted", "deleted_count": deleted_count})
    except Exception as e:
        return _response(500, {"message": str(e)})
