# DomPerignon — 종합 정리

> AWS Lambda + API Gateway + RDS + Athena 패턴 모음

---

## 📁 레포 구조

```
DomPerignon/
├── Lambda/             # Lambda 함수 예제 (CRUD 단계별)
├── API Gateway/        # API Gateway 설정 가이드
├── Athena/             # Athena SQL 쿼리 템플릿
├── dml113/             # CTF 문제 풀이
└── docs/               # 종합 정리 (현재 파일)
```

---

## 1. Lambda (Lambda + API Gateway + RDS)

### 아키텍처 흐름

```
클라이언트
  └─► API Gateway (REST API)
        └─► Lambda Function
              └─► RDS MySQL (VPC 내부)
```

### 단계별 함수 구성

| 파일 | 지원 메서드 | 핵심 기능 |
|------|------------|----------|
| `lambda_function_1.py` | GET | 단건/전체 조회 |
| `lambda_function_2.py` | GET, POST | 생성 추가 |
| `lambda_function_3.py` | GET, POST, PUT, PATCH | 전체/부분 수정 |
| `lambda_function_4.py` | GET, POST, PUT, PATCH | `updated_at` 자동 갱신 |
| `lambda_function_5.py` | GET, POST, PUT | 필터 + 페이지네이션 |
| `lambda_function_6.py` | GET, POST, PUT, PATCH, DELETE | 완전한 CRUD + 필터/페이지네이션 |
| `lambda_function_7.py` | GET, POST, PUT, PATCH, DELETE | Soft Delete (`is_deleted` 플래그) |
| `lambda_function_8.py` | GET, POST(Bulk), DELETE(Bulk) | 배치 생성 / 배치 삭제 |

### 환경변수 (공통)

| 변수 | 설명 |
|------|------|
| `RDS_HOST` | RDS 엔드포인트 |
| `RDS_PORT` | 포트 (기본 `3306`) |
| `RDS_USER` | DB 사용자명 |
| `RDS_PASSWORD` | DB 비밀번호 |
| `RDS_DB` | DB 이름 |

> 보안 권장: 환경변수 평문 대신 **Secrets Manager** 사용 (`lambda_secrets_manager.py` 참고)

### Secrets Manager 패턴 (권장)

```python
import json, boto3

_SECRET_CACHE = None  # 웜 스타트 캐싱

def get_secret() -> dict:
    global _SECRET_CACHE
    if _SECRET_CACHE is not None:
        return _SECRET_CACHE
    client = boto3.client('secretsmanager', region_name='ap-northeast-2')
    response = client.get_secret_value(SecretId='prod/myapp/mysql')
    _SECRET_CACHE = json.loads(response['SecretString'])
    return _SECRET_CACHE
```

> `_SECRET_CACHE`를 모듈 레벨에 두면 웜 스타트 시 API 재호출 없이 재사용 → 비용·레이턴시 절감

### Lambda 응답 형식 (필수)

```python
return {
    "statusCode": 200,           # int
    "headers": {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
    },
    "body": json.dumps(data, default=str)  # 반드시 string
}
```

> `body`를 dict로 반환하면 `502 Bad Gateway` 발생

### VPC 설정 (RDS 접근 시)

- Lambda → RDS와 **동일 VPC + Private Subnet**
- Lambda SG → RDS SG 인바운드 **3306 허용**
- VPC Lambda에서 외부 API 호출 필요 시: **NAT Gateway** 또는 **VPC Endpoint** 필요

---

## 2. API Gateway

### Endpoint 타입

| 타입 | 설명 |
|------|------|
| `Regional` | 같은 리전 클라이언트 최적. 일반 사용 권장 |
| `Edge-Optimized` | CloudFront 앞단 경유. 글로벌 사용자 대상 |
| `Private` | VPC 내부에서만 접근 (VPC Endpoint 필요) |

### API 타입

| 타입 | 특징 | 주요 사용처 |
|------|------|------------|
| REST API | 가장 기능 풍부, Authorizer/캐싱/사용량 플랜 지원 | 범용 |
| HTTP API | 경량, 저비용, JWT Authorizer 기본 지원 | 단순 Lambda 연동 |
| WebSocket API | 양방향 실시간 통신 | 채팅, 알림 |

### Lambda Proxy Integration

> ⚠️ **반드시 체크** — 미체크 시 `httpMethod`, `path`, `queryStringParameters` 등이 event에 전달되지 않음

```json
{
  "httpMethod": "GET",
  "path": "/item",
  "pathParameters": { "id": "abc-123" },
  "queryStringParameters": { "id": "abc-123" },
  "headers": { "Authorization": "eyJ..." },
  "body": "{\"name\": \"test\"}",
  "isBase64Encoded": false
}
```

### CORS 설정

Lambda Proxy 방식에서는 Lambda 응답에 **직접** CORS 헤더 포함 필요.

```python
"headers": {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Api-Key",
}
```

> OPTIONS 메서드는 Authorizer 없이 허용해야 CORS preflight 통과

### Cognito Authorizer

1. Cognito User Pool 생성 (Client Secret 비활성화 권장)
2. API Gateway → Authorizers → `Type: Cognito` 설정
3. Token Source: `Authorization` 헤더
4. 메서드 Method Request → Authorization 연결
5. **반드시 재배포**

```bash
# 토큰 발급
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=user@example.com,PASSWORD=pass \
  --client-id <App Client ID>

# 인증 호출
curl https://{invoke-url}/prod/item -H "Authorization: $ID_TOKEN"
```

> Cognito Authorizer는 기본적으로 **IdToken** 사용. AccessToken은 `aud` claim 없어 검증 실패 가능

### Throttling & Usage Plan

| 설정 | 설명 |
|------|------|
| Stage-level throttling | API 전체 요청 제한 |
| Method-level throttling | 특정 메서드별 제한 |
| Usage Plan | API Key 단위로 요청 수/속도 제한 |

- **Burst limit**: 순간 최대 동시 요청 수 (Token Bucket)
- **Rate limit**: 초당 평균 요청 수

### Stages & Deployment

- 설정 변경 후 **Actions → Deploy API** 필수
- Stage 변수(`${stageVariables.xxx}`)로 환경별(dev/prod) Lambda 분리 가능
- Canary 배포: 트래픽 일부를 새 버전으로 라우팅 후 검증

---

## 3. Athena

> S3에 저장된 데이터를 Presto SQL로 쿼리하는 서버리스 분석 서비스

### 핵심 쿼리 패턴

```sql
-- 파티션 프루닝 (비용 절감 핵심)
SELECT * FROM db.table
WHERE year='2024' AND month='01' AND day='15';

-- JSON 컬럼 파싱
SELECT json_extract_scalar(payload, '$.user_id') AS user_id FROM table;

-- 배열 펼치기
SELECT id, tag FROM table CROSS JOIN UNNEST(tags) AS t(tag);

-- 윈도우 함수 (그룹 내 순위)
SELECT *, RANK() OVER (PARTITION BY dept ORDER BY salary DESC) AS rnk FROM table;

-- CTAS (결과를 S3 Parquet으로 저장)
CREATE TABLE new_table WITH (
  format = 'PARQUET',
  external_location = 's3://bucket/prefix/',
  partitioned_by = ARRAY['dt']
) AS SELECT * FROM source_table WHERE condition;

-- 최근 N일 필터
SELECT * FROM table
WHERE date_col >= DATE_ADD('day', -7, CURRENT_DATE);

-- 월별 집계
SELECT DATE_TRUNC('month', created_at) AS month, COUNT(*) AS cnt
FROM table GROUP BY 1 ORDER BY 1;
```

### 비용 최적화

- 파티션 컬럼(`year/month/day`)으로 스캔 범위 최소화
- Parquet / ORC 컬럼형 포맷 사용 → 스캔 데이터 감소
- CTAS로 중간 결과 캐싱

---

## 4. 향후 추가 가능한 내용

### 인프라 / 배포
- [ ] **Terraform** — Lambda + API Gateway + RDS IaC 코드
- [ ] **SAM / CDK** — 서버리스 앱 배포 템플릿
- [ ] **GitHub Actions CI/CD** — Lambda 자동 배포 워크플로우

### Lambda 고급
- [ ] **Lambda Layer** — `pymysql` 등 공통 패키지 레이어화
- [ ] **Lambda Alias + Versioning** — 트래픽 분산 배포
- [ ] **Dead Letter Queue (DLQ)** — 비동기 실패 처리
- [ ] **Lambda Power Tuning** — 메모리/비용 최적화
- [ ] **Connection Pooling (RDS Proxy)** — DB 커넥션 재사용

### 보안
- [ ] **WAF 연동** — API Gateway에 Web ACL 적용
- [ ] **Lambda Authorizer** — 커스텀 토큰 검증 로직
- [ ] **API Key 관리** — Usage Plan + API Key 발급 자동화
- [ ] **KMS 암호화** — Secrets Manager 시크릿 KMS 키 지정

### 모니터링
- [ ] **CloudWatch Alarms** — 에러율/레이턴시 임계값 알람
- [ ] **X-Ray Tracing** — Lambda + API Gateway 분산 추적
- [ ] **CloudWatch Logs Insights** — 로그 분석 쿼리 패턴

### 데이터 파이프라인
- [ ] **S3 + Glue + Athena** — ETL 파이프라인 예제
- [ ] **Kinesis Data Streams** → Lambda — 실시간 이벤트 처리
- [ ] **EventBridge** → Lambda — 스케줄/이벤트 기반 트리거

---

## 5. 자주 겪는 오류 & 해결

| 오류 | 원인 | 해결 |
|------|------|------|
| `502 Bad Gateway` | Lambda `body`를 dict로 반환 | `json.dumps(body)` 로 string 변환 |
| `403 Forbidden` | Authorizer 연결 후 재배포 안 함 | Deploy API 실행 |
| `401 Unauthorized` | AccessToken 사용 (Cognito 기본은 IdToken) | IdToken 사용으로 변경 |
| DB 연결 실패 | Lambda VPC ↔ RDS SG 3306 미허용 | Security Group 인바운드 규칙 추가 |
| CORS 에러 | OPTIONS 메서드에 Authorizer 적용됨 | OPTIONS는 Authorizer 없이 설정 |
| 외부 API 호출 실패 (VPC Lambda) | VPC에서 인터넷 차단 | NAT Gateway 또는 VPC Endpoint 추가 |
| Athena 스캔 비용 과다 | 파티션 미사용 | WHERE에 파티션 컬럼 조건 추가 |
| Secrets Manager 매 요청 호출 | 캐싱 미구현 | 모듈 레벨 `_SECRET_CACHE` 변수 사용 |
