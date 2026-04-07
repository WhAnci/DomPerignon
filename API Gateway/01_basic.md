# 01. REST API + Lambda Proxy 기본 연동

## 1. REST API 생성

콘솔 → API Gateway → **Create API** → REST API → Build

| 항목 | 값 |
|------|----|
| API name | 요구사항에 맞게 |
| Endpoint Type | Regional |

> **Endpoint Type 차이**
> - `Regional` : 같은 리전 클라이언트 최적. 일반 사용 권장
> - `Edge-Optimized` : CloudFront 앞단 경유. 글로벌 사용자 대상
> - `Private` : VPC 내부에서만 접근 (VPC Endpoint 필요)

---

## 2. 리소스 생성

**Actions → Create Resource**

| 항목 | 값 |
|------|----|
| Resource Path | `/item` |
| Enable API Gateway CORS | ✅ 체크 (CORS 요구 시) |

> 경로 파라미터 방식(`ID_SOURCE = "path"`) 요구 시 `/item/{id}` 리소스도 추가 생성

---

## 3. 메서드 연결

`/item` 선택 → **Actions → Create Method** → `ANY` (또는 GET, POST, PUT, DELETE 개별)

| 항목 | 값 |
|------|----|
| Integration type | Lambda Function |
| Use Lambda Proxy integration | ✅ **반드시 체크** |
| Lambda Function | 연결할 함수 이름 입력 |

> ⚠️ **Lambda Proxy integration 미체크 시** `httpMethod`, `path`, `queryStringParameters` 등이 event에 전달되지 않아 함수가 정상 동작하지 않음

### Lambda Proxy integration event 구조

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

> `body`는 **문자열(string)** 형태로 전달 → Lambda 내부에서 `json.loads(event['body'])` 필요

---

## 4. CORS 헤더 추가 (Lambda 코드)

Lambda Proxy 방식에서는 **Lambda 응답에 직접 CORS 헤더를 넣어야** 함.

```python
def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Api-Key",
        },
        "body": json.dumps(body, default=str),
    }
```

> CORS 요구사항이 없으면 `Content-Type`만 있어도 무방

---

## 5. API 배포

**Actions → Deploy API**

| 항목 | 값 |
|------|----|
| Deployment stage | [New Stage] |
| Stage name | `prod` (요구사항에 맞게) |

배포 후 Invoke URL:
```
https://{api-id}.execute-api.ap-northeast-2.amazonaws.com/prod/item
```

> ⚠️ **메서드/Authorizer/통합 설정을 변경하면 반드시 재배포** 해야 적용됨

---

## 6. 동작 확인

```bash
# 전체 조회
curl https://{invoke-url}/prod/item

# 단일 조회 (query 방식)
curl https://{invoke-url}/prod/item?id=<uuid>

# 단일 조회 (path 방식)
curl https://{invoke-url}/prod/item/<uuid>

# 생성
curl -X POST https://{invoke-url}/prod/item \
  -H "Content-Type: application/json" \
  -d '{"name": "test", "category": "food", "price": 1000}'

# 수정 (전체)
curl -X PUT https://{invoke-url}/prod/item?id=<uuid> \
  -H "Content-Type: application/json" \
  -d '{"name": "updated", "category": "drink", "price": 2000}'

# 부분 수정
curl -X PATCH https://{invoke-url}/prod/item?id=<uuid> \
  -H "Content-Type: application/json" \
  -d '{"price": 1500}'

# 삭제
curl -X DELETE https://{invoke-url}/prod/item?id=<uuid>
```

---

## 7. Lambda 환경변수 설정

Lambda 함수 → Configuration → Environment variables

| Key | Value |
|-----|-------|
| `RDS_HOST` | RDS 엔드포인트 |
| `RDS_PORT` | `3306` |
| `RDS_USER` | DB 사용자명 |
| `RDS_PASSWORD` | DB 비밀번호 |
| `RDS_DB` | DB 이름 |

> 보안 강화 시: Secrets Manager에 저장 후 Lambda에서 boto3로 조회

---

## 8. VPC Lambda (RDS 접근 시)

Lambda → Configuration → VPC

- RDS와 **동일한 VPC + Private Subnet** 선택
- Lambda용 Security Group → RDS Security Group의 **3306 포트 인바운드 허용**
- RDS Security Group 인바운드: Lambda SG에서 3306 허용

> Lambda를 VPC에 넣으면 인터넷 접근이 차단됨.  
> 외부 API 호출 필요 시 **NAT Gateway** 또는 **VPC Endpoint** 추가 필요

---

## 9. Lambda 응답 형식 (필수 구조)

```python
# 반드시 이 형식으로 반환해야 API Gateway가 정상 처리
return {
    "statusCode": 200,          # HTTP 상태 코드 (int)
    "headers": { ... },         # 선택 (CORS 등)
    "body": json.dumps(data)    # 반드시 string 형태
}
```

> `body`를 dict로 반환하면 `502 Bad Gateway` 발생
