-- ============================================================
-- Athena 쿼리 모음 — wsi_db.wsi_table 기준
-- ============================================================


-- ── 전체 조회 ─────────────────────────────────────────────

SELECT * FROM wsi_db.wsi_table LIMIT 100;


-- ── 단건 조회 ─────────────────────────────────────────────

SELECT * FROM wsi_db.wsi_table
WHERE id = <id>;


-- ── 정렬 ──────────────────────────────────────────────────

-- 내림차순
SELECT * FROM wsi_db.wsi_table
ORDER BY value DESC
LIMIT 10;

-- 상위 N개
SELECT * FROM wsi_db.wsi_table
ORDER BY value DESC
LIMIT <n>;


-- ── 필터 ──────────────────────────────────────────────────

-- 같음
SELECT * FROM wsi_db.wsi_table
WHERE region = '<region>';

-- 범위
SELECT * FROM wsi_db.wsi_table
WHERE value BETWEEN <min> AND <max>;

-- 날짜 범위
SELECT * FROM wsi_db.wsi_table
WHERE created_at BETWEEN '<start_date>' AND '<end_date>';

-- 복수 값 (IN)
SELECT * FROM wsi_db.wsi_table
WHERE region IN ('<value1>', '<value2>', '<value3>');

-- NULL 처리
SELECT * FROM wsi_db.wsi_table WHERE <column> IS NULL;
SELECT * FROM wsi_db.wsi_table WHERE <column> IS NOT NULL;

-- 문자열 포함
SELECT * FROM wsi_db.wsi_table
WHERE name LIKE '%<keyword>%';


-- ── 집계 ──────────────────────────────────────────────────

-- 그룹별 COUNT / SUM / AVG
SELECT
  region,
  COUNT(*)       AS cnt,
  SUM(value)     AS total,
  AVG(value)     AS avg_val,
  MAX(value)     AS max_val,
  MIN(value)     AS min_val
FROM wsi_db.wsi_table
GROUP BY region
ORDER BY cnt DESC;

-- HAVING 필터
SELECT region, COUNT(*) AS cnt
FROM wsi_db.wsi_table
GROUP BY region
HAVING COUNT(*) >= <min_count>;


-- ── 윈도우 함수 ───────────────────────────────────────────

-- 그룹 내 순위
SELECT
  region,
  name,
  value,
  RANK() OVER (PARTITION BY region ORDER BY value DESC) AS rnk
FROM wsi_db.wsi_table;

-- 누적 합계
SELECT
  created_at,
  value,
  SUM(value) OVER (ORDER BY created_at) AS cumulative
FROM wsi_db.wsi_table;

-- 이전/다음 행 비교
SELECT
  id,
  value,
  LAG(value)  OVER (ORDER BY id) AS prev_value,
  LEAD(value) OVER (ORDER BY id) AS next_value
FROM wsi_db.wsi_table;


-- ── 날짜 함수 ─────────────────────────────────────────────

-- 최근 N일
SELECT * FROM wsi_db.wsi_table
WHERE created_at >= DATE_FORMAT(DATE_ADD('day', -<n>, CURRENT_DATE), '%Y-%m-%d');

-- 월별 집계
SELECT
  DATE_TRUNC('month', DATE(created_at)) AS month,
  COUNT(*) AS cnt
FROM wsi_db.wsi_table
GROUP BY DATE_TRUNC('month', DATE(created_at))
ORDER BY month;


-- ── 파티션 쿼리 (비용 절감) ───────────────────────────────

SELECT * FROM wsi_db.wsi_table_partitioned
WHERE year = '2025'
  AND month = '01'
  AND day = '01';


-- ── JSON 파싱 ─────────────────────────────────────────────

SELECT
  id,
  json_extract_scalar(<json_column>, '$.<key>') AS <alias>
FROM wsi_db.wsi_table;


-- ── 배열 펼치기 (UNNEST) ──────────────────────────────────

SELECT id, tag
FROM wsi_db.wsi_table
CROSS JOIN UNNEST(<array_column>) AS t(tag);


-- ── 복합 조건 ─────────────────────────────────────────────

SELECT *
FROM wsi_db.wsi_table
WHERE region = '<region>'
  AND value >= <min_value>
  AND (name LIKE '%<keyword1>%' OR name LIKE '%<keyword2>%')
ORDER BY value DESC
LIMIT <n>;


-- ── CTE (WITH 절) ─────────────────────────────────────────

-- 단순 CTE
WITH ranked AS (
  SELECT
    *,
    RANK() OVER (PARTITION BY region ORDER BY value DESC) AS rnk
  FROM wsi_db.wsi_table
)
SELECT * FROM ranked WHERE rnk <= 3;

-- 다중 CTE
WITH
  total AS (
    SELECT region, SUM(value) AS total_value
    FROM wsi_db.wsi_table
    GROUP BY region
  ),
  avg_all AS (
    SELECT AVG(value) AS avg_value
    FROM wsi_db.wsi_table
  )
SELECT t.region, t.total_value, a.avg_value
FROM total t
CROSS JOIN avg_all a
ORDER BY t.total_value DESC;


-- ── 서브쿼리 ──────────────────────────────────────────────

-- WHERE 절 서브쿼리 (평균 이상만 조회)
SELECT * FROM wsi_db.wsi_table
WHERE value > (SELECT AVG(value) FROM wsi_db.wsi_table);

-- IN 서브쿼리
SELECT * FROM wsi_db.wsi_table
WHERE region IN (
  SELECT region FROM wsi_db.wsi_table
  GROUP BY region
  HAVING COUNT(*) >= <min_count>
);

-- FROM 절 인라인 뷰
SELECT region, max_val
FROM (
  SELECT region, MAX(value) AS max_val
  FROM wsi_db.wsi_table
  GROUP BY region
) t
WHERE max_val > <threshold>;


-- ── CASE WHEN ─────────────────────────────────────────────

-- 값 분류
SELECT
  id,
  name,
  value,
  CASE
    WHEN value >= 1000 THEN 'high'
    WHEN value >= 500  THEN 'mid'
    ELSE 'low'
  END AS grade
FROM wsi_db.wsi_table;

-- 조건별 집계 (PIVOT 대용)
SELECT
  COUNT(CASE WHEN region = 'Seoul'  THEN 1 END) AS seoul_cnt,
  COUNT(CASE WHEN region = 'Busan'  THEN 1 END) AS busan_cnt,
  COUNT(CASE WHEN region = 'Daegu'  THEN 1 END) AS daegu_cnt,
  SUM(CASE WHEN region = 'Seoul'    THEN value ELSE 0 END) AS seoul_total
FROM wsi_db.wsi_table;


-- ── 문자열 함수 ───────────────────────────────────────────

SELECT
  id,
  name,
  LOWER(name)                          AS name_lower,
  UPPER(name)                          AS name_upper,
  LENGTH(name)                         AS name_len,
  SUBSTR(name, 1, 3)                   AS name_prefix,
  REPLACE(name, '<old>', '<new>')      AS name_replaced,
  TRIM(name)                           AS name_trimmed,
  SPLIT_PART(name, '-', 1)             AS name_part1,   -- 구분자로 분리 후 N번째
  CONCAT(name, '-', CAST(id AS VARCHAR)) AS name_with_id,
  REGEXP_REPLACE(name, '[^a-zA-Z0-9]', '') AS name_clean
FROM wsi_db.wsi_table;


-- ── CAST / 타입 변환 ──────────────────────────────────────

SELECT
  CAST(id AS VARCHAR)            AS id_str,
  CAST('123' AS INT)             AS str_to_int,
  CAST(value AS INT)             AS value_int,
  CAST(created_at AS DATE)       AS created_date,
  CAST(created_at AS TIMESTAMP)  AS created_ts,
  DATE_FORMAT(DATE(created_at), '%Y-%m') AS year_month
FROM wsi_db.wsi_table;


-- ── DISTINCT / 중복 제거 ───────────────────────────────────

SELECT DISTINCT region FROM wsi_db.wsi_table;

SELECT COUNT(DISTINCT region) AS unique_regions FROM wsi_db.wsi_table;


-- ── COALESCE / NULL 대체 ───────────────────────────────────

SELECT
  id,
  COALESCE(name, 'unknown')    AS name,
  COALESCE(value, 0)           AS value,
  NULLIF(value, 0)             AS value_no_zero   -- 0이면 NULL로
FROM wsi_db.wsi_table;


-- ── 숫자 함수 ─────────────────────────────────────────────

SELECT
  id,
  value,
  ROUND(value, 2)              AS value_rounded,
  CEIL(value)                  AS value_ceil,
  FLOOR(value)                 AS value_floor,
  ABS(value)                   AS value_abs,
  MOD(id, 2)                   AS is_even          -- 0이면 짝수
FROM wsi_db.wsi_table;
