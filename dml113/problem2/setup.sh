#!/bin/bash
# ============================================================
# Problem 2 — Query from S3 세팅 (CloudShell 기준)
# ============================================================

REGION="ap-northeast-2"
BUCKET="<bucket-name>"
RESULT_BUCKET="<result-bucket-name>"
GLUE_DB="wsi_db"
ATHENA_WORKGROUP="wsi-workgroup"

# ── 1. S3 버킷 생성 ──────────────────────────────────────────

aws s3 mb s3://${BUCKET} --region ${REGION}
aws s3 mb s3://${RESULT_BUCKET} --region ${REGION}

# 버킷 퍼블릭 액세스 차단 (기본값 유지)
aws s3api put-public-access-block \
  --bucket ${BUCKET} \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# 데이터 업로드 (CSV 예시)
# aws s3 cp data.csv s3://${BUCKET}/data/

# ── 2. Glue 데이터베이스 생성 ─────────────────────────────────

aws glue create-database \
  --region ${REGION} \
  --database-input "{\"Name\": \"${GLUE_DB}\"}"

# ── 3. Athena 워크그룹 생성 ───────────────────────────────────

aws athena create-work-group \
  --region ${REGION} \
  --name ${ATHENA_WORKGROUP} \
  --configuration "{
    \"ResultConfiguration\": {
      \"OutputLocation\": \"s3://${RESULT_BUCKET}/results/\"
    },
    \"EnforceWorkGroupConfiguration\": true,
    \"PublishCloudWatchMetricsEnabled\": false
  }"

# ── 4. Athena DDL 실행 (테이블 생성) ─────────────────────────

QUERY_ID=$(aws athena start-query-execution \
  --region ${REGION} \
  --query-string "$(cat ddl.sql)" \
  --work-group ${ATHENA_WORKGROUP} \
  --query-execution-context "Database=${GLUE_DB}" \
  --query 'QueryExecutionId' \
  --output text)

echo "DDL QueryExecutionId: ${QUERY_ID}"

# ── 5. 쿼리 실행 상태 확인 ───────────────────────────────────

aws athena get-query-execution \
  --region ${REGION} \
  --query-execution-id ${QUERY_ID} \
  --query 'QueryExecution.Status.State' \
  --output text

# ── 6. 쿼리 결과 조회 ─────────────────────────────────────────

QUERY_ID=$(aws athena start-query-execution \
  --region ${REGION} \
  --work-group ${ATHENA_WORKGROUP} \
  --query-string "SELECT * FROM ${GLUE_DB}.wsi_table LIMIT 10" \
  --query-execution-context "Database=${GLUE_DB}" \
  --query 'QueryExecutionId' \
  --output text)

# 완료 대기
sleep 3

aws athena get-query-results \
  --region ${REGION} \
  --query-execution-id ${QUERY_ID}
