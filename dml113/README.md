# dml113 — WSI 2026 2과제 예측 자료

## 폴더 구조

```
dml113/
├── problem2/          Query from S3  (Athena)
│   ├── README.md      개념 설명 + 세팅 순서
│   ├── setup.sh       S3·Glue·Athena CLI 세팅 명령어
│   ├── ddl.sql        테이블 생성 DDL (CSV·JSON·Parquet·파티션·CTAS)
│   └── queries.sql    자주 나오는 쿼리 패턴 모음
│
├── problem3/          Fine-grained IAM policy
│   ├── README.md      개념 설명 + 파일별 용도
│   ├── s3_abac.json            태그 기반 S3 접근 제어 (ABAC)
│   ├── ec2_tag_control.json    Owner 태그로 EC2 시작/중지 제한
│   ├── deny_conditions.json    리전·MFA·인스턴스 타입 Deny
│   ├── s3_bucket_policy.json   버킷 정책 (HTTPS 강제·VPC 전용·IP 제한)
│   ├── permission_boundary.json  권한 경계 (IAM 에스컬레이션 방지)
│   └── role_trust_policy.json  신뢰 정책 (EC2·Lambda·크로스계정)
│
└── problem4/          MySQL with Lambda
    ├── README.md      개념 설명 + 아키텍처·세팅 순서
    ├── init.sql       RDS MySQL DB·테이블 생성 + IAM 인증 유저
    └── lambda_function.py  Lambda Function URL + RDS Proxy CRUD
```
