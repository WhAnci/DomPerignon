# 07. 과제/시험 빈출 포인트

## ✅ 자주 틀리는 것들

### 1. Lambda Proxy Integration 반드시 체크

```
❌ 미체크 → event에 httpMethod, path, body 등 전달 안 됨
✅ 체크   → 전체 HTTP 요청 정보가 event에 담겨 Lambda로 전달
```

### 2. 배포(Deploy) 빠뜨리기

```
설정 변경 후 Deploy 안 하면 → 이전 버전으로 동작
반드시: Actions → Deploy API → 스테이지 선택 → Deploy
```

### 3. Lambda 응답 body는 반드시 string

```python
❌ "body": {"key": "value"}          # dict → 502 Bad Gateway
✅ "body": json.dumps({"key": "value"}) # string
```

### 4. CORS OPTIONS 메서드

```
Cognito Authorizer 연결 시:
→ OPTIONS 메서드는 Authorizer 없이 설정해야 CORS preflight 통과
→ 그렇지 않으면 브라우저에서 401 오류 발생
```

### 5. IdToken vs AccessToken

```
Cognito Authorizer (기본): IdToken 사용
AccessToken: aud claim 없음 → 검증 실패 가능
```

### 6. VPC Lambda와 인터넷

```
Lambda를 VPC에 넣으면 → 인터넷 차단
외부 호출 필요 시:
  - NAT Gateway (비용 발생)
  - VPC Endpoint (AWS 서비스 전용)
```

---

## ✅ 자주 나오는 구현 요구사항 체크리스트

- [ ] REST API, Regional Endpoint 생성
- [ ] Lambda Proxy Integration 체크
- [ ] CORS 헤더 응답에 포함
- [ ] `prod` 스테이지로 배포
- [ ] 환경변수로 DB 접속 정보 설정
- [ ] VPC + Private Subnet + SG 인바운드 3306 설정
- [ ] Cognito User Pool + App Client (Client Secret 없이)
- [ ] Authorizer 생성 + 메서드에 연결 + 재배포
- [ ] API Key + Usage Plan + 메서드 API Key Required 설정
- [ ] CRUD (GET / POST / PUT / PATCH / DELETE) 구현
- [ ] UUID 자동 발급, created_at/updated_at 자동 저장
- [ ] 필터 + 페이지네이션 (category, price_lt, price_gt, limit, offset)

---

## ✅ HTTP 상태 코드 정리

| 코드 | 의미 | 발생 상황 |
|------|------|-----------|
| 200 | OK | 조회/수정/삭제 성공 |
| 201 | Created | 생성 성공 |
| 400 | Bad Request | 필수 파라미터 누락, 잘못된 요청 |
| 401 | Unauthorized | Cognito 토큰 없음/만료 |
| 403 | Forbidden | API Key 없음/잘못됨 |
| 404 | Not Found | 해당 ID 없음 |
| 429 | Too Many Requests | 스로틀링 초과 |
| 500 | Internal Server Error | Lambda 코드 오류 |
| 502 | Bad Gateway | Lambda 응답 형식 오류 (body가 string 아님 등) |

---

## ✅ 용어 정리

| 용어 | 설명 |
|------|------|
| Resource | API 경로 (`/item`, `/item/{id}`) |
| Method | HTTP 동사 (GET, POST, ANY 등) |
| Integration | 백엔드 연결 방식 (Lambda, HTTP, Mock 등) |
| Stage | 배포 환경 단위 (`dev`, `prod`) |
| Authorizer | 요청 인증 처리 (Cognito, Lambda) |
| Usage Plan | API Key별 요청 한도/속도 제한 |
| Invoke URL | 배포된 API 호출 주소 |
| Lambda Proxy | 전체 HTTP 요청을 그대로 Lambda에 전달하는 통합 방식 |
| CORS | 브라우저의 교차 출처 요청 허용 정책 |
| Cold Start | Lambda 컨테이너 최초 실행 시 초기화 지연 |
