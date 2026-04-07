import json
import boto3
import pymysql
import os
from datetime import datetime
import uuid

# ===========================================================
# ★ 수정 포인트 ★  — 아래 설정만 바꾸면 됩니다.
# ===========================================================

# Secrets Manager 에 저장된 시크릿 이름(ARN 또는 이름)
# 예) 'prod/myapp/mysql' 또는 전체 ARN
SECRET_ID = os.getenv("SECRET_ID", "prod/myapp/mysql")

# AWS 리전
REGION = os.getenv("AWS_REGION", "ap-northeast-2")

# 대상 테이블 이름
TABLE_NAME = "item"

# POST 시 허용 필드
CREATE_ALLOWED_FIELDS = ["name", "category", "price"]

# PUT / PATCH 시 허용 필드
UPDATE_ALLOWED_FIELDS = ["name", "category", "price"]
IMMUTABLE_FIELDS      = {"id", "created_at"}

# ID 추출 방식: "query" 또는 "path"
ID_SOURCE = "query"

# ===========================================================
# Secrets Manager 에서 DB 자격 증명 가져오기
# ===========================================================
# Secrets Manager 에 저장된 시크릿 형식 (JSON):
# {
#   "host":     "your-rds-endpoint.rds.amazonaws.com",
#   "port":     3306,
#   "username": "admin",
#   "password": "yourpassword",
#   "dbname":   "mydb"
# }
#
# ⚠️ Lambda 실행 Role 에 아래 권한이 필요합니다:
#   - secretsmanager:GetSecretValue
#   - secretsmanager:DescribeSecret
# ===========================================================

# 콜드 스타트 최적화: 모듈 최상위에서 한 번만 가져옵니다.
# Lambda 컨테이너가 재사용될 때는 이 변수가 캐시되어
# Secrets Manager API 를 반복 호출하지 않습니다.
_SECRET_CACHE = None


def get_secret() -> dict:
    """
    Secrets Manager 에서 DB 자격 증명을 가져옵니다.
    콜드 스타트 이후에는 캐시된 값을 반환합니다.

    Returns:
        dict: host, port, username, password, dbname 포함
    """
    global _SECRET_CACHE
    if _SECRET_CACHE is not None:
        return _SECRET_CACHE

    client = boto3.client("secretsmanager", region_name=REGION)
    response = client.get_secret_value(SecretId=SECRET_ID)
    _SECRET_CACHE = json.loads(response["SecretString"])
    return _SECRET_CACHE


# ===========================================================
# DB 연결
# ===========================================================

def _get_connection():
    """
    Secrets Manager 에서 가져온 자격 증명으로 RDS 에 연결합니다.
    환경 변수에 평문 비밀번호를 노출하지 않아도 됩니다.
    """
    secret = get_secret()
    return pymysql.connect(
        host     = secret["host"],
        port     = int(secret.get("port", 3306)),
        user     = secret["username"],
        password = secret["password"],
        database = secret["dbname"],
        cursorclass = pymysql.cursors.DictCursor,
    )


# ===========================================================
# 내부 유틸
# ===========================================================

def _response(status_code: int, body) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def _extract_id(event) -> str | None:
    """ID_SOURCE 설정에 따라 Query 또는 Path 에서 id 추출"""
    if ID_SOURCE == "path":
        parts = event.get("path", "").strip("/").split("/")
        return parts[1] if len(parts) == 2 else None
    params = event.get("queryStringParameters") or {}
    return params.get("id")


# ===========================================================
# 핸들러 — GET + POST + PUT + PATCH + DELETE
# ===========================================================
# 지원 엔드포인트
#   GET    /item           → 전체 조회
#   GET    /item?id=<id>   → 단건 조회
#   POST   /item           → 생성
#   PUT    /item?id=<id>   → 전체 수정
#   PATCH  /item?id=<id>   → 부분 수정
#   DELETE /item?id=<id>   → 삭제
# ===========================================================

def lambda_handler(event, context):
    http_method = event.get("httpMethod", "")
    path        = event.get("path", "")
    path_base   = path.strip("/").split("/")[0]

    if http_method == "GET"    and path_base == TABLE_NAME:
        return _handle_get(event)
    if http_method == "POST"   and path == f"/{TABLE_NAME}":
        return _handle_post(event)
    if http_method == "PUT"    and path_base == TABLE_NAME:
        return _handle_update(event, full=True)
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

        data["id"]         = str(uuid.uuid4())
        data["created_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        columns      = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))

        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {TABLE_NAME} ({columns}) VALUES ({placeholders})",
                list(data.values())
            )
        conn.commit()
        conn.close()
        return _response(201, {"message": "Item created", "id": data["id"]})
    except Exception as e:
        return _response(500, {"message": str(e)})


# ===========================================================
# PUT / PATCH 처리  (full=True → PUT, full=False → PATCH)
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

        data["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
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


# ===========================================================
# DELETE 처리
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
