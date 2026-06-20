-- ============================================================
-- AI TO AI HOLDING — Learning Loop & Feedback Pipeline
-- Signal [C] | Phase 1
-- ============================================================
-- กลไกนี้ทำให้องค์กร "똑똑ขึ้น" ทุกครั้งที่จบ case
-- ทุก lesson ต้องวิ่งกลับเข้า Knowledge Office (P-06)
-- ไม่มี lesson ที่หายไปโดยไม่ถูกบันทึก (P-04)
-- ============================================================

-- ============================================================
-- FLOW ภาพรวม:
--
-- [Case จบ] → learning_triggers
--      ↓
-- [Knowledge Office วิเคราะห์] → learning_sessions
--      ↓
-- [สกัด Lesson] → learning_lessons
--      ↓
-- [อัปเดต Knowledge Graph] → knowledge_graph_nodes/edges (schema_v1)
--      ↓
-- [ประเมินผล] → learning_evaluations
--      ↓
-- [รายงาน] → reports (schema_comms_v1)
-- ============================================================

-- ============================================================
-- TABLE: learning_triggers
-- เหตุการณ์ที่กระตุ้นให้เกิด learning cycle
-- ============================================================

CREATE TABLE learning_triggers (
    id              TEXT PRIMARY KEY,
    trigger_type    TEXT NOT NULL
                    CHECK (trigger_type IN (
                        'CASE_COMPLETED',       -- จบ customs case ปกติ
                        'OVERRIDE_DETECTED',    -- Chairman/AI CEO แก้ output ของ Agent
                        'DISPUTE_RESOLVED',     -- Governance ชี้ขาดข้อพิพาทแล้ว
                        'LOW_CONFIDENCE',       -- Confidence Score ต่ำกว่า threshold
                        'NEW_REGULATION',       -- Knowledge Office ตรวจพบกฎหมายใหม่
                        'AGENT_ESCALATION'      -- Agent ส่ง escalation เพราะไม่รู้คำตอบ
                    )),
    source_id       TEXT NOT NULL,              -- case_id | task_id | dispute_id
    source_table    TEXT NOT NULL,              -- 'customs_cases' | 'task_assignments' | 'customs_disputes'
    confidence_at_trigger REAL,                 -- score ตอนที่ trigger (ถ้ามี)
    triggered_at    TEXT NOT NULL DEFAULT (datetime('now')),
    processed       INTEGER NOT NULL DEFAULT 0, -- 0=รอ Knowledge Office รับ | 1=รับแล้ว
    evidence_hash   TEXT NOT NULL               -- P-04
);

-- ============================================================
-- TABLE: learning_sessions
-- Knowledge Office เปิด session วิเคราะห์แต่ละ trigger
-- ============================================================

CREATE TABLE learning_sessions (
    id              TEXT PRIMARY KEY,
    trigger_id      TEXT NOT NULL REFERENCES learning_triggers(id),
    conducted_by    TEXT NOT NULL REFERENCES org_entities(id),  -- Knowledge Office agent
    session_status  TEXT NOT NULL DEFAULT 'OPEN'
                    CHECK (session_status IN ('OPEN','ANALYZING','COMPLETED','SKIPPED')),
    skip_reason     TEXT,                       -- กรณี SKIPPED (เช่น duplicate lesson)
    opened_at       TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT,
    evidence_hash   TEXT NOT NULL               -- P-04
);

-- ============================================================
-- TABLE: learning_lessons
-- บทเรียนที่สกัดได้จากแต่ละ session — หัวใจของระบบ
-- ============================================================

CREATE TABLE learning_lessons (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES learning_sessions(id),
    lesson_category TEXT NOT NULL
                    CHECK (lesson_category IN (
                        'HS_CLASSIFICATION',    -- เรียนรู้ HS Code ที่ถูกต้อง
                        'DUTY_RATE',            -- อัตราภาษีที่อัปเดต
                        'COMPLIANCE_RULE',      -- กฎ OGA / สินค้าควบคุมใหม่
                        'DOCUMENT_PATTERN',     -- pattern เอกสารที่พบใหม่
                        'AGENT_BEHAVIOR',       -- พฤติกรรม Agent ที่ต้องแก้
                        'CLIENT_PATTERN'        -- พฤติกรรม client AI ที่ควรรู้
                    )),
    -- สิ่งที่เคยเชื่อ vs สิ่งที่ถูกต้อง
    previous_belief TEXT,                       -- JSON: output เดิมที่ Agent ให้
    corrected_belief TEXT NOT NULL,             -- JSON: สิ่งที่ถูกต้องหลังวิเคราะห์
    confidence_gain REAL,                       -- Confidence Score ที่คาดว่าจะเพิ่มขึ้น
    -- หลักฐานที่ใช้สนับสนุน lesson นี้
    evidence_doc_ids TEXT,                      -- JSON array: knowledge_documents.id
    legal_reference TEXT,                       -- กฎหมาย/ระเบียบที่ยืนยัน (P-05)
    -- การ apply ลง Knowledge Graph
    graph_node_id   TEXT REFERENCES knowledge_graph_nodes(id),  -- node ที่อัปเดต
    graph_edge_id   TEXT REFERENCES knowledge_graph_edges(id),  -- edge ที่อัปเดต
    apply_status    TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (apply_status IN ('PENDING','APPLIED','REJECTED','NEEDS_CHAIRMAN')),
    applied_at      TEXT,
    applied_by      TEXT REFERENCES org_entities(id),
    rejection_reason TEXT,
    -- ถ้า lesson นี้ต้องให้ Chairman อนุมัติก่อน (เช่น เปลี่ยนนโยบายใหญ่)
    requires_chairman_approval INTEGER NOT NULL DEFAULT 0,
    chairman_approved_at TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    evidence_hash   TEXT NOT NULL               -- P-04
);

-- ============================================================
-- TABLE: learning_evaluations
-- วัดผลว่าการเรียนรู้ได้ผลจริงไหม — ปิด feedback loop
-- ============================================================

CREATE TABLE learning_evaluations (
    id              TEXT PRIMARY KEY,
    lesson_id       TEXT NOT NULL REFERENCES learning_lessons(id),
    evaluated_by    TEXT NOT NULL REFERENCES org_entities(id),  -- Trust Office
    -- case ทดสอบหลัง apply lesson
    test_case_id    TEXT,                       -- customs_cases.id ที่ใช้วัดผล
    before_score    REAL,                       -- Confidence Score ก่อน apply
    after_score     REAL,                       -- Confidence Score หลัง apply
    score_delta     REAL GENERATED ALWAYS AS (after_score - before_score) STORED,
    evaluation_result TEXT NOT NULL
                    CHECK (evaluation_result IN (
                        'IMPROVED',             -- score เพิ่มขึ้น ≥ threshold
                        'NO_CHANGE',            -- score ไม่เปลี่ยน
                        'DEGRADED',             -- score ลดลง — ต้อง escalate
                        'INSUFFICIENT_DATA'     -- ยังไม่มี case ทดสอบพอ
                    )),
    notes           TEXT,
    evaluated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    evidence_hash   TEXT NOT NULL               -- P-04
);

-- ============================================================
-- TABLE: agent_knowledge_state
-- ติดตามว่า Agent แต่ละตัวรับ lesson ล่าสุดไปแล้วหรือยัง
-- ============================================================

CREATE TABLE agent_knowledge_state (
    id              TEXT PRIMARY KEY,
    agent_id        TEXT NOT NULL REFERENCES org_entities(id),
    lesson_id       TEXT NOT NULL REFERENCES learning_lessons(id),
    sync_status     TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (sync_status IN ('PENDING','SYNCED','FAILED')),
    synced_at       TEXT,
    UNIQUE(agent_id, lesson_id)                 -- Agent รับ lesson เดิมซ้ำไม่ได้
);

-- ============================================================
-- TABLE: knowledge_version_log
-- ติดตาม version ของ Foundation knowledge ทั้งองค์กร
-- ============================================================

CREATE TABLE knowledge_version_log (
    id              TEXT PRIMARY KEY,
    version         TEXT NOT NULL,              -- 'v1.0.0' | 'v1.0.1' ...
    lessons_applied INTEGER NOT NULL DEFAULT 0, -- จำนวน lesson ที่ทำให้เกิด version นี้
    nodes_updated   INTEGER NOT NULL DEFAULT 0,
    edges_updated   INTEGER NOT NULL DEFAULT 0,
    published_by    TEXT NOT NULL REFERENCES org_entities(id),  -- Knowledge Office
    published_at    TEXT NOT NULL DEFAULT (datetime('now')),
    release_notes   TEXT,
    evidence_hash   TEXT NOT NULL               -- P-04
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_trigger_type      ON learning_triggers(trigger_type);
CREATE INDEX idx_trigger_processed ON learning_triggers(processed);
CREATE INDEX idx_session_status    ON learning_sessions(session_status);
CREATE INDEX idx_lesson_category   ON learning_lessons(lesson_category);
CREATE INDEX idx_lesson_apply      ON learning_lessons(apply_status);
CREATE INDEX idx_lesson_chairman   ON learning_lessons(requires_chairman_approval);
CREATE INDEX idx_eval_result       ON learning_evaluations(evaluation_result);
CREATE INDEX idx_agent_sync        ON agent_knowledge_state(sync_status);
