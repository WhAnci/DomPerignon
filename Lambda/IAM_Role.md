# Lambda IAM Role 가이드

> Lambda 함수에 붙이는 **실행 역할(Execution Role)** 을 목적별로 정리합니다.
> 모든 Role 은 AWS 관리형 정책 `AWSLambdaBasicExecutionRole` (CloudWatch Logs 쓰기) 을 기본으로 포함합니다.

---

## 1. 기본 구조

```
Lambda 함수
  └── Execution Role (IAM Role)
        ├── Trust Policy   → lambda.amazonaws.com 이 Assume 가능하도록 설정
        └── Permission Policy → 함수가 호출할 AWS 서비스 권한
```

### Trust Policy (공통)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

---

## 2. 목적별 IAM Role

### 2-1. 기본 Role (CloudWatch Logs 만)

> 외부 서비스를 호출하지 않는 단순 함수에 사용합니다.

**필요 정책**

| 정책 | 설명 |
|------|------|
| `AWSLambdaBasicExecutionRole` (AWS 관리형) | CloudWatch Logs 에 로그 생성/기록 |

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

---

### 2-2. RDS (VPC 내부 접근) Role

> Lambda → RDS MySQL/PostgreSQL 직접 연결 시 사용합니다.
> Lambda 를 RDS 와 같은 VPC 에 배치하고 Security Group 인바운드 규칙도 함께 설정해야 합니다.

**필요 정책**

| 정책 | 설명 |
|------|------|
| `AWSLambdaBasicExecutionRole` | CloudWatch Logs |
| `AWSLambdaVPCAccessExecutionRole` (AWS 관리형) | VPC ENI 생성/삭제 권한 |

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
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

> ⚠️ RDS 자체에는 IAM 권한이 필요 없습니다. VPC/Security Group 설정이 핵심입니다.

---

### 2-3. Secrets Manager Role

> `boto3.client('secretsmanager')` 로 DB 비밀번호 등 시크릿 값을 가져올 때 사용합니다.
> 환경 변수에 평문 비밀번호를 넣지 않아도 됩니다.

**필요 정책**

| 정책 | 설명 |
|------|------|
| `AWSLambdaBasicExecutionRole` | CloudWatch Logs |
| 인라인 정책 (아래) | 특정 Secret ARN 읽기 |

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:ap-northeast-2:<ACCOUNT_ID>:secret:prod/myapp/mysql-*"
    }
  ]
}
```

> 💡 `Resource` 에 `*` 대신 특정 Secret ARN(또는 접두사+와일드카드)을 지정하는 것이 최소 권한 원칙에 맞습니다.

---

### 2-4. RDS + Secrets Manager 통합 Role

> VPC 내 RDS 에 접근하면서 Secrets Manager 로 자격 증명을 관리하는 가장 일반적인 패턴입니다.

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
    }
  ]
}
```

---

### 2-5. S3 접근 Role

> Lambda 에서 S3 버킷에 파일을 읽거나 쓸 때 사용합니다.

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
      "Sid": "S3ReadWrite",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::<BUCKET_NAME>/*"
    },
    {
      "Sid": "S3ListBucket",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::<BUCKET_NAME>"
    }
  ]
}
```

---

### 2-6. DynamoDB 접근 Role

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
      "Sid": "DynamoDBCRUD",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": "arn:aws:dynamodb:ap-northeast-2:<ACCOUNT_ID>:table/<TABLE_NAME>"
    }
  ]
}
```

---

### 2-7. SQS / SNS 연동 Role

> Lambda 가 SQS 큐를 폴링하거나 SNS 토픽에 발행할 때 사용합니다.

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
      "Sid": "SQSConsume",
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "arn:aws:sqs:ap-northeast-2:<ACCOUNT_ID>:<QUEUE_NAME>"
    },
    {
      "Sid": "SNSPublish",
      "Effect": "Allow",
      "Action": "sns:Publish",
      "Resource": "arn:aws:sns:ap-northeast-2:<ACCOUNT_ID>:<TOPIC_NAME>"
    }
  ]
}
```

---

## 3. Terraform 예시 (RDS + Secrets Manager)

```hcl
resource "aws_iam_role" "lambda_exec" {
  name = "lambda-rds-secrets-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "basic_exec" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "vpc_access" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "secrets_read" {
  name = "secrets-manager-read"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ]
      Resource = "arn:aws:secretsmanager:ap-northeast-2:${var.account_id}:secret:prod/myapp/mysql-*"
    }]
  })
}
```

---

## 4. 체크리스트

- [ ] Trust Policy 에 `lambda.amazonaws.com` 이 Assume 가능하도록 설정
- [ ] `AWSLambdaBasicExecutionRole` 기본 부착 (CloudWatch Logs)
- [ ] VPC 배치 시 `AWSLambdaVPCAccessExecutionRole` 추가
- [ ] Secrets Manager 사용 시 `secretsmanager:GetSecretValue` 권한 추가
- [ ] `Resource` 는 `*` 대신 특정 ARN 으로 최소 권한 원칙 준수
- [ ] 환경 변수에 평문 비밀번호 절대 금지 → Secrets Manager 사용
