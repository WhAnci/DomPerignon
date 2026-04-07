# Problem 4 — MySQL with Lambda

## 아키텍처

```
클라이언트 (HTTP)
    │
    ▼
Lambda Function URL   ← HTTPS 엔드포인트 (API Gateway 없이 Lambda에 직접 URL)
    │
    ▼
Lambda (VPC 내 실행)   ← IAM 역할로 RDS Proxy 인증 토큰 생성
    │  IAM 인증 토큰 (패스워드 없음)
    ▼
RDS Proxy             ← 커넥션 풀 관리, IAM 인증 처리
    │
    ▼
RDS MySQL (프라이빗 서브넷)
```

---

## 개념 이해

### Lambda Function URL
- Lambda에 고정 HTTPS 엔드포인트를 직접 부여하는 기능
- API Gateway 없이 HTTP 요청 수신 가능
- 이벤트 구조가 API Gateway와 다름 → `requestContext.http.method` 로 메서드 추출

### RDS Proxy + IAM 인증
- 패스워드 없이 IAM 역할 기반으로 DB 연결
- Lambda가 `generate_db_auth_token()` 호출 → 임시 토큰 생성 → pymysql password로 전달
- RDS Proxy가 토큰 검증 후 실제 RDS로 연결 위임
- Lambda에 `rds-db:connect` 권한 필요

### VPC 내 Lambda 실행
- Lambda가 프라이빗 서브넷 안의 RDS에 접근하려면 Lambda를 VPC에 붙여야 함
- Lambda용 보안 그룹 → RDS Proxy 보안 그룹 TCP 3306 인바운드 허용

---

## 파일 설명

| 파일 | 용도 |
|------|------|
| `init.sql` | RDS MySQL DB·테이블 생성, 샘플 데이터, IAM 인증 유저 생성 |
| `lambda_function.py` | Lambda Function URL 기반 CRUD (GET·POST·PUT·DELETE) |

---

## 세팅 순서

### 1단계 — VPC·서브넷·보안 그룹

```
VPC
├── 프라이빗 서브넷 (AZ-a, AZ-c)  ← RDS·RDS Proxy 위치
└── 보안 그룹
    ├── sg-lambda  : 아웃바운드 3306 → sg-rds-proxy 허용
    └── sg-rds-proxy : 인바운드 3306 from sg-lambda 허용
```

### 2단계 — RDS MySQL 생성

```bash
# 서브넷 그룹 생성
aws rds create-db-subnet-group \
  --db-subnet-group-name wsi-db-subnet-group \
  --db-subnet-group-description "WSI DB Subnet Group" \
  --subnet-ids <subnet-a-id> <subnet-c-id>

# RDS 생성
aws rds create-db-instance \
  --db-instance-identifier wsi-mysql \
  --db-instance-class db.t3.micro \
  --engine mysql \
  --master-username admin \
  --master-user-password <password> \
  --db-subnet-group-name wsi-db-subnet-group \
  --vpc-security-group-ids <sg-rds-proxy-id> \
  --no-publicly-accessible
```

### 3단계 — RDS Proxy 생성

```bash
aws rds create-db-proxy \
  --db-proxy-name wsi-rds-proxy \
  --engine-family MYSQL \
  --auth '[{
    "AuthScheme": "SECRETS",
    "IAMAuth": "REQUIRED",
    "SecretArn": "<secret-arn>"
  }]' \
  --role-arn <proxy-role-arn> \
  --vpc-subnet-ids <subnet-a-id> <subnet-c-id> \
  --vpc-security-group-ids <sg-rds-proxy-id>

# 프록시 타겟 등록
aws rds register-db-proxy-targets \
  --db-proxy-name wsi-rds-proxy \
  --db-instance-identifiers wsi-mysql
```

### 4단계 — DB 초기화

RDS에 접속해서 `init.sql` 실행

```bash
mysql -h <rds-endpoint> -u admin -p < init.sql
```

### 5단계 — Lambda 생성

```bash
# 배포 패키지 생성 (pymysql 포함)
pip install pymysql -t ./package
cp lambda_function.py ./package/
cd package && zip -r ../function.zip .

# Lambda 생성
aws lambda create-function \
  --function-name wsi-mysql-lambda \
  --runtime python3.12 \
  --handler lambda_function.lambda_handler \
  --role <lambda-role-arn> \
  --zip-file fileb://function.zip \
  --vpc-config SubnetIds=<subnet-a-id>,<subnet-c-id>,SecurityGroupIds=<sg-lambda-id> \
  --environment Variables='{
    "DB_HOST": "<rds-proxy-endpoint>",
    "DB_USER": "<db-user>",
    "DB_NAME": "wsi_db"
  }'

# Function URL 활성화
aws lambda create-function-url-config \
  --function-name wsi-mysql-lambda \
  --auth-type NONE
```

### 6단계 — Lambda IAM 역할에 rds-db:connect 권한 추가

```json
{
  "Effect": "Allow",
  "Action": "rds-db:connect",
  "Resource": "arn:aws:rds-db:<region>:<account-id>:dbuser:<proxy-resource-id>/<db-user>"
}
```

---

## API 사용법 (Function URL 기준)

```bash
FUNC_URL="https://<function-url>.lambda-url.ap-northeast-2.on.aws"

# 전체 조회
curl "${FUNC_URL}/"

# 단건 조회
curl "${FUNC_URL}/?id=1"

# 생성
curl -X POST "${FUNC_URL}/" \
  -H "Content-Type: application/json" \
  -d '{"name": "test", "value": 99.9}'

# 수정
curl -X PUT "${FUNC_URL}/?id=1" \
  -H "Content-Type: application/json" \
  -d '{"name": "updated", "value": 50.0}'

# 삭제
curl -X DELETE "${FUNC_URL}/?id=1"
```

---

## 자주 나오는 포인트

| 상황 | 해결 |
|------|------|
| Lambda → RDS 연결 안 됨 | Lambda 보안 그룹이 RDS Proxy SG로 3306 아웃바운드 허용인지 확인 |
| IAM 인증 토큰 오류 | Lambda 역할에 `rds-db:connect` 권한 있는지 확인 |
| pymysql 모듈 없음 | 배포 패키지에 pymysql 포함 또는 Lambda Layer 추가 |
| RDS Proxy 연결 타임아웃 | Lambda VPC 서브넷이 RDS Proxy와 같은 VPC인지 확인 |
| SSL 오류 | `ssl={"ssl": True}` pymysql 연결에 추가 |
