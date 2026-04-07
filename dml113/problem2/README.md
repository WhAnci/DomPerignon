# Problem 2 — Query from S3

## 개념 이해

### S3 / Glue / Athena 관계

```
S3 (데이터 저장)
  └── Glue Data Catalog (테이블 정의 — "이 S3 경로의 데이터는 이런 컬럼 구조다")
        └── Athena (SQL로 S3 데이터 쿼리)
```

- **S3** : 실제 CSV·JSON·Parquet 파일이 저장되는 곳. DB가 아니라 그냥 파일 저장소
- **Glue Data Catalog** : 스키마 정보(컬럼명·타입)를 저장하는 메타데이터 저장소. Athena가 "이 S3 경로가 어떤 형식인지" 알려면 반드시 필요
- **Athena** : Glue 카탈로그를 보고 S3 파일을 SQL로 읽어오는 쿼리 엔진. 서버 없이 쿼리당 과금

---

## 파일 설명

| 파일 | 용도 |
|------|------|
| `setup.sh` | S3 버킷·Glue DB·Athena 워크그룹 생성 CLI 명령어 |
| `ddl.sql` | Glue 테이블 생성 DDL (CREATE EXTERNAL TABLE) |
| `queries.sql` | 조회·필터·집계·윈도우 함수 등 쿼리 패턴 모음 |

---

## 세팅 순서

### 1단계 — S3 버킷 생성 및 데이터 업로드

```bash
# 데이터 버킷 생성
aws s3 mb s3://<bucket-name> --region ap-northeast-2

# 쿼리 결과 버킷 생성 (Athena 결과 저장용)
aws s3 mb s3://<result-bucket-name> --region ap-northeast-2

# CSV 파일 업로드
aws s3 cp data.csv s3://<bucket-name>/data/
```

> CSV 첫 줄은 헤더 행. `ddl.sql`에서 `skip.header.line.count=1` 옵션으로 처리

### 2단계 — Glue 데이터베이스 생성

```bash
aws glue create-database \
  --region ap-northeast-2 \
  --database-input '{"Name": "wsi_db"}'
```

### 3단계 — Athena 워크그룹 생성

```bash
aws athena create-work-group \
  --name wsi-workgroup \
  --configuration '{
    "ResultConfiguration": {
      "OutputLocation": "s3://<result-bucket-name>/results/"
    }
  }'
```

> 워크그룹은 쿼리 결과를 저장할 S3 경로를 지정하는 단위. 없으면 쿼리 실행 불가

### 4단계 — 외부 테이블 생성 (ddl.sql 실행)

Athena 콘솔 또는 CLI에서 `ddl.sql`의 `CREATE EXTERNAL TABLE` 구문 실행

```bash
# CLI로 실행
aws athena start-query-execution \
  --region ap-northeast-2 \
  --work-group wsi-workgroup \
  --query-string "CREATE EXTERNAL TABLE IF NOT EXISTS wsi_db.wsi_table ..." \
  --query-execution-context 'Database=wsi_db'
```

> **외부 테이블(EXTERNAL TABLE)** : 테이블을 삭제해도 S3 원본 데이터는 삭제되지 않음. Athena는 항상 EXTERNAL TABLE 사용

### 5단계 — 쿼리 실행

```bash
# 전체 조회
aws athena start-query-execution \
  --region ap-northeast-2 \
  --work-group wsi-workgroup \
  --query-string "SELECT * FROM wsi_db.wsi_table LIMIT 10" \
  --query-execution-context 'Database=wsi_db' \
  --query 'QueryExecutionId' --output text
```

```bash
# 결과 조회
aws athena get-query-results \
  --region ap-northeast-2 \
  --query-execution-id <QueryExecutionId>
```

---

## 자주 나오는 포인트

| 상황 | 해결 |
|------|------|
| 쿼리 결과가 안 나옴 | S3 경로 끝에 `/` 빠졌는지 확인 (`LOCATION 's3://버킷/prefix/'`) |
| 헤더가 데이터로 조회됨 | `TBLPROPERTIES ('skip.header.line.count'='1')` 추가 |
| 파티션 데이터가 조회 안 됨 | `MSCK REPAIR TABLE 테이블명` 실행 후 재조회 |
| 비용 줄이기 | 파티션 컬럼(`year/month/day`)으로 WHERE 절 필터링 |
| CSV 쉼표 안에 쉼표 포함 | LazySimpleSerDe 대신 OpenCSVSerDe 사용 |
