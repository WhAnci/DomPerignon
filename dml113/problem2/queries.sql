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
