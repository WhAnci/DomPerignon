# 02. Cognito Authorizer

인증된 사용자만 API를 호출할 수 있도록 Cognito User Pool을 Authorizer로 연결하는 방법.

---

## 1. Cognito User Pool 생성

Cognito → **Create user pool**

| 항목 | 값 |
|------|----|
| Sign-in option | Email (또는 요구사항에 맞게) |
| Password policy | 요구사항에 맞게 |
| App client name | 요구사항에 맞게 |
| Client secret | **Generate a client secret → 체크 해제** (Lambda/CLI에서 사용 시 없는 게 편함) |

생성 후 메모:
- **User Pool ID**: `ap-northeast-2_XXXXXXXXX`
- **App Client ID**: `xxxxxxxxxxxxxxxxxxxxxxxxxx`

---

## 2. 테스트 유저 생성

```bash
# 유저 생성
aws cognito-idp admin-create-user \
  --user-pool-id ap-northeast-2_XXXXXXXXX \
  --username test@example.com \
  --temporary-password Temp1234!

# 비밀번호 영구 설정 (FORCE_CHANGE_PASSWORD 상태 해제)
aws cognito-idp admin-set-user-password \
  --user-pool-id ap-northeast-2_XXXXXXXXX \
  --username test@example.com \
  --password Final1234! \
  --permanent
```

---

## 3. 토큰 발급

```bash
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=test@example.com,PASSWORD=Final1234! \
  --client-id <App Client ID>
```

응답에서 `IdToken` 또는 `AccessToken` 복사:

```json
{
  "AuthenticationResult": {
    "IdToken": "eyJhbG...",
    "AccessToken": "eyJhbG...",
    "RefreshToken": "eyJhbG...",
    "ExpiresIn": 3600,
    "TokenType": "Bearer"
  }
}
```

> **토큰 유효기간**: 기본 1시간(3600초). `RefreshToken`으로 재발급 가능

---

## 4. API Gateway Authorizer 생성

API Gateway → 해당 API → **Authorizers → Create New Authorizer**

| 항목 | 값 |
|------|----|
| Name | 요구사항에 맞게 |
| Type | **Cognito** |
| Cognito User Pool | 위에서 만든 User Pool 선택 |
| Token Source | `Authorization` |
| Token Validation | 비워두기 (선택사항) |

**Create** 클릭

---

## 5. 메서드에 Authorizer 연결

`/item` → `ANY` (또는 각 메서드) → **Method Request**

| 항목 | 값 |
|------|----|
| Authorization | 위에서 만든 Authorizer 선택 |

변경 후 반드시 **Actions → Deploy API** 재배포

---

## 6. 인증 토큰으로 API 호출

```bash
TOKEN="eyJhbG..."

# 인증 성공
curl https://{invoke-url}/prod/item \
  -H "Authorization: $TOKEN"

# 토큰 없이 호출 → 401 Unauthorized
curl https://{invoke-url}/prod/item

# 만료된 토큰 → 401 Unauthorized
```

---

## 7. Lambda에서 Cognito 유저 정보 꺼내기

Authorizer가 검증한 뒤 `event['requestContext']['authorizer']`에 유저 정보가 담김.

```python
def lambda_handler(event, context):
    claims = event['requestContext']['authorizer']['claims']
    user_email = claims.get('email')
    user_sub = claims.get('sub')   # Cognito 고유 User ID
    print(f"호출자: {user_email}, sub: {user_sub}")
```

---

## 8. 주의사항

| 항목 | 설명 |
|------|------|
| Token Source | `Authorization` 헤더 — `Bearer` prefix 불필요 (IdToken 그대로) |
| IdToken vs AccessToken | Cognito Authorizer 기본은 **IdToken** 사용. AccessToken은 `aud` claim이 없어 검증 실패할 수 있음 |
| CORS + Authorizer | OPTIONS 메서드는 Authorizer 없이 허용해야 CORS preflight 통과 |
| 재배포 필수 | Authorizer 연결 후 반드시 Deploy API 해야 적용됨 |
| Client Secret 설정 시 | `SECRET_HASH` 계산이 필요 — CLI 호출 복잡해짐. 학습 환경에서는 Client Secret 비활성화 권장 |

---

## 9. Authorizer 캐싱

- 기본 TTL: **300초 (5분)**
- 동일 토큰 반복 요청 시 캐시된 결과 반환 → Lambda Authorizer 호출 비용 절감
- Cognito Authorizer는 캐싱 TTL 직접 설정 가능 (0 = 캐싱 비활성화)

```
캐싱 비활성화 시: 모든 요청마다 Cognito 토큰 검증 수행
캐싱 활성화 시: TTL 내 동일 토큰은 재검증 없이 허용/거부 결정
```
