# Athena Query Templates

> AWS Athena (Presto SQL 기반) 쿼리 패턴 모음

---

## 📁 목차

- [정렬](#정렬)
- [필터](#필터)
- [집계](#집계)
- [NULL 처리](#null-처리)
- [문자열 검색](#문자열-검색)
- [복합 조건](#복합-조건)
- [Athena 특화 쿼리](#athena-특화-쿼리)

---

## 정렬

### 기본 오름차순 / 내림차순

```sql
-- 오름차순 (ASC)
SELECT *
FROM {table}
ORDER BY {column} ASC;

-- 내림차순 (DESC)
SELECT *
FROM {table}
ORDER BY {column} DESC;
```

> 예) `{column}` = `salary`, `age`, `score`

---

### 특정 값 순서대로 정렬 (CASE WHEN 정렬)

```sql
SELECT *
FROM {table}
ORDER BY
  CASE {column}
    WHEN '{value1}' THEN 1
    WHEN '{value2}' THEN 2
    WHEN '{value3}' THEN 3
    ELSE 4
  END;
```

> 예) `{column}` = `region`, `{value1~3}` = `Seoul`, `Busan`, `Daegu`

---

## 필터

### 비교 연산자 (이상 / 이하 / 초과 / 미만)

```sql
SELECT *
FROM {table}
WHERE {column} >= {value};
-- >= 이상 / <= 이하 / > 초과 / < 미만
```

> 예) `{column}` = `hire_date`, `{value}` = `DATE '2023-03-14'`

---

### 날짜 범위 필터 (BETWEEN)

```sql
SELECT *
FROM {table}
WHERE {date_column} BETWEEN DATE '{start_date}' AND DATE '{end_date}';
```

> 예) `{date_column}` = `created_at`, 범위 = `2024-01-01` ~ `2024-12-31`

---

### 특정 값 목록 필터 (IN)

```sql
SELECT *
FROM {table}
WHERE {column} IN ('{value1}', '{value2}', '{value3}');
```

> 예) `{column}` = `department`, 값 = `'HR'`, `'Dev'`, `'Sales'`

---

### 상위 N개 조회 (LIMIT)

```sql
SELECT *
FROM {table}
ORDER BY {column} DESC
LIMIT {n};
```

> 예) 연봉 상위 10명: `{column}` = `salary`, `{n}` = `10`

---

## 집계

### 그룹별 집계 (GROUP BY)

```sql
SELECT
  {group_column},
  COUNT(*)        AS cnt,
  SUM({col})      AS total,
  AVG({col})      AS avg_val,
  MAX({col})      AS max_val,
  MIN({col})      AS min_val
FROM {table}
GROUP BY {group_column}
ORDER BY cnt DESC;
```

> 예) `{group_column}` = `region`, `{col}` = `salary`

---

### 그룹 집계 결과 필터 (HAVING)

```sql
SELECT {group_column}, COUNT(*) AS cnt
FROM {table}
GROUP BY {group_column}
HAVING COUNT(*) >= {min_count};
```

> 예) 직원 수가 `{min_count}`명 이상인 부서만 출력

---

## NULL 처리

### NULL 포함 / 제외 조회

```sql
-- NULL인 데이터
SELECT *
FROM {table}
WHERE {column} IS NULL;

-- NULL이 아닌 데이터
SELECT *
FROM {table}
WHERE {column} IS NOT NULL;
```

> 예) `{column}` = `phone_number`, `email`

---

### NULL 대체값 처리 (COALESCE)

```sql
SELECT
  {column1},
  COALESCE({nullable_column}, '{default_value}') AS {alias}
FROM {table};
```

> 예) null인 `phone_number`를 `'N/A'`로 대체

---

## 문자열 검색

### 패턴 검색 (LIKE)

```sql
SELECT *
FROM {table}
WHERE {column} LIKE '%{keyword}%';
-- 접두사: '{keyword}%' / 접미사: '%{keyword}'
```

> 예) `{column}` = `name`, `{keyword}` = `김`

---

### 정규식 검색 (REGEXP_LIKE)

```sql
SELECT *
FROM {table}
WHERE REGEXP_LIKE({column}, '{pattern}');
```

> 예) 이메일 형식 검증: `REGEXP_LIKE(email, '^[^@]+@[^@]+\.[^@]+$')`

---

## 복합 조건

### AND / OR 복합 조건

```sql
SELECT *
FROM {table}
WHERE {column1} = '{value1}'
  AND {column2} >= {value2}
  AND ({column3} = '{value3a}' OR {column3} = '{value3b}');
```

> 예) 지역이 서울이고 연봉이 5000만 이상이며 부서가 Dev 또는 HR

---

## Athena 특화 쿼리

### S3 파티션 필터링 (파티션 프루닝)

```sql
SELECT *
FROM {database}.{table}
WHERE year = '{yyyy}'
  AND month = '{mm}'
  AND day = '{dd}';
```

> Athena는 파티션 컬럼 필터 시 스캔 범위를 줄여 비용 절감 가능

---

### JSON 컬럼 파싱 (json_extract_scalar)

```sql
SELECT
  id,
  json_extract_scalar({json_column}, '$.{key}') AS {alias}
FROM {table};
```

> 예) `{json_column}` = `payload`, `{key}` = `user_id`

---

### 배열 컬럼 UNNEST (배열 펼치기)

```sql
SELECT id, tag
FROM {table}
CROSS JOIN UNNEST({array_column}) AS t(tag);
```

> 예) `tags` 배열 컬럼을 행 단위로 펼쳐서 조회

---

### 윈도우 함수 (순위 / 누적합)

```sql
-- 그룹 내 순위
SELECT
  {group_column},
  {value_column},
  RANK() OVER (PARTITION BY {group_column} ORDER BY {value_column} DESC) AS rnk
FROM {table};

-- 누적 합계
SELECT
  {date_column},
  {value_column},
  SUM({value_column}) OVER (ORDER BY {date_column}) AS cumulative_sum
FROM {table};
```

---

### 특정 기간 데이터 집계 (date_diff / date_trunc)

```sql
-- 최근 N일 데이터
SELECT *
FROM {table}
WHERE {date_column} >= DATE_ADD('day', -{n}, CURRENT_DATE);

-- 월별 집계
SELECT
  DATE_TRUNC('month', {date_column}) AS month,
  COUNT(*) AS cnt
FROM {table}
GROUP BY DATE_TRUNC('month', {date_column})
ORDER BY month;
```

---

### CTAS (결과를 S3에 저장)

```sql
CREATE TABLE {new_table}
WITH (
  format = 'PARQUET',
  external_location = 's3://{bucket}/{prefix}/',
  partitioned_by = ARRAY['{partition_col}']
)
AS
SELECT *
FROM {source_table}
WHERE {condition};
```

> 쿼리 결과를 S3에 Parquet 형식으로 저장하여 재사용 가능
