# 05. 스로틀링 & Usage Plan & API Key

## 스로틀링(Throttling)

API Gateway가 Lambda(또는 백엔드)를 과부하로부터 보호.

| 항목 | 설명 |
|------|------|
| Steady-state rate | 초당 허용 요청 수 (RPS) |
| Burst limit | 순간 최대 요청 수 |
| 초과 시 응답 | `429 Too Many Requests` |

> AWS 계정 기본: 10,000 RPS / 버스트 5,000
> 스테이지 또는 메서드별로 개별 제한 설정 가능

---

## Usage Plan

특정 API Key에 **요청 한도(Quota)** 와 **속도 제한(Throttle)** 부여.

### 생성 순서

1. **API Key 생성**: API Gateway → API Keys → Create API Key
2. **Usage Plan 생성**: Usage Plans → Create
   - Throttle: RPS, Burst 설정
   - Quota: 일/주/월 최대 요청 수 설정
3. **Usage Plan에 API Key 연결**: Add API Key
4. **Usage Plan에 API Stage 연결**: Add API Stage
5. **메서드에서 API Key 필수 설정**: Method Request → API Key Required = `true`
6. **재배포**

### 호출 방법

```bash
# API Key를 x-api-key 헤더에 포함
curl https://{invoke-url}/prod/item \
  -H "x-api-key: YOUR_API_KEY"

# API Key 없이 호출 → 403 Forbidden
```

---

## Cognito Authorizer + API Key 동시 사용

```bash
# 두 헤더 모두 필요
curl https://{invoke-url}/prod/item \
  -H "Authorization: $TOKEN" \
  -H "x-api-key: YOUR_API_KEY"
```

---

## 정리

| 기능 | 목적 | 응답 코드 |
|------|------|-----------|
| Throttling | 과부하 방지 | 429 |
| API Key Required | 키 없는 접근 차단 | 403 |
| Cognito Authorizer | 미인증 사용자 차단 | 401 |
