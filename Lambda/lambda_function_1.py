import json
import pymysql
import os

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

# ----------------------------------------------------------
# ID 추출 방식: "query" 또는 "path" 중 하나를 선택하세요.
#   "query" → GET /item?id=<id>     (쿼리 파라미터 방식)
#   "path"  → GET /item/<id>        (패스 파라미터 방식)
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
# 핸들러 — GET 단건 / 전체 조회
# ===========================================================
# 지원 엔드포인트
#   GET /item           → 전체 조회
#   GET /item?id=<id>   → 단건 조회  (ID_SOURCE="query")
#   GET /item/<id>      → 단건 조회  (ID_SOURCE="path")
# ===========================================================

def lambda_handler(event, context):
    http_method = event.get("httpMethod", "")
    path        = event.get("path", "")

    # Path 방식일 때는 /item/<id> 도 GET 라우팅에 포함
    path_base = path.strip("/").split("/")[0]

    if http_method == "GET" and path_base == TABLE_NAME:
        return _handle_get(event)

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
