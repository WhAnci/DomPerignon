# 04. 스테이지 & 배포

## 스테이지(Stage)란?

- 배포된 API의 **버전/환경 단위** (예: `dev`, `staging`, `prod`)
- 스테이지마다 **Invoke URL이 다름**
- 스테이지별로 변수(Stage Variables) 설정 가능

---

## 배포 절차

```
API 변경 → Actions → Deploy API → 스테이지 선택 → Deploy
```

> ⚠️ **배포하지 않으면 변경사항이 적용되지 않음** (가장 흔한 실수)

---

## Stage Variables

스테이지별로 다른 Lambda 함수 또는 설정값을 사용할 수 있음.

```
# 스테이지 변수 설정 예시
stageVariables.lambdaAlias = prod

# 메서드 통합에서 참조
arn:aws:lambda:...:function:myFunction:${stageVariables.lambdaAlias}
```

---

## 카나리 배포 (Canary Deployment)

- 트래픽 일부(예: 10%)를 새 버전으로 라우팅 → 점진적 전환
- Stage → Canary 탭에서 설정

```
기존 배포: 90% 트래픽
카나리:    10% 트래픽 (새 버전)

→ 문제 없으면 Promote Canary로 100% 전환
→ 문제 있으면 Delete Canary로 롤백
```

---

## 캐싱 (Response Caching)

- Stage → Settings → Enable API Cache
- TTL 기본: 300초
- 캐싱 키: 기본은 메서드 + 경로. Query Parameter 포함 가능

```
캐싱 ON: 동일 요청 반복 시 Lambda 미호출 → 비용 절감
캐싱 OFF: 모든 요청 Lambda 호출
```

> ⚠️ 캐싱은 유료 기능 (캐시 크기에 따라 과금)
