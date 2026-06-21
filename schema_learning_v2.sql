-- ============================================================
-- schema_learning_v2.sql
-- Learning Loop Extension: Classification Cache + Candidates Log
-- ต่อจาก schema_learning_v1.sql
-- ============================================================

-- ============================================================
-- TABLE: hs_classification_cache
-- Fast-lookup: สินค้าที่เคยจำแนกแล้ว confidence >= 0.85
-- ครั้งต่อไปที่ถามสินค้าเดิม -> คืนจาก cache ทันที ไม่ต้อง call Claude
-- Source hierarchy: CLAUDE < CONFIRMED < CHAIRMAN_OVERRIDE
-- ============================================================
CREATE TABLE IF NOT EXISTS hs_classification_cache (
    id                  TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    description_hash    TEXT NOT NULL UNIQUE,   -- SHA256(lower(trim(description)))
    description_sample  TEXT NOT NULL,          -- 200 chars แรก (debug)
    hs_code             TEXT NOT NULL,
    hs_code_11          TEXT,                   -- Thai 11-digit from CKAN
    hs_description      TEXT,
    hs_description_th   TEXT,
    confidence_score    REAL NOT NULL,
    source              TEXT NOT NULL DEFAULT 'CLAUDE'
                        CHECK (source IN (
                            'CLAUDE',           -- Claude API, confidence >= 0.85
                            'CONFIRMED',        -- ลูกค้า/Chairman ยืนยันแล้ว
                            'CHAIRMAN_OVERRIDE' -- Chairman แก้เอง (สูงสุด)
                        )),
    hit_count           INTEGER NOT NULL DEFAULT 1,     -- ถูกเรียกซ้ำกี่ครั้ง
    miss_count          INTEGER NOT NULL DEFAULT 0,     -- ถูก reject กี่ครั้ง
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    last_hit_at         TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at          TEXT,                   -- NULL = ไม่หมดอายุ (CONFIRMED/OVERRIDE)
    evidence_hash       TEXT NOT NULL DEFAULT 'PENDING'
);

-- ============================================================
-- TABLE: classification_candidates_log
-- บันทึก candidates ทุกตัว (ไม่ใช่แค่ best) จาก Claude
-- ใช้วิเคราะห์ว่า Claude สับสนระหว่าง HS ไหนบ่อย
-- และ feedback จากลูกค้าช่วย refine cache
-- ============================================================
CREATE TABLE IF NOT EXISTS classification_candidates_log (
    id                  TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    session_id          TEXT NOT NULL,          -- sandbox_session_id หรือ customs_case_id
    session_type        TEXT NOT NULL DEFAULT 'SANDBOX'
                        CHECK (session_type IN ('SANDBOX', 'PRODUCTION', 'CHAIRMAN')),
    description         TEXT NOT NULL,
    candidate_rank      INTEGER NOT NULL,       -- 1=best, 2=second, ...
    hs_code             TEXT,
    hs_code_11          TEXT,
    hs_description      TEXT,
    confidence_score    REAL,
    source_reference    TEXT,
    was_selected        INTEGER NOT NULL DEFAULT 0, -- 1 ถ้าเป็น rank=1 (top pick)
    -- Feedback จากลูกค้าหรือ Chairman
    feedback_status     TEXT DEFAULT NULL
                        CHECK (feedback_status IN (
                            NULL,               -- ยังไม่มี feedback
                            'CONFIRMED',        -- ยืนยันว่าถูก
                            'REJECTED',         -- ปฏิเสธ
                            'AMENDED'           -- แก้ไขเป็น HS อื่น
                        )),
    amended_hs_code     TEXT,                   -- HS Code ที่ถูกต้องตาม feedback
    feedback_by         TEXT,                   -- client_id หรือ 'CHAIRMAN'
    feedback_at         TEXT,
    -- Learning trigger: ถ้า rejected -> สร้าง learning_trigger อัตโนมัติ
    learning_triggered  INTEGER NOT NULL DEFAULT 0,
    learning_trigger_id TEXT,                   -- REFERENCES learning_triggers(id)
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    evidence_hash       TEXT NOT NULL DEFAULT 'PENDING'
);

-- ============================================================
-- TABLE: cache_feedback_queue
-- Queue: feedback ที่รอ process เข้า learning_lessons
-- Worker ประมวลผลทุก 1 ชั่วโมง
-- ============================================================
CREATE TABLE IF NOT EXISTS cache_feedback_queue (
    id                  TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    candidate_log_id    TEXT NOT NULL REFERENCES classification_candidates_log(id),
    action              TEXT NOT NULL
                        CHECK (action IN (
                            'PROMOTE_TO_CACHE',     -- confirmed -> เพิ่ม/อัปเดต cache
                            'DEMOTE_FROM_CACHE',    -- rejected -> ลด hit_count / ลบ cache
                            'CREATE_LESSON',        -- สร้าง learning_lesson
                            'NOTIFY_CHAIRMAN'       -- confidence ต่ำมาก -> แจ้ง Chairman
                        )),
    status              TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK (status IN ('PENDING', 'PROCESSING', 'DONE', 'FAILED')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    processed_at        TEXT,
    error_msg           TEXT
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_cache_hash        ON hs_classification_cache(description_hash);
CREATE INDEX IF NOT EXISTS idx_cache_hs          ON hs_classification_cache(hs_code);
CREATE INDEX IF NOT EXISTS idx_cache_source      ON hs_classification_cache(source);
CREATE INDEX IF NOT EXISTS idx_cache_hits        ON hs_classification_cache(hit_count DESC);
CREATE INDEX IF NOT EXISTS idx_candidates_session ON classification_candidates_log(session_id);
CREATE INDEX IF NOT EXISTS idx_candidates_hs     ON classification_candidates_log(hs_code);
CREATE INDEX IF NOT EXISTS idx_candidates_fb     ON classification_candidates_log(feedback_status);
CREATE INDEX IF NOT EXISTS idx_feedback_queue    ON cache_feedback_queue(status);
