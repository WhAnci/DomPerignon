#!/bin/bash
# ============================================================
# Problem 4 — MySQL with Lambda 세팅 (CloudShell 기준)
# ============================================================

REGION="ap-northeast-2"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

VPC_ID="<vpc-id>"
SUBNET_A="<subnet-a-id>"
SUBNET_C="<subnet-c-id>"
SG_LAMBDA="<sg-lambda-id>"
SG_PROXY="<sg-proxy-id>"

DB_INSTANCE="wsi-mysql"
DB_PROXY="wsi-rds-proxy"
FUNC_NAME="wsi-mysql-lambda"
SECRET_NAME="wsi/mysql/credentials"
ROLE_NAME="wsi-lambda-role"

# ── 1. Secrets Manager — DB 크레덴셜 저장 ────────────────────

SECRET_ARN=$(aws secretsmanager create-secret \
  --region ${REGION} \
  --name ${SECRET_NAME} \
  --secret-string "{
    \"username\": \"admin\",
    \"password\": \"<db-password>\",
    \"engine\": \"mysql\",
    \"host\": \"<rds-endpoint>\",
    \"port\": 3306,
    \"dbname\": \"wsi_db\"
  }" \
  --query 'ARN' --output text)

echo "Secret ARN: ${SECRET_ARN}"

# ── 2. Lambda IAM 역할 생성 ───────────────────────────────────

ROLE_ARN=$(aws iam create-role \
  --role-name ${ROLE_NAME} \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' \
  --query 'Role.Arn' --output text)

echo "Role ARN: ${ROLE_ARN}"

# 정책 연결
aws iam put-role-policy \
  --role-name ${ROLE_NAME} \
  --policy-name wsi-lambda-policy \
  --policy-document file://lambda_role.json

# ── 3. RDS Proxy IAM 역할 생성 ────────────────────────────────

PROXY_ROLE_ARN=$(aws iam create-role \
  --role-name wsi-rds-proxy-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "rds.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' \
  --query 'Role.Arn' --output text)

aws iam put-role-policy \
  --role-name wsi-rds-proxy-role \
  --policy-name wsi-proxy-secrets-policy \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Action\": [\"secretsmanager:GetSecretValue\", \"secretsmanager:DescribeSecret\"],
      \"Resource\": \"${SECRET_ARN}\"
    }]
  }"

# ── 4. RDS Proxy 생성 ─────────────────────────────────────────

PROXY_ARN=$(aws rds create-db-proxy \
  --region ${REGION} \
  --db-proxy-name ${DB_PROXY} \
  --engine-family MYSQL \
  --auth "[{
    \"AuthScheme\": \"SECRETS\",
    \"IAMAuth\": \"REQUIRED\",
    \"SecretArn\": \"${SECRET_ARN}\"
  }]" \
  --role-arn ${PROXY_ROLE_ARN} \
  --vpc-subnet-ids ${SUBNET_A} ${SUBNET_C} \
  --vpc-security-group-ids ${SG_PROXY} \
  --query 'DBProxy.DBProxyArn' --output text)

echo "Proxy ARN: ${PROXY_ARN}"

# 프록시 타겟 등록 (RDS 인스턴스 연결)
aws rds register-db-proxy-targets \
  --region ${REGION} \
  --db-proxy-name ${DB_PROXY} \
  --db-instance-identifiers ${DB_INSTANCE}

# 프록시 엔드포인트 확인
PROXY_ENDPOINT=$(aws rds describe-db-proxies \
  --region ${REGION} \
  --db-proxy-name ${DB_PROXY} \
  --query 'DBProxies[0].Endpoint' --output text)

echo "Proxy Endpoint: ${PROXY_ENDPOINT}"

# ── 5. Lambda 배포 패키지 생성 ────────────────────────────────

mkdir -p /tmp/lambda_package
pip install pymysql -t /tmp/lambda_package --quiet
cp lambda_function.py /tmp/lambda_package/
cd /tmp/lambda_package && zip -r /tmp/function.zip . -q
cd -

# ── 6. Lambda 함수 생성 ───────────────────────────────────────

# 역할 전파 대기 (IAM 전파 지연)
sleep 10

FUNC_ARN=$(aws lambda create-function \
  --region ${REGION} \
  --function-name ${FUNC_NAME} \
  --runtime python3.12 \
  --handler lambda_function.lambda_handler \
  --role ${ROLE_ARN} \
  --zip-file fileb:///tmp/function.zip \
  --timeout 30 \
  --memory-size 256 \
  --vpc-config "SubnetIds=${SUBNET_A},${SUBNET_C},SecurityGroupIds=${SG_LAMBDA}" \
  --environment "Variables={
    DB_HOST=${PROXY_ENDPOINT},
    DB_PORT=3306,
    DB_USER=<db-user>,
    DB_NAME=wsi_db
  }" \
  --query 'FunctionArn' --output text)

echo "Function ARN: ${FUNC_ARN}"

# ── 7. Lambda Function URL 활성화 ────────────────────────────

FUNC_URL=$(aws lambda create-function-url-config \
  --region ${REGION} \
  --function-name ${FUNC_NAME} \
  --auth-type NONE \
  --query 'FunctionUrl' --output text)

# 퍼블릭 호출 허용
aws lambda add-permission \
  --region ${REGION} \
  --function-name ${FUNC_NAME} \
  --statement-id FunctionURLAllowPublicAccess \
  --action lambda:InvokeFunctionUrl \
  --principal "*" \
  --function-url-auth-type NONE

echo "Function URL: ${FUNC_URL}"

# ── 8. Lambda rds-db:connect 권한 추가 ───────────────────────

PROXY_RESOURCE_ID=$(aws rds describe-db-proxies \
  --region ${REGION} \
  --db-proxy-name ${DB_PROXY} \
  --query 'DBProxies[0].DBProxyArn' --output text | cut -d: -f7)

aws iam put-role-policy \
  --role-name ${ROLE_NAME} \
  --policy-name wsi-rds-connect-policy \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Action\": \"rds-db:connect\",
      \"Resource\": \"arn:aws:rds-db:${REGION}:${ACCOUNT_ID}:dbuser:${PROXY_RESOURCE_ID}/<db-user>\"
    }]
  }"

echo ""
echo "===== 완료 ====="
echo "Function URL: ${FUNC_URL}"
echo "Proxy Endpoint: ${PROXY_ENDPOINT}"
