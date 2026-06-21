-- schema_cache_v1.sql
-- HS Classification Cache — ลด Claude API cost
-- Cache hit = $0 ต้นทุน ไม่ว่าใช้ model ไหน

CREATE TABLE IF NOT EXISTS hs_classification_cache (
    cache_key       TEXT PRIMARY KEY,          -- SHA256(normalized_desc + origin)
    description     TEXT NOT NULL,             -- ต้นฉบับ
    origin_country  TEXT,
    hs_code         TEXT,
    hs_description  TEXT,
    confidence_score REAL,
    source_reference TEXT,
    notes           TEXT,
    model_used      TEXT,                      -- 'mock' | 'haiku' | 'sonnet' ฯลฯ
    hit_count       INTEGER DEFAULT 1,         -- ถูกดึงกี่ครั้งแล้ว
    created_at      TIMESTAMP DEFAULT (datetime('now')),
    last_hit_at     TIMESTAMP DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cache_hs ON hs_classification_cache(hs_code);
CREATE INDEX IF NOT EXISTS idx_cache_created ON hs_classification_cache(created_at);
