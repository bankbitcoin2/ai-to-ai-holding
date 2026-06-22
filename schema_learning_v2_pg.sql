-- ============================================================
-- schema_learning_v2_pg.sql
-- Learning Loop Extension: Classification Cache + Candidates Log
-- PostgreSQL version — apply บน Railway
-- ============================================================

-- ============================================================
-- TABLE: hs_classification_cache
-- ============================================================
CREATE TABLE IF NOT EXISTS hs_classification_cache (
    id                  TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    description_hash    TEXT NOT NULL UNIQUE,
    description_sample  TEXT NOT NULL,
    hs_code             TEXT NOT NULL,
    hs_code_11          TEXT,
    hs_description      TEXT,
    hs_description_th   TEXT,
    confidence_score    REAL NOT NULL,
    source              TEXT NOT NULL DEFAULT 'CLAUDE'
                        CHECK (source IN ('CLAUDE','CONFIRMED','CHAIRMAN_OVERRIDE')),
    hit_count           INTEGER NOT NULL DEFAULT 1,
    miss_count          INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_hit_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ,
    evidence_hash       TEXT NOT NULL DEFAULT 'PENDING'
);

-- ============================================================
-- TABLE: classification_candidates_log
-- ============================================================
CREATE TABLE IF NOT EXISTS classification_candidates_log (
    id                  TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    session_id          TEXT NOT NULL,
    session_type        TEXT NOT NULL DEFAULT 'SANDBOX'
                        CHECK (session_type IN ('SANDBOX','PRODUCTION','CHAIRMAN')),
    description         TEXT NOT NULL,
    candidate_rank      INTEGER NOT NULL,
    hs_code             TEXT,
    hs_code_11          TEXT,
    hs_description      TEXT,
    confidence_score    REAL,
    source_reference    TEXT,
    was_selected        INTEGER NOT NULL DEFAULT 0,
    feedback_status     TEXT DEFAULT NULL
                        CHECK (feedback_status IN (NULL,'CONFIRMED','REJECTED','AMENDED')),
    amended_hs_code     TEXT,
    feedback_by         TEXT,
    feedback_at         TIMESTAMPTZ,
    learning_triggered  INTEGER NOT NULL DEFAULT 0,
    learning_trigger_id TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    evidence_hash       TEXT NOT NULL DEFAULT 'PENDING'
);

-- ============================================================
-- TABLE: cache_feedback_queue
-- ============================================================
CREATE TABLE IF NOT EXISTS cache_feedback_queue (
    id                  TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    candidate_log_id    TEXT NOT NULL REFERENCES classification_candidates_log(id),
    action              TEXT NOT NULL
                        CHECK (action IN (
                            'PROMOTE_TO_CACHE',
                            'DEMOTE_FROM_CACHE',
                            'CREATE_LESSON',
                            'NOTIFY_CHAIRMAN'
                        )),
    status              TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK (status IN ('PENDING','PROCESSING','DONE','FAILED')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at        TIMESTAMPTZ,
    error_msg           TEXT
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_cache_hash         ON hs_classification_cache(description_hash);
CREATE INDEX IF NOT EXISTS idx_cache_hs           ON hs_classification_cache(hs_code);
CREATE INDEX IF NOT EXISTS idx_cache_source       ON hs_classification_cache(source);
CREATE INDEX IF NOT EXISTS idx_cache_hits         ON hs_classification_cache(hit_count DESC);
CREATE INDEX IF NOT EXISTS idx_candidates_session ON classification_candidates_log(session_id);
CREATE INDEX IF NOT EXISTS idx_candidates_hs      ON classification_candidates_log(hs_code);
CREATE INDEX IF NOT EXISTS idx_candidates_fb      ON classification_candidates_log(feedback_status);
CREATE INDEX IF NOT EXISTS idx_feedback_queue     ON cache_feedback_queue(status);
