# API Gateway

> AWS API Gateway + Lambda + RDS(MySQL) 연동 정리

## 목차

| 파일 | 내용 |
|------|------|
| [01_basic.md](./01_basic.md) | REST API 생성 + Lambda Proxy 기본 연동 |
| [02_cognito.md](./02_cognito.md) | Cognito Authorizer 연결 |
| [03_api_types.md](./03_api_types.md) | REST vs HTTP vs WebSocket API 비교 |
| [04_stages_and_deployment.md](./04_stages_and_deployment.md) | 스테이지, 배포, 카나리 배포 |
| [05_throttling_and_usage_plan.md](./05_throttling_and_usage_plan.md) | 스로틀링, Usage Plan, API Key |
| [06_lambda_functions.md](./06_lambda_functions.md) | Lambda 함수 구현 패턴 (function 1~6 요약) |
| [07_exam_tips.md](./07_exam_tips.md) | 과제/시험 빈출 포인트 |

---

## 아키텍처 흐름

```
Client
  │
  ▼
API Gateway (REST API)
  │  ├─ Cognito Authorizer (선택)
  │  ├─ API Key / Usage Plan (선택)
  │  └─ Resource + Method
  ▼
AWS Lambda
  │  ├─ VPC (RDS 접근 시)
  │  └─ Environment Variables
  ▼
RDS MySQL (Private Subnet)
```
