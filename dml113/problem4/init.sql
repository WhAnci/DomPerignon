-- ============================================================
-- Problem 4 — RDS MySQL 초기 세팅
-- ============================================================

-- ── 1. 데이터베이스 생성 ──────────────────────────────────────

CREATE DATABASE IF NOT EXISTS wsi_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE wsi_db;

-- ── 2. 테이블 생성 ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS item (
  id         INT          NOT NULL AUTO_INCREMENT,
  name       VARCHAR(100) NOT NULL,
  value      DOUBLE,
  created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  INDEX idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── 3. 샘플 데이터 삽입 ───────────────────────────────────────

INSERT INTO item (name, value) VALUES
  ('item-a', 100.0),
  ('item-b', 200.5),
  ('item-c', 300.75);

-- ── 4. Lambda IAM 인증용 DB 유저 생성 ────────────────────────
-- RDS Proxy IAM 인증 사용 시 해당 유저에 AWSAuthenticationPlugin 적용

CREATE USER IF NOT EXISTS '<db-user>'@'%'
  IDENTIFIED WITH AWSAuthenticationPlugin AS 'RDS';

GRANT SELECT, INSERT, UPDATE, DELETE ON wsi_db.* TO '<db-user>'@'%';

FLUSH PRIVILEGES;

-- ── 5. 확인 쿼리 ──────────────────────────────────────────────

SHOW TABLES;
SELECT * FROM item;
SELECT user, host, plugin FROM mysql.user WHERE user = '<db-user>';
