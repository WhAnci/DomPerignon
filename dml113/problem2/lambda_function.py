import json
import time
import boto3
import os

# ===========================================================
# ★ 수정 포인트 ★  — 아래 설정만 바꾸면 됩니다.
# ===========================================================

ATHENA_DATABASE = os.getenv("ATHENA_DATABASE", "wsi_db")
ATHENA_TABLE    = os.getenv("ATHENA_TABLE", "wsi_table")
ATHENA_OUTPUT   = os.getenv("ATHENA_OUTPUT")   # s3://버킷명/prefix/
REGION          = os.getenv("AWS_REGION", "ap-northeast-2")

# ===========================================================
# 내부 유틸
# ===========================================================

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


def _run_query(sql: str) -> list[dict]:
    """Athena 쿼리 실행 후 결과 반환"""
    client = boto3.client("athena", region_name=REGION)

    res = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": ATHENA_DATABASE},
        ResultConfiguration={"OutputLocation": ATHENA_OUTPUT},
    )
    exec_id = res["QueryExecutionId"]

    # 완료 대기 (최대 30초)
    for _ in range(30):
        status = client.get_query_execution(QueryExecutionId=exec_id)
        state  = status["QueryExecution"]["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)

    if state != "SUCCEEDED":
        reason = status["QueryExecution"]["Status"].get("StateChangeReason", "")
        raise RuntimeError(f"Query {state}: {reason} (id={exec_id})")

    rows   = client.get_query_results(QueryExecutionId=exec_id)["ResultSet"]["Rows"]
    if not rows:
        return []

    headers = [col["VarCharValue"] for col in rows[0]["Data"]]
    return [
        {headers[i]: col.get("VarCharValue", "") for i, col in enumerate(row["Data"])}
        for row in rows[1:]
    ]


# ===========================================================
# 핸들러 — Lambda Function URL 기준
# ===========================================================
# 지원 엔드포인트
#   GET  /?query=<sql>           → SQL 직접 실행
#   GET  /?filter=<col>&value=<v>  → 단순 WHERE 필터 조회
#   GET  /  (파라미터 없음)        → 전체 조회 (LIMIT 100)
# ===========================================================

def lambda_handler(event, context):
    method, qs, body = _parse_event(event)

    if method != "GET":
        return _response(405, {"message": "Method Not Allowed"})

    try:
        # 직접 SQL 전달
        if "query" in qs:
            sql = qs["query"]

        # 단순 컬럼 필터
        elif "filter" in qs and "value" in qs:
            col   = qs["filter"]
            value = qs["value"]
            sql   = f"SELECT * FROM {ATHENA_DATABASE}.{ATHENA_TABLE} WHERE {col} = '{value}' LIMIT 100"

        # 전체 조회
        else:
            sql = f"SELECT * FROM {ATHENA_DATABASE}.{ATHENA_TABLE} LIMIT 100"

        data = _run_query(sql)
        return _response(200, {"count": len(data), "data": data})

    except Exception as e:
        return _response(500, {"message": str(e)})
