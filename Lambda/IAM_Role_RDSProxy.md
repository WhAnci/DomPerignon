# IAM Role — Lambda + RDS Proxy

> Lambda 함수가 RDS Proxy를 통해 RDS에 접근할 때 필요한 IAM Role 정리

---

## 1. 구조 한눈에 보기

```
Lambda 함수
  └── Execution Role
        ├── AWSLambdaBasicExecutionRole   → CloudWatch Logs
        ├── AWSLambdaVPCAccessExecutionRole → VPC ENI 생성/삭제
        └── 인라인 정책
              └── rds-db:connect          → RDS Proxy IAM 인증 (선택)
```

> RDS Proxy는 두 가지 인증 방식을 지원합니다.
> - **사용자/비밀번호 인증** (os.getenv / Secrets Manager) — 이 파일의 기본 방식
> - **IAM 인증** — `rds-db:connect` 권한 추가 필요

---

## 2. 기본 Role (사용자/비밀번호 인증)

### Trust Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

### Permission Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Sid": "VPCAccess",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateNetworkInterface",
        "ec2:DescribeNetworkInterfaces",
        "ec2:DeleteNetworkInterface"
      ],
      "Resource": "*"
    }
  ]
}
```

> 관리형 정책으로 대체 가능:
> - `arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole`
> - `arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole`

---

## 3. Secrets Manager 추가 시 (선택)

`lambda_rds_proxy.py` 의 Secrets Manager 주석을 해제한 경우 아래 Sid 추가.

```json
{
  "Sid": "SecretsManagerRead",
  "Effect": "Allow",
  "Action": [
    "secretsmanager:GetSecretValue",
    "secretsmanager:DescribeSecret"
  ],
  "Resource": "arn:aws:secretsmanager:ap-northeast-2:<ACCOUNT_ID>:secret:prod/myapp/mysql-*"
}
```

---

## 4. RDS Proxy IAM 인증 추가 시 (선택)

os.getenv 방식 대신 IAM 토큰으로 Proxy에 접근할 때 아래 Sid 추가.

```json
{
  "Sid": "RDSProxyConnect",
  "Effect": "Allow",
  "Action": "rds-db:connect",
  "Resource": "arn:aws:rds-db:ap-northeast-2:<ACCOUNT_ID>:dbuser:<PROXY_RESOURCE_ID>/<DB_USER>"
}
```

> `PROXY_RESOURCE_ID`는 RDS 콘솔 → Proxies → Proxy ARN 에서 확인

---

## 5. 전체 통합 Policy (참고용)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Sid": "VPCAccess",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateNetworkInterface",
        "ec2:DescribeNetworkInterfaces",
        "ec2:DeleteNetworkInterface"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SecretsManagerRead",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:ap-northeast-2:<ACCOUNT_ID>:secret:prod/myapp/mysql-*"
    },
    {
      "Sid": "RDSProxyConnect",
      "Effect": "Allow",
      "Action": "rds-db:connect",
      "Resource": "arn:aws:rds-db:ap-northeast-2:<ACCOUNT_ID>:dbuser:<PROXY_RESOURCE_ID>/<DB_USER>"
    }
  ]
}
```

---

## 6. Security Group 설정

| 방향 | 소스 | 포트 | 설명 |
|------|------|------|------|
| Lambda SG → RDS Proxy SG | Lambda SG ID | 3306 | Lambda → Proxy 접근 |
| RDS Proxy SG → RDS SG | Proxy SG ID | 3306 | Proxy → RDS 접근 |

> Lambda SG가 직접 RDS SG에 접근할 필요 없음. Proxy가 중간에서 관리.

---

## 7. 환경변수 설정

| Key | Value | 설명 |
|-----|-------|------|
| `RDS_HOST` | `xxxx.proxy-xxx.ap-northeast-2.rds.amazonaws.com` | RDS Proxy 엔드포인트 |
| `RDS_PORT` | `3306` | 포트 |
| `RDS_USER` | `admin` | DB 사용자명 |
| `RDS_PASSWORD` | `yourpassword` | DB 비밀번호 |
| `RDS_DB` | `mydb` | 데이터베이스 이름 |
| `HEALTH_CHECK_INTERVAL` | `60` | 헬스체크 주기 (초, 기본 60) |

> Secrets Manager 사용 시 `RDS_*` 대신 `SECRET_ID` 하나만 설정.

---

## 8. 체크리스트

- [ ] Lambda를 RDS Proxy와 **동일한 VPC + Private Subnet** 에 배치
- [ ] Lambda SG → Proxy SG 3306 인바운드 허용
- [ ] Proxy SG → RDS SG 3306 인바운드 허용
- [ ] `AWSLambdaVPCAccessExecutionRole` 부착
- [ ] RDS Proxy 생성 시 **Secrets Manager에 DB 자격 증명 등록** 필수
- [ ] Lambda 환경변수 `RDS_HOST`에 **Proxy 엔드포인트** 입력 (RDS 직접 엔드포인트 X)
- [ ] Function URL 사용 시 Auth Type 설정 확인 (`NONE` 또는 `AWS_IAM`)
