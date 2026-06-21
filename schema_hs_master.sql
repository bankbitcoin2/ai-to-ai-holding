-- schema_hs_master.sql
-- ตาราง HS Code Master Data + FTA Eligibility
-- รัน: ครั้งเดียวบน Railway PostgreSQL Console

-- ── HS Code Master (8-digit, TH + EN descriptions) ──────────────────────────
CREATE TABLE IF NOT EXISTS hs_code_master (
    hs_code      VARCHAR(12)  PRIMARY KEY,   -- e.g. "01012100"
    desc_th      TEXT,
    desc_en      TEXT,
    chapter      CHAR(2)      GENERATED ALWAYS AS (LEFT(TRIM(hs_code), 2)) STORED,
    source       VARCHAR(50)  DEFAULT 'AHTN2022',
    created_at   TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hs_master_chapter ON hs_code_master(chapter);
CREATE INDEX IF NOT EXISTS idx_hs_master_desc_th ON hs_code_master USING gin(to_tsvector('simple', COALESCE(desc_th,'')));
CREATE INDEX IF NOT EXISTS idx_hs_master_desc_en ON hs_code_master USING gin(to_tsvector('simple', COALESCE(desc_en,'')));

-- ── FTA Eligibility (HS code × country → FTA Form) ───────────────────────────
CREATE TABLE IF NOT EXISTS fta_eligibility (
    hs_code      VARCHAR(12)  NOT NULL,
    country_code CHAR(2)      NOT NULL,
    fta_form     VARCHAR(60)  NOT NULL,
    source       VARCHAR(50)  DEFAULT 'ThaiCustoms2022',
    PRIMARY KEY (hs_code, country_code)
);

CREATE INDEX IF NOT EXISTS idx_fta_hs      ON fta_eligibility(hs_code);
CREATE INDEX IF NOT EXISTS idx_fta_country ON fta_eligibility(country_code);

COMMENT ON TABLE hs_code_master  IS 'Thai Customs AHTN Protocol 2022 — 8-digit HS descriptions TH+EN';
COMMENT ON TABLE fta_eligibility IS 'FTA eligibility: RCEP/ATIGA/AANZFTA/JTEPA/TAFTA — 14 countries';
