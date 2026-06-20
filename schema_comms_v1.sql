-- ============================================================
-- AI TO AI HOLDING — Command & Communication Architecture
-- Signal [B] | Phase 1
-- ============================================================
-- ระบบนี้กำหนดวิธีที่ Chairman สั่งการ → AI CEO รับ → กระจายไป Offices → Agents ทำงาน → รายงานกลับ
-- ทุก message ต้องผ่าน Audit Core (P-04)
-- ============================================================

-- ============================================================
-- TABLE: command_queue
-- ทุกคำสั่งในองค์กรเริ่มต้นที่นี่
-- ============================================================

CREATE TABLE command_queue (
    id              TEXT PRIMARY KEY,           -- UUID v4
    command_type    TEXT NOT NULL
                    CHECK (command_type IN (
                        'KILL_SWITCH',          -- Chairman only, zero delay
                        'POLICY_CHANGE',        -- Chairman → Governance Office
                        'TASK_ASSIGN',          -- AI CEO → Office/Division
                        'TASK_DELEGATE',        -- Office → Agent
                        'QUERY_REQUEST',        -- Agent → Knowledge Office
                        'ESCALATION',           -- Agent → Office → AI CEO → Chairman
                        'REPORT_REQUEST'        -- AI CEO → Office (ขอรายงาน)
                    )),
    issued_by       TEXT NOT NULL REFERENCES org_entities(id),
    issued_to       TEXT NOT NULL REFERENCES org_entities(id),
    priority        INTEGER NOT NULL DEFAULT 5  -- 1=CRITICAL(Kill Switch) 2=HIGH 3=NORMAL 4=LOW 5=BACKGROUND
                    CHECK (priority BETWEEN 1 AND 5),
    payload         TEXT NOT NULL,              -- JSON: รายละเอียดคำสั่ง
    status          TEXT NOT NULL DEFAULT 'QUEUED'
                    CHECK (status IN ('QUEUED','DISPATCHED','ACKNOWLEDGED','IN_PROGRESS','COMPLETED','FAILED','CANCELLED')),
    issued_at       TEXT NOT NULL DEFAULT (datetime('now')),
    deadline_at     TEXT,                       -- NULL = no deadline
    parent_cmd_id   TEXT REFERENCES command_queue(id),  -- สำหรับ sub-commands
    evidence_hash   TEXT NOT NULL               -- P-04
);

-- ============================================================
-- TABLE: command_acknowledgements
-- ทุก entity ที่รับคำสั่งต้อง ACK ภายใน SLA ที่กำหนด
-- ============================================================

CREATE TABLE command_acknowledgements (
    id              TEXT PRIMARY KEY,
    command_id      TEXT NOT NULL REFERENCES command_queue(id),
    acknowledged_by TEXT NOT NULL REFERENCES org_entities(id),
    ack_status      TEXT NOT NULL
                    CHECK (ack_status IN ('ACCEPTED','REJECTED','ESCALATED')),
    rejection_reason TEXT,                      -- กรณี REJECTED
    acknowledged_at TEXT NOT NULL DEFAULT (datetime('now')),
    evidence_hash   TEXT NOT NULL               -- P-04
);

-- ============================================================
-- TABLE: task_assignments
-- งานที่ถูก assign ให้ Agent ทำจริง ๆ
-- ============================================================

CREATE TABLE task_assignments (
    id              TEXT PRIMARY KEY,
    command_id      TEXT NOT NULL REFERENCES command_queue(id),
    assigned_to     TEXT NOT NULL REFERENCES org_entities(id),  -- Agent
    assigned_by     TEXT NOT NULL REFERENCES org_entities(id),  -- Office
    task_type       TEXT NOT NULL,              -- 'HS_CLASSIFY' | 'DUTY_CALC' | 'COMPLIANCE_SCREEN' | 'DOC_EXTRACT' ...
    input_payload   TEXT NOT NULL,              -- JSON: ข้อมูลที่ Agent ต้องใช้
    output_payload  TEXT,                       -- JSON: ผลลัพธ์ที่ Agent ส่งกลับ
    status          TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING','IN_PROGRESS','COMPLETED','FAILED','NEEDS_REVIEW')),
    confidence_score REAL                       -- P-05: Agent ต้องแนบมาด้วย
                    CHECK (confidence_score BETWEEN 0 AND 1),
    source_reference TEXT,                      -- P-05: อ้างอิงกฎหมาย/ระเบียบ
    started_at      TEXT,
    completed_at    TEXT,
    evidence_hash   TEXT NOT NULL               -- P-04
);

-- ============================================================
-- TABLE: escalation_log
-- เมื่อ Agent ติดปัญหา → ส่งขึ้น Office → AI CEO → Chairman
-- ============================================================

CREATE TABLE escalation_log (
    id              TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES task_assignments(id),
    escalated_by    TEXT NOT NULL REFERENCES org_entities(id),
    escalated_to    TEXT NOT NULL REFERENCES org_entities(id),
    escalation_level INTEGER NOT NULL           -- 1=Office, 2=AI CEO, 3=Chairman
                    CHECK (escalation_level BETWEEN 1 AND 3),
    reason          TEXT NOT NULL,
    resolution      TEXT,
    escalated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at     TEXT,
    evidence_hash   TEXT NOT NULL               -- P-04
);

-- ============================================================
-- TABLE: reports
-- Office/Division รายงานกลับ AI CEO → AI CEO สรุปถึง Chairman
-- ============================================================

CREATE TABLE reports (
    id              TEXT PRIMARY KEY,
    report_type     TEXT NOT NULL
                    CHECK (report_type IN (
                        'DAILY_SUMMARY',
                        'TASK_COMPLETION',
                        'RISK_ALERT',
                        'REVENUE_SUMMARY',
                        'AUDIT_DIGEST',
                        'ESCALATION_OUTCOME'
                    )),
    authored_by     TEXT NOT NULL REFERENCES org_entities(id),
    submitted_to    TEXT NOT NULL REFERENCES org_entities(id),
    period_start    TEXT,
    period_end      TEXT,
    content         TEXT NOT NULL,              -- JSON: เนื้อหารายงาน
    status          TEXT NOT NULL DEFAULT 'SUBMITTED'
                    CHECK (status IN ('SUBMITTED','READ','ACTIONED','ARCHIVED')),
    submitted_at    TEXT NOT NULL DEFAULT (datetime('now')),
    read_at         TEXT,
    evidence_hash   TEXT NOT NULL               -- P-04
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_cmd_status     ON command_queue(status);
CREATE INDEX idx_cmd_issued_to  ON command_queue(issued_to);
CREATE INDEX idx_cmd_priority   ON command_queue(priority);
CREATE INDEX idx_task_agent     ON task_assignments(assigned_to);
CREATE INDEX idx_task_status    ON task_assignments(status);
CREATE INDEX idx_escalation_lvl ON escalation_log(escalation_level);
CREATE INDEX idx_report_to      ON reports(submitted_to);
