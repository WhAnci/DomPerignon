# Problem 3 — Fine-grained IAM policy

## 개념 이해

### IAM 정책 종류

```
IAM 정책
├── Identity-based policy   — 사용자·역할에 붙이는 정책 (누가 뭘 할 수 있나)
├── Resource-based policy   — 리소스(S3 버킷 등)에 붙이는 정책 (누가 이 리소스에 접근할 수 있나)
└── Permission boundary     — 역할/사용자에게 부여 가능한 최대 권한 상한선
```

### 정책 평가 순서

```
명시적 Deny → 명시적 Allow → 암묵적 Deny (기본 거부)
```

Deny가 하나라도 있으면 Allow가 있어도 막힘

### ABAC (Attribute-Based Access Control)

태그를 조건으로 쓰는 접근 제어 방식

```
사용자 태그 (PrincipalTag)  ←→  리소스 태그 (ResourceTag)
예) 사용자의 Department=dev  →  dev 태그 붙은 리소스만 접근 허용
```

---

## 파일 설명

| 파일 | 용도 |
|------|------|
| `s3_abac.json` | 사용자의 Department 태그와 S3 경로를 일치시켜 접근 제어 |
| `ec2_tag_control.json` | Owner 태그가 자신인 EC2만 시작·중지 가능, dev/test 환경만 삭제 허용 |
| `deny_conditions.json` | 특정 리전 외 차단, MFA 없으면 민감 작업 차단, 인스턴스 타입 제한 |
| `s3_bucket_policy.json` | 버킷에 직접 붙이는 정책 — HTTPS 강제, VPC 엔드포인트 전용, IP 허용 |
| `permission_boundary.json` | 역할에 부여 가능한 최대 권한 상한. S3·Lambda 허용, IAM 변경은 차단 |
| `role_trust_policy.json` | 역할을 Assume할 수 있는 주체 정의 (EC2·Lambda·크로스계정) |

---

## 자주 나오는 조건 키

| 조건 키 | 설명 | 예시 |
|---------|------|------|
| `aws:PrincipalTag/<key>` | 요청자(사용자·역할)의 태그 | `aws:PrincipalTag/Department` |
| `aws:ResourceTag/<key>` | 대상 리소스의 태그 | `ec2:ResourceTag/Owner` |
| `aws:RequestedRegion` | 요청된 AWS 리전 | `ap-northeast-2` |
| `aws:MultiFactorAuthPresent` | MFA 인증 여부 | `true` / `false` |
| `aws:SecureTransport` | HTTPS 여부 | `true` / `false` |
| `aws:SourceIp` | 요청 IP 주소 | `1.2.3.4/32` |
| `aws:SourceVpce` | VPC 엔드포인트 ID | `vpce-xxxxxx` |
| `aws:username` | IAM 사용자명 | `${aws:username}` (변수) |
| `ec2:InstanceType` | EC2 인스턴스 타입 | `t3.micro` |
| `s3:prefix` | S3 경로 prefix | `data/` |

---

## 정책 적용 방법 (CLI)

```bash
# IAM 역할 생성
aws iam create-role \
  --role-name <role-name> \
  --assume-role-policy-document file://role_trust_policy.json

# 인라인 정책 추가
aws iam put-role-policy \
  --role-name <role-name> \
  --policy-name <policy-name> \
  --policy-document file://s3_abac.json

# 권한 경계 설정
aws iam put-role-permissions-boundary \
  --role-name <role-name> \
  --permissions-boundary arn:aws:iam::<account-id>:policy/<boundary-policy-name>

# S3 버킷 정책 적용
aws s3api put-bucket-policy \
  --bucket <bucket-name> \
  --policy file://s3_bucket_policy.json
```

---

## 자주 나오는 포인트

| 상황 | 해결 |
|------|------|
| Allow 줬는데 접근 거부됨 | 상위 SCP나 Permission Boundary에 Deny 있는지 확인 |
| 태그 조건이 안 먹힘 | 리소스에 태그가 실제로 붙어 있는지 확인 |
| `${aws:username}` 변수 안 됨 | 정책 변수는 `"` 안에서 `${}` 형식으로 사용, IAM 사용자에만 동작 |
| 크로스계정 역할 Assume 실패 | 신뢰 정책(Trust Policy)에 상대 계정 ARN 추가됐는지 확인 |
