-- ============================================================
-- 1. 데이터베이스 생성
-- ============================================================

CREATE DATABASE IF NOT EXISTS wsi_db
  COMMENT 'WSI 2026 Query from S3';


-- ============================================================
-- 2. 외부 테이블 생성 — CSV
-- ============================================================

CREATE EXTERNAL TABLE IF NOT EXISTS wsi_db.wsi_table (
  id        INT,
  name      STRING,
  value     DOUBLE,
  region    STRING,
  created_at STRING
)
ROW FORMAT DELIMITED
  FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 's3://<bucket>/<prefix>/'
TBLPROPERTIES ('skip.header.line.count'='1');


-- ============================================================
-- 3. 외부 테이블 생성 — JSON
-- ============================================================

CREATE EXTERNAL TABLE IF NOT EXISTS wsi_db.wsi_table_json (
  id        INT,
  name      STRING,
  value     DOUBLE,
  region    STRING,
  created_at STRING
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
STORED AS TEXTFILE
LOCATION 's3://<bucket>/<prefix>/';


-- ============================================================
-- 4. 외부 테이블 생성 — Parquet
-- ============================================================

CREATE EXTERNAL TABLE IF NOT EXISTS wsi_db.wsi_table_parquet (
  id        INT,
  name      STRING,
  value     DOUBLE,
  region    STRING,
  created_at STRING
)
STORED AS PARQUET
LOCATION 's3://<bucket>/<prefix>/';


-- ============================================================
-- 5. 파티션 테이블 생성 — CSV (year/month/day)
-- ============================================================

CREATE EXTERNAL TABLE IF NOT EXISTS wsi_db.wsi_table_partitioned (
  id     INT,
  name   STRING,
  value  DOUBLE,
  region STRING
)
PARTITIONED BY (
  year  STRING,
  month STRING,
  day   STRING
)
ROW FORMAT DELIMITED
  FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 's3://<bucket>/<prefix>/'
TBLPROPERTIES ('skip.header.line.count'='1');

-- 파티션 수동 추가
ALTER TABLE wsi_db.wsi_table_partitioned
ADD PARTITION (year='2025', month='01', day='01')
LOCATION 's3://<bucket>/<prefix>/year=2025/month=01/day=01/';

-- 파티션 자동 감지 (S3 구조가 Hive 형식일 때)
MSCK REPAIR TABLE wsi_db.wsi_table_partitioned;


-- ============================================================
-- 6. CTAS — 쿼리 결과를 S3에 Parquet으로 저장
-- ============================================================

CREATE TABLE wsi_db.wsi_table_result
WITH (
  format            = 'PARQUET',
  external_location = 's3://<result-bucket>/<prefix>/',
  partitioned_by    = ARRAY['region']
)
AS
SELECT *
FROM wsi_db.wsi_table
WHERE value > 0;


-- ============================================================
-- 7. 외부 테이블 생성 — CSV (쉼표 포함 필드 대응 OpenCSVSerDe)
-- ============================================================
-- 필드 안에 쉼표가 들어있는 CSV (예: "Seoul, Korea") → OpenCSVSerDe 사용

CREATE EXTERNAL TABLE IF NOT EXISTS wsi_db.wsi_table_csv_quoted (
  id        INT,
  name      STRING,
  value     DOUBLE,
  region    STRING,
  created_at STRING
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES (
  "separatorChar" = ",",
  "quoteChar"     = "\"",
  "escapeChar"    = "\\"
)
STORED AS TEXTFILE
LOCATION 's3://<bucket>/<prefix>/'
TBLPROPERTIES ('skip.header.line.count'='1');


-- ============================================================
-- 8. 외부 테이블 생성 — ORC
-- ============================================================

CREATE EXTERNAL TABLE IF NOT EXISTS wsi_db.wsi_table_orc (
  id        INT,
  name      STRING,
  value     DOUBLE,
  region    STRING,
  created_at STRING
)
STORED AS ORC
LOCATION 's3://<bucket>/<prefix>/';


-- ============================================================
-- 9. 외부 테이블 생성 — TSV (탭 구분자)
-- ============================================================

CREATE EXTERNAL TABLE IF NOT EXISTS wsi_db.wsi_table_tsv (
  id        INT,
  name      STRING,
  value     DOUBLE,
  region    STRING,
  created_at STRING
)
ROW FORMAT DELIMITED
  FIELDS TERMINATED BY '\t'
STORED AS TEXTFILE
LOCATION 's3://<bucket>/<prefix>/'
TBLPROPERTIES ('skip.header.line.count'='1');


-- ============================================================
-- 10. 테이블 스키마 확인 / 삭제
-- ============================================================

-- 스키마 확인
DESCRIBE wsi_db.wsi_table;
DESCRIBE EXTENDED wsi_db.wsi_table;
SHOW TABLES IN wsi_db;
SHOW PARTITIONS wsi_db.wsi_table_partitioned;

-- 테이블 삭제 (외부 테이블은 S3 원본 데이터 유지됨)
DROP TABLE IF EXISTS wsi_db.wsi_table;
