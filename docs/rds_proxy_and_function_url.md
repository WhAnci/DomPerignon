# RDS Proxy 생성 & Lambda Function URL 가이드

---

## 1. RDS Proxy 생성

### 왜 RDS Proxy를 쓰나?

| 항목 | RDS 직접 연결 | RDS Proxy 경유 |
|------|-------------|---------------|
| 커넥션 수 | Lambda 인스턴스 수 × 1 | Proxy가 풀링 — RDS 부하 감소 |
| 콜드 스타트 | 매번 DB 핸드셰이크 | Proxy가 미리 연결 유지 |
| 장애 복구 | 앱이 직접 재연결 | Proxy가 자동 failover |
| 비밀번호 교체 | Lambda 재배포 필요 | Secrets Manager 연동으로 무중단 교체 |

---

### 1-1. 사전 준비

1. **Secrets Manager에 DB 자격 증명 저장** (Proxy 필수 요건)

```json
{
  "username": "admin",
  "password": "yourpassword"
}
```

> RDS 콘솔에서 자동 생성되는 시크릿 형식과 동일하면 됩니다.

2. RDS 인스턴스가 **VPC 내 Private Subnet**에 존재하는지 확인

---

### 1-2. RDS Proxy 생성 (콘솔)

RDS 콘솔 → **Proxies → Create proxy**

| 항목 | 값 |
|------|---------|
| Proxy identifier | `myapp-proxy` (임의) |
| Engine family | `MySQL` (또는 PostgreSQL) |
| Require Transport Layer Security | 필요 시 체크 |
| IAM role | 신규 생성 또는 기존 Role 선택 |
| Secrets Manager secret | 위에서 생성한 시크릿 선택 |
| VPC | RDS와 동일한 VPC |
| VPC subnets | Private Subnet 2개 이상 선택 |
| VPC security group | Proxy 전용 SG 생성 권장 |
| RDS DB instance | 대상 RDS 인스턴스 선택 |

**Create proxy** 클릭 → 생성까지 약 5~10분 소요

생성 완료 후 **Proxy endpoint** 복사:
```
myapp-proxy.proxy-xxxxxxxxxxxx.ap-northeast-2.rds.amazonaws.com
```

---

### 1-3. Security Group 설정

```
Lambda SG
  └── Outbound 3306 → Proxy SG

Proxy SG
  └── Inbound  3306 from Lambda SG
  └── Outbound 3306 → RDS SG

RDS SG
  └── Inbound  3306 from Proxy SG
```

> Lambda SG와 RDS SG 사이에 **직접 규칙은 불필요**합니다.

---

### 1-4. Lambda 환경변수 설정

Lambda 함수 → Configuration → Environment variables

| Key | Value |
|-----|-------|
| `RDS_HOST` | Proxy 엔드포인트 (위에서 복사한 값) |
| `RDS_PORT` | `3306` |
| `RDS_USER` | DB 사용자명 |
| `RDS_PASSWORD` | DB 비밀번호 |
| `RDS_DB` | 데이터베이스 이름 |
| `HEALTH_CHECK_INTERVAL` | `60` (헬스체크 주기, 초) |

---

### 1-5. Lambda VPC 설정

Lambda 함수 → Configuration → VPC

- VPC: RDS Proxy와 동일한 VPC
- Subnets: Private Subnet (Proxy와 같은 가용영역 포함)
- Security Group: Lambda 전용 SG (Proxy SG에 3306 허용된 것)

> Lambda가 VPC에 배치되면 기본적으로 인터넷 접근이 차단됩니다.  
> 외부 API 호출이 필요하면 **NAT Gateway** 또는 **VPC Endpoint**를 추가하세요.

---

### 1-6. 동작 확인

```bash
# Lambda 테스트 이벤트
{
  "httpMethod": "GET",
  "path": "/item",
  "queryStringParameters": null
}
```

CloudWatch Logs에서 `[DB] 새 커넥션 생성 완료` 로그 확인

---

## 2. Lambda Function URL

### Function URL이란?

API Gateway 없이 Lambda에 **전용 HTTPS 엔드포인트**를 직접 부여하는 기능입니다.

| 항목 | API Gateway | Function URL |
|------|------------|-------------|
| 비용 | 요청 수 기반 과금 | Lambda 실행 비용만 |
| Authorizer | Cognito, Lambda, JWT 등 | `AWS_IAM` 또는 `NONE` |
| 커스텀 도메인 | 지원 | 미지원 (CloudFront 앞에 배치 필요) |
| Throttling / Usage Plan | 지원 | 미지원 |
| WebSocket | 지원 | 미지원 |
| 적합한 상황 | 복잡한 라우팅/인증 필요 | 빠른 프로토타입, 단순 엔드포인트 |

---

### 2-1. Function URL 생성 (콘솔)

Lambda 함수 → Configuration → **Function URL → Create function URL**

| 항목 | 값 |
|------|---------|
| Auth type | `NONE` (공개) 또는 `AWS_IAM` (IAM 인증) |
| CORS — Allow origin | `*` (또는 특정 도메인) |
| CORS — Allow methods | `GET, POST, OPTIONS` |
| CORS — Allow headers | `Content-Type, Authorization` |

> `NONE`으로 설정하면 누구나 호출 가능합니다.  
> 운영 환경에서는 `AWS_IAM` 또는 앞에 API Gateway/CloudFront를 두는 것을 권장합니다.

생성 후 URL 확인:
```
https://xxxxxxxxxxxxxxxx.lambda-url.ap-northeast-2.on.aws/
```

---

### 2-2. Function URL 이벤트 구조

API Gateway와 다르게 `requestContext.http` 안에 메서드/경로가 들어옵니다.

```json
{
  "requestContext": {
    "http": {
      "method": "GET",
      "path": "/item",
      "sourceIp": "1.2.3.4"
    }
  },
  "rawPath": "/item",
  "rawQueryString": "id=abc-123",
  "queryStringParameters": { "id": "abc-123" },
  "headers": { "content-type": "application/json" },
  "body": null,
  "isBase64Encoded": false
}
```

> `lambda_rds_proxy.py`의 `_normalize_event()` 함수가 API Gateway ↔ Function URL 이벤트를 자동으로 통일합니다.

---

### 2-3. 동작 확인

```bash
FUNCTION_URL="https://xxxxxxxx.lambda-url.ap-northeast-2.on.aws"

# 전체 조회
curl "$FUNCTION_URL/item"

# 단건 조회
curl "$FUNCTION_URL/item?id=1"

# 생성
curl -X POST "$FUNCTION_URL/item" \
  -H "Content-Type: application/json" \
  -d '{"name": "아메리카노", "category": "음료", "price": 4500}'
```

---

### 2-4. AWS_IAM 인증 호출 (선택)

`Auth type: AWS_IAM` 설정 시 SigV4 서명이 필요합니다.

```bash
# AWS CLI로 호출
aws lambda invoke-url \
  --function-url-arn <FUNCTION_ARN> \
  --payload '{"rawPath":"/item"}' response.json

# Python (aws-requests-auth 사용)
pip install aws-requests-auth
```

```python
from aws_requests_auth.aws_auth import AWSRequestsAuth
import requests, boto3

session = boto3.Session()
creds = session.get_credentials().get_frozen_credentials()

auth = AWSRequestsAuth(
    aws_access_key=creds.access_key,
    aws_secret_access_key=creds.secret_key,
    aws_token=creds.token,
    aws_host="xxxxxxxx.lambda-url.ap-northeast-2.on.aws",
    aws_region="ap-northeast-2",
    aws_service="lambda",
)

response = requests.get(
    "https://xxxxxxxx.lambda-url.ap-northeast-2.on.aws/item",
    auth=auth,
)
print(response.json())
```

---

## 3. 연결 흐름 정리

### API Gateway 사용 시
```
클라이언트
  → API Gateway (REST API)
    → Lambda (lambda_rds_proxy.py)
      → RDS Proxy
        → RDS MySQL
```

### Function URL 사용 시
```
클라이언트
  → Lambda Function URL (HTTPS)
    → Lambda (lambda_rds_proxy.py)
      → RDS Proxy
        → RDS MySQL
```

> 두 경로 모두 `lambda_rds_proxy.py` 하나로 처리 가능합니다 (`_normalize_event()` 덕분).

---

## 4. 헬스체크 동작 원리

```python
# 웜 스타트 시 HEALTH_CHECK_INTERVAL 초마다 ping 실행
_conn.ping(reconnect=False)   # 살아있으면 재사용
                               # 실패 시 → 재연결
```

| 상황 | 동작 |
|------|------|
| 콜드 스타트 | 새 커넥션 생성 |
| 웜 스타트 (INTERVAL 미경과) | 기존 커넥션 재사용 |
| 웜 스타트 (INTERVAL 경과) | ping → 성공 시 재사용 / 실패 시 재연결 |
| RDS Proxy 장애 | ping 실패 → 재연결 → Proxy가 다른 RDS로 라우팅 |

> RDS Proxy 자체가 커넥션 풀을 관리하므로, Lambda 쪽 커넥션은 **단일 커넥션**으로 충분합니다.
