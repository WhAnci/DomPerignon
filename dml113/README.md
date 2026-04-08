# dml113 — WSI 2026 2과제 예측 자료

## 폴더 구조

```
dml113/
├── problem2/          Query from S3  (Athena)
│   ├── README.md      개념 설명 + 세팅 순서 + 트러블슈팅
│   ├── setup.sh       S3·Glue·Athena CLI 세팅 명령어
│   ├── ddl.sql        테이블 생성 DDL (CSV·OpenCSVSerDe·JSON·Parquet·ORC·TSV·파티션·CTAS)
│   ├── queries.sql    쿼리 패턴 모음 (CTE·서브쿼리·CASE WHEN·문자열·CAST·윈도우 등)
│   └── sample.csv     테스트용 샘플 데이터 (S3에 업로드해서 사용)
│
├── problem3/          Fine-grained IAM policy
│   ├── README.md      개념 설명 + 조건 키 표 + CLI 적용 방법
│   ├── s3_abac.json            태그 기반 S3 접근 제어 (ABAC, PrincipalTag)
│   ├── ec2_tag_control.json    Owner 태그로 EC2 시작/중지 제한
│   ├── deny_conditions.json    리전·MFA·인스턴스 타입 Deny
│   ├── s3_bucket_policy.json   버킷 정책 (HTTPS 강제·VPC 엔드포인트 전용·IP 제한)
│   ├── permission_boundary.json  권한 경계 (IAM 에스컬레이션 방지)
│   ├── role_trust_policy.json  신뢰 정책 (EC2·Lambda·크로스계정)
│   ├── lambda_role.json        Lambda 실행 역할 (VPC·CloudWatch·RDS·S3·Athena)
│   ├── secrets_manager.json    Secrets Manager 읽기 전용 + 로테이션 정책
│   └── scp_example.json        SCP (리전 제한·CloudTrail 보호·루트 계정 차단)
│
└── problem4/          MySQL with Lambda
    ├── README.md      개념 설명 + 아키텍처·세팅 순서 + curl 테스트
    ├── setup.sh       전체 인프라 자동 세팅 CLI (Secrets Manager → Proxy → Lambda → URL)
    ├── init.sql       RDS MySQL DB·테이블 생성 + 샘플 데이터 + IAM 인증 유저
    ├── lambda_role.json        Lambda 필요 최소 권한 (VPC·로그·RDS Proxy 연결)
    └── lambda_function.py     Lambda Function URL + RDS Proxy IAM 인증 + CRUD + 커넥션 재사용
```
