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

# PUT / PATCH 시 허용 필드
UPDATE_ALLOWED_FIELDS = ["name", "category", "price"]
IMMUTABLE_FIELDS      = {"id", "created_at", "is_deleted", "deleted_at"}

# GET 필터
FILTER_FIELDS       = ["category"]
FILTER_RANGE_FIELDS = ["price"]

# 페이지당 기본 조회 건수
DEFAULT_LIMIT = 20

# 타임스탬프 컬럼 사용 여부
USE_CREATED_AT = True
USE_UPDATED_AT = True

# ----------------------------------------------------------
# Soft Delete 설정
# is_deleted TINYINT(1) DEFAULT 0
# deleted_at DATETIME  DEFAULT NULL
# 위 컬럼이 테이블에 없으면 False 로 바꾸세요.
# ----------------------------------------------------------
USE_SOFT_DELETE = True

# ----------------------------------------------------------
# ID 추출 방식: "query" 또는 "path" 중 하나를 선택하세요.
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
    if ID_SOURCE == "path":
        parts = event.get("path", "").strip("/").split("/")
        return parts[1] if len(parts) == 2 else None
    else:
        params = event.get("queryStringParameters") or {}
        return params.get("id")


def _build_filter_clause(params, include_deleted=False):
    """WHERE 절 생성. Soft Delete 가 활성화된 경우 삭제된 항목을 기본적으로 제외합니다."""
    conditions, values = [], []
    if USE_SOFT_DELETE and not include_deleted:
        conditions.append("is_deleted = 0")
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
# 핸들러 — GET + POST + PUT + PATCH + DELETE (Soft)
# ===========================================================
# 지원 엔드포인트
#   GET    /item                          → 전체 조회 (삭제된 항목 제외)
#   GET    /item?id=<id>                  → 단건 조회
#   GET    /item?include_deleted=true     → 삭제된 항목 포함 조회
#   GET    /item?category=food            → 필터 조회
#   GET    /item?limit=10&offset=0        → 페이지네이션
#   POST   /item                          → 생성
#   PUT    /item?id=<id>                  → 전체 수정
#   PATCH  /item?id=<id>                  → 부분 수정
#   DELETE /item?id=<id>                  → Soft Delete (is_deleted=1, deleted_at 기록)
#   PATCH  /item/restore?id=<id>          → 삭제 취소 (is_deleted=0, deleted_at=NULL)
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
    if http_method == "PUT"    and path_base == TABLE_NAME:
        return _handle_update(event, full=True)
    if http_method == "PATCH"  and path_base == TABLE_NAME and path_sub == "restore":
        return _handle_restore(event)
    if http_method == "PATCH"  and path_base == TABLE_NAME:
        return _handle_update(event, full=False)
    if http_method == "DELETE" and path_base == TABLE_NAME:
        return _handle_delete(event)

    return _response(405, {"message": "Method Not Allowed"})


# ===========================================================
# GET 처리
# ===========================================================

def _handle_get(event):
    item_id = _extract_id(event)
    params  = event.get("queryStringParameters") or {}
    include_deleted = params.get("include_deleted", "false").lower() == "true"
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            if item_id:
                if USE_SOFT_DELETE and not include_deleted:
                    cur.execute(f"SELECT * FROM {TABLE_NAME} WHERE id = %s AND is_deleted = 0", (item_id,))
                else:
                    cur.execute(f"SELECT * FROM {TABLE_NAME} WHERE id = %s", (item_id,))
                result = cur.fetchone()
                if not result:
                    conn.close()
                    return _response(404, {"message": "Item not found"})
            else:
                limit  = int(params.get("limit",  DEFAULT_LIMIT))
                offset = int(params.get("offset", 0))
                where, fv = _build_filter_clause(params, include_deleted=include_deleted)

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
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        if USE_CREATED_AT:
            data["created_at"] = now
        if USE_UPDATED_AT:
            data["updated_at"] = now
        if USE_SOFT_DELETE:
            data["is_deleted"] = 0

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
# PUT / PATCH 처리
# ===========================================================

def _handle_update(event, full: bool):
    item_id = _extract_id(event)
    if not item_id:
        return _response(400, {"message": "'id' is required"})
    try:
        body = json.loads(event.get("body") or "{}")
        data = {
            k: body[k]
            for k in UPDATE_ALLOWED_FIELDS
            if k in body and k not in IMMUTABLE_FIELDS
        }
        if not data:
            return _response(400, {"message": f"Request body must contain at least one of: {UPDATE_ALLOWED_FIELDS}"})

        if USE_UPDATED_AT:
            data["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # Soft Delete 된 항목은 수정 불가
        extra_where = " AND is_deleted = 0" if USE_SOFT_DELETE else ""
        set_clause = ", ".join([f"{k} = %s" for k in data])
        values     = list(data.values()) + [item_id]

        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(f"UPDATE {TABLE_NAME} SET {set_clause} WHERE id = %s{extra_where}", values)
            if cur.rowcount == 0:
                conn.close()
                return _response(404, {"message": "Item not found or already deleted"})
        conn.commit()
        conn.close()
        action = "updated" if full else "patched"
        return _response(200, {"message": f"Item {action}", "id": item_id})
    except Exception as e:
        return _response(500, {"message": str(e)})


# ===========================================================
# DELETE 처리 — Soft Delete
# ===========================================================
# USE_SOFT_DELETE=True  : is_deleted=1, deleted_at=현재시각 으로 업데이트
# USE_SOFT_DELETE=False : 실제 DELETE 쿼리 실행
# ===========================================================

def _handle_delete(event):
    item_id = _extract_id(event)
    if not item_id:
        return _response(400, {"message": "'id' is required"})
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            if USE_SOFT_DELETE:
                now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                cur.execute(
                    f"UPDATE {TABLE_NAME} SET is_deleted = 1, deleted_at = %s WHERE id = %s AND is_deleted = 0",
                    (now, item_id)
                )
            else:
                cur.execute(f"DELETE FROM {TABLE_NAME} WHERE id = %s", (item_id,))
            if cur.rowcount == 0:
                conn.close()
                return _response(404, {"message": "Item not found or already deleted"})
        conn.commit()
        conn.close()
        return _response(200, {"message": "Item deleted", "id": item_id})
    except Exception as e:
        return _response(500, {"message": str(e)})


# ===========================================================
# RESTORE 처리 — Soft Delete 취소
# ===========================================================
# PATCH /item/restore?id=<id>
# is_deleted=0, deleted_at=NULL 로 복구합니다.
# ===========================================================

def _handle_restore(event):
    item_id = _extract_id(event)
    if not item_id:
        return _response(400, {"message": "'id' is required"})
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE {TABLE_NAME} SET is_deleted = 0, deleted_at = NULL WHERE id = %s AND is_deleted = 1",
                (item_id,)
            )
            if cur.rowcount == 0:
                conn.close()
                return _response(404, {"message": "Item not found or not deleted"})
        conn.commit()
        conn.close()
        return _response(200, {"message": "Item restored", "id": item_id})
    except Exception as e:
        return _response(500, {"message": str(e)})
