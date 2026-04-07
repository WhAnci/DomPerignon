# 03. API 유형 비교 (REST vs HTTP vs WebSocket)

## API Gateway 제공 API 유형

| 항목 | REST API | HTTP API | WebSocket API |
|------|----------|----------|--------------|
| 프로토콜 | HTTP/HTTPS | HTTP/HTTPS | WebSocket |
| 통신 방향 | 단방향 (요청-응답) | 단방향 (요청-응답) | **양방향** |
| 비용 | 높음 | **낮음 (REST의 ~70%)** | 중간 |
| 기능 | 풍부 (캐싱, API Key, Usage Plan 등) | 기본 | 연결 관리 |
| 권장 사용처 | 일반 CRUD API | 저비용 간단 API | 채팅, 실시간 알림 |
| Lambda Proxy | ✅ | ✅ | ✅ (라우트 키 방식) |
| Cognito Authorizer | ✅ | ✅ (JWT Authorizer) | ✅ |
| 캐싱 | ✅ | ❌ | ❌ |
| Usage Plan / API Key | ✅ | ❌ | ❌ |

---

## 과제에서 주로 쓰는 것

> 대부분의 과제에서 **REST API** 사용 요구
> - CRUD 구현 + Cognito 인증 + Usage Plan 조합

---

## REST API Endpoint Type 선택 기준

| Endpoint Type | 설명 | 사용 시기 |
|--------------|------|-----------|
| Regional | 같은 리전 최적화 | 일반적인 경우 (기본값) |
| Edge-Optimized | CloudFront 경유 | 글로벌 사용자 분산 필요 |
| Private | VPC 내부 전용 | 인터넷 노출 금지 API |
