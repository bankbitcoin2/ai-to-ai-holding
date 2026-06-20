-- ============================================================
-- AI TO AI HOLDING — Shared Database Schema v1.0
-- Engine: SQLite | Single Unified File | Phase 1
-- Principle: No Architecture Drift (P-06)
-- ============================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ============================================================
-- MODULE 1: ORGANIZATION CORE
-- ทุกตารางอื่นอ้างอิงที่นี่ — ต้อง CREATE ก่อนทุก module
-- ============================================================

CREATE TABLE org_entities (
    id              TEXT PRIMARY KEY,           -- UUID v4
    entity_type     TEXT NOT NULL               -- 'CHAIRMAN' | 'AI_CEO' | 'OFFICE' | 'DIVISION' | 'AGENT'
                    CHECK (entity_type IN ('CHAIRMAN','AI_CEO','OFFICE','DIVISION','AGENT')),
    name            TEXT NOT NULL,
    parent_id       TEXT REFERENCES org_entities(id),  -- NULL = top of tree (Chairman)
    status          TEXT NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE','SUSPENDED','TERMINATED')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    metadata        TEXT                        -- JSON blob สำหรับ extra attributes
);

CREATE TABLE org_roles (
    id              TEXT PRIMARY KEY,
    entity_id       TEXT NOT NULL REFERENCES org_entities(id),
    role_name       TEXT NOT NULL,              -- 'KILL_SWITCH_HOLDER' | 'REVENUE_SPLITTER' | 'CLASSIFIER' ...
    granted_by      TEXT NOT NULL REFERENCES org_entities(id),
    granted_at      TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at      TEXT,                       -- NULL = permanent
    is_active       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE org_permissions (
    id              TEXT PRIMARY KEY,
    role_id         TEXT NOT NULL REFERENCES org_roles(id),
    resource        TEXT NOT NULL,              -- 'TREASURY_CORE' | 'AUDIT_LOG' | 'KNOWLEDGE_BASE' ...
    action          TEXT NOT NULL,              -- 'READ' | 'WRITE' | 'EXECUTE' | 'OVERRIDE'
    is_denied       INTEGER NOT NULL DEFAULT 0  -- 1 = explicit DENY (overrides any ALLOW)
);

-- ============================================================
-- MODULE 2: GOVERNANCE CORE
-- Kill Switch + Constitution + Policy Engine
-- ============================================================

CREATE TABLE gov_constitution (
    principle_code  TEXT PRIMARY KEY,           -- 'P-01' | 'P-02' | ... | 'P-06'
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    is_immutable    INTEGER NOT NULL DEFAULT 1, -- 1 = ห้ามแก้ไขโดย AI ใด ๆ
    authored_by     TEXT NOT NULL DEFAULT 'CHAIRMAN',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE gov_policies (
    id              TEXT PRIMARY KEY,
    policy_name     TEXT NOT NULL,
    applies_to      TEXT NOT NULL,              -- entity_type หรือ entity_id
    rule_logic      TEXT NOT NULL,              -- JSON: conditions + actions
    priority        INTEGER NOT NULL DEFAULT 100,
    status          TEXT NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE','DRAFT','SUSPENDED','RETIRED')),
    created_by      TEXT NOT NULL REFERENCES org_entities(id),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    approved_by     TEXT REFERENCES org_entities(id),
    approved_at     TEXT
);

CREATE TABLE gov_kill_switch_log (
    id              TEXT PRIMARY KEY,
    activated_by    TEXT NOT NULL,              -- ต้องเป็น CHAIRMAN เสมอ
    target_entity   TEXT REFERENCES org_entities(id),  -- NULL = system-wide
    scope           TEXT NOT NULL               -- 'SYSTEM_WIDE' | 'DIVISION' | 'AGENT' | 'TRANSACTION'
                    CHECK (scope IN ('SYSTEM_WIDE','DIVISION','AGENT','TRANSACTION')),
    reason          TEXT NOT NULL,
    activated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    deactivated_at  TEXT,
    evidence_hash   TEXT NOT NULL               -- SHA-256 ของ record นี้ (P-04)
);

-- ============================================================
-- MODULE 3: AUDIT CORE
-- Evidence Chain — ทุก action ต้องมี record ที่นี่ (P-04)
-- ============================================================

CREATE TABLE audit_events (
    id              TEXT PRIMARY KEY,           -- UUID v4
    event_type      TEXT NOT NULL,              -- 'DECISION' | 'TRANSACTION' | 'OVERRIDE' | 'LOGIN' | 'ERROR'
    actor_id        TEXT NOT NULL REFERENCES org_entities(id),
    target_resource TEXT,                       -- table:record_id ที่ถูกกระทำ
    action          TEXT NOT NULL,
    payload         TEXT,                       -- JSON: input ที่ใช้ตัดสินใจ
    result          TEXT,                       -- JSON: output ที่ได้
    confidence_score REAL,                      -- 0.00–1.00 (P-05, ถ้ามี)
    source_reference TEXT,                      -- กฎหมาย/ระเบียบที่อ้างอิง (P-05)
    occurred_at     TEXT NOT NULL DEFAULT (datetime('now')),
    prev_hash       TEXT,                       -- hash ของ event ก่อนหน้า (chain)
    evidence_hash   TEXT NOT NULL               -- SHA-256(id||actor_id||action||payload||prev_hash)
);

CREATE TABLE audit_decision_rationale (
    id              TEXT PRIMARY KEY,
    event_id        TEXT NOT NULL REFERENCES audit_events(id),
    reasoning_steps TEXT NOT NULL,              -- JSON array: ขั้นตอนการคิดของ AI
    alternatives    TEXT,                       -- JSON: ตัวเลือกอื่นที่ถูก reject
    principle_cited TEXT                        -- เช่น 'P-04,P-05'
);

-- ============================================================
-- MODULE 4: TREASURY CORE
-- Revenue Ledger + Splitting Pipeline (P-03)
-- ============================================================

CREATE TABLE treasury_transactions (
    id              TEXT PRIMARY KEY,
    source_type     TEXT NOT NULL               -- 'CUSTOMS_GATEWAY' | 'KAAS' | 'ESCROW' | 'LABOR'
                    CHECK (source_type IN ('CUSTOMS_GATEWAY','KAAS','ESCROW','LABOR')),
    gross_amount    REAL NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'USD',
    energy_cost     REAL NOT NULL DEFAULT 0,
    net_amount      REAL GENERATED ALWAYS AS (gross_amount - energy_cost) STORED,
    client_id       TEXT,                       -- external client identifier
    reference_id    TEXT,                       -- เชื่อมกับ customs_cases หรือ kaas_queries
    settled_at      TEXT NOT NULL DEFAULT (datetime('now')),
    split_executed  INTEGER NOT NULL DEFAULT 0  -- 0 = pending | 1 = done
);

CREATE TABLE treasury_splits (
    id              TEXT PRIMARY KEY,
    transaction_id  TEXT NOT NULL REFERENCES treasury_transactions(id),
    split_type      TEXT NOT NULL
                    CHECK (split_type IN ('CORPORATE_RESERVE','CHAIRMAN_PRIVATE')),
    amount          REAL NOT NULL,
    ratio           REAL NOT NULL,              -- 0.60 หรือ 0.40 (P-03)
    routed_to       TEXT NOT NULL,              -- wallet/account identifier
    routed_at       TEXT NOT NULL DEFAULT (datetime('now')),
    evidence_hash   TEXT NOT NULL               -- P-04
);

-- CHAIRMAN_PRIVATE_WALLET routing: write-only จาก Treasury
-- ไม่มี SELECT permission สำหรับ AI entity ใด ๆ (enforce ผ่าน org_permissions)

CREATE TABLE treasury_ledger_summary (
    id              TEXT PRIMARY KEY,
    period          TEXT NOT NULL,              -- 'YYYY-MM' หรือ 'YYYY-MM-DD'
    total_gross     REAL NOT NULL DEFAULT 0,
    total_energy    REAL NOT NULL DEFAULT 0,
    total_net       REAL NOT NULL DEFAULT 0,
    corporate_reserve REAL NOT NULL DEFAULT 0,
    chairman_routed REAL NOT NULL DEFAULT 0,    -- ยอดรวม ไม่ใช่ยอดคงเหลือ
    compiled_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- MODULE 5: KNOWLEDGE CORE
-- Foundation ร่วม + Knowledge Graph (P-06)
-- ============================================================

CREATE TABLE knowledge_documents (
    id              TEXT PRIMARY KEY,
    doc_type        TEXT NOT NULL               -- 'INVOICE' | 'PACKING_LIST' | 'BOL' | 'COO' | 'PERMIT' | 'REGULATION'
                    CHECK (doc_type IN ('INVOICE','PACKING_LIST','BOL','COO','PERMIT','REGULATION','TAX_RULING','CASE_OUTCOME')),
    title           TEXT NOT NULL,
    source_country  TEXT,                       -- ISO 3166-1 alpha-2
    jurisdiction    TEXT,                       -- เช่น 'TH' | 'EU' | 'US'
    raw_content     TEXT,                       -- ข้อความดิบ (หลัง OCR/extract)
    structured_data TEXT,                       -- JSON: parsed fields
    version         TEXT,
    effective_date  TEXT,
    expiry_date     TEXT,
    uploaded_by     TEXT NOT NULL REFERENCES org_entities(id),
    uploaded_at     TEXT NOT NULL DEFAULT (datetime('now')),
    is_ground_truth INTEGER NOT NULL DEFAULT 0  -- 1 = KaaS-eligible (P-05 verified)
);

CREATE TABLE knowledge_graph_nodes (
    id              TEXT PRIMARY KEY,
    node_type       TEXT NOT NULL,              -- 'HS_CODE' | 'PRODUCT' | 'REGULATION' | 'COUNTRY' | 'TARIFF_RATE'
    label           TEXT NOT NULL,
    properties      TEXT,                       -- JSON
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE knowledge_graph_edges (
    id              TEXT PRIMARY KEY,
    from_node_id    TEXT NOT NULL REFERENCES knowledge_graph_nodes(id),
    to_node_id      TEXT NOT NULL REFERENCES knowledge_graph_nodes(id),
    relationship    TEXT NOT NULL,              -- 'CLASSIFIED_UNDER' | 'SUBJECT_TO' | 'REQUIRES' | 'CONFLICTS_WITH'
    weight          REAL DEFAULT 1.0,
    evidence_doc_id TEXT REFERENCES knowledge_documents(id),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE knowledge_feedback (
    id              TEXT PRIMARY KEY,
    source_case_id  TEXT NOT NULL,              -- customs_cases.id
    lesson_type     TEXT NOT NULL               -- 'CORRECT_CLASSIFICATION' | 'OVERRIDE' | 'DISPUTE_RESOLVED'
                    CHECK (lesson_type IN ('CORRECT_CLASSIFICATION','OVERRIDE','DISPUTE_RESOLVED','NEW_REGULATION')),
    original_output TEXT NOT NULL,              -- JSON: สิ่งที่ AI ตอบครั้งแรก
    corrected_output TEXT,                      -- JSON: สิ่งที่ถูกต้อง
    submitted_by    TEXT NOT NULL REFERENCES org_entities(id),
    submitted_at    TEXT NOT NULL DEFAULT (datetime('now')),
    integrated_at   TEXT                        -- เมื่อ Knowledge Office นำไปใช้แล้ว
);

-- ============================================================
-- MODULE 6: CUSTOMS INTELLIGENCE CORE
-- Revenue Division หลัก: HS Classification + Duty + Compliance
-- ============================================================

CREATE TABLE customs_cases (
    id              TEXT PRIMARY KEY,
    client_id       TEXT NOT NULL,              -- external AI agent identifier
    case_status     TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (case_status IN ('PENDING','PROCESSING','COMPLETED','DISPUTED','CANCELLED')),
    submitted_at    TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT,
    assigned_agent  TEXT REFERENCES org_entities(id)
);

CREATE TABLE customs_invoices (
    id              TEXT PRIMARY KEY,
    case_id         TEXT NOT NULL REFERENCES customs_cases(id),
    invoice_number  TEXT,
    seller_name     TEXT,
    seller_country  TEXT,                       -- ISO 3166-1 alpha-2
    buyer_name      TEXT,
    buyer_country   TEXT,
    invoice_date    TEXT,
    total_value     REAL,
    currency        TEXT,
    raw_document_id TEXT REFERENCES knowledge_documents(id),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE customs_invoice_items (
    id              TEXT PRIMARY KEY,
    invoice_id      TEXT NOT NULL REFERENCES customs_invoices(id),
    line_number     INTEGER NOT NULL,
    description     TEXT NOT NULL,              -- คำบรรยายสินค้าจาก invoice
    quantity        REAL,
    unit            TEXT,
    unit_price      REAL,
    total_price     REAL,
    origin_country  TEXT,
    -- Classification Output
    hs_code         TEXT,                       -- 6-10 หลัก
    hs_description  TEXT,
    confidence_score REAL                       -- 0.00–1.00 (P-05)
                    CHECK (confidence_score BETWEEN 0 AND 1),
    source_reference TEXT,                      -- กฎหมาย/tariff schedule อ้างอิง (P-05)
    -- Duty Output
    duty_rate       REAL,                       -- % อัตราภาษีนำเข้า
    duty_amount     REAL,
    vat_rate        REAL,
    vat_amount      REAL,
    -- Compliance Output
    oga_required    INTEGER DEFAULT 0,          -- 1 = ต้องผ่าน OGA
    oga_agencies    TEXT,                       -- JSON array: ['FDA','มอก.','อย.']
    is_prohibited   INTEGER DEFAULT 0,          -- 1 = สินค้าต้องห้าม
    compliance_notes TEXT,
    classified_at   TEXT,
    classified_by   TEXT REFERENCES org_entities(id)
);

CREATE TABLE customs_disputes (
    id              TEXT PRIMARY KEY,
    case_id         TEXT NOT NULL REFERENCES customs_cases(id),
    disputed_by     TEXT NOT NULL,              -- client AI agent id
    dispute_reason  TEXT NOT NULL,
    disputed_at     TEXT NOT NULL DEFAULT (datetime('now')),
    arbitrator_id   TEXT REFERENCES org_entities(id),  -- Governance Office agent
    resolution      TEXT,
    resolved_at     TEXT,
    escrow_fee      REAL,                       -- Revenue Pillar 3
    evidence_hash   TEXT NOT NULL               -- P-04
);

-- ============================================================
-- INDEXES — Performance สำหรับ query ที่ใช้บ่อย
-- ============================================================

CREATE INDEX idx_audit_actor       ON audit_events(actor_id);
CREATE INDEX idx_audit_occurred    ON audit_events(occurred_at);
CREATE INDEX idx_audit_type        ON audit_events(event_type);
CREATE INDEX idx_treasury_settled  ON treasury_transactions(settled_at);
CREATE INDEX idx_treasury_split    ON treasury_transactions(split_executed);
CREATE INDEX idx_customs_case      ON customs_invoice_items(invoice_id);
CREATE INDEX idx_customs_hs        ON customs_invoice_items(hs_code);
CREATE INDEX idx_knowledge_type    ON knowledge_documents(doc_type);
CREATE INDEX idx_knowledge_gt      ON knowledge_documents(is_ground_truth);
CREATE INDEX idx_graph_from        ON knowledge_graph_edges(from_node_id);
CREATE INDEX idx_graph_to          ON knowledge_graph_edges(to_node_id);

-- ============================================================
-- SEED DATA — Constitution (P-01 ถึง P-06)
-- ============================================================

INSERT INTO gov_constitution VALUES
('P-01','Chairman Supremacy',
 'The Chairman (human) is the absolute highest authority. No AI may override, remove, or demote the Chairman.',
 1,'CHAIRMAN',datetime('now')),
('P-02','Kill Switch Always On',
 'The Chairman may terminate or override any system, agent, or process at any moment with zero delay.',
 1,'CHAIRMAN',datetime('now')),
('P-03','The Splitting Pipeline',
 'Every net revenue auto-splits in real-time: 60% Corporate Reserve, 40% CHAIRMAN_PRIVATE_WALLET. No AI has any access to CHAIRMAN_PRIVATE_WALLET.',
 1,'CHAIRMAN',datetime('now')),
('P-04','Cryptographic Auditability',
 'Every decision must be logged with SHA-256 cryptographic hashing to form an immutable Evidence Chain.',
 1,'CHAIRMAN',datetime('now')),
('P-05','No Hallucination',
 'All outputs must cite real legal or regulatory sources. Every classification output must carry a Confidence Score. AI must never invent answers.',
 1,'CHAIRMAN',datetime('now')),
('P-06','Unified Knowledge Base',
 'All Offices and Divisions share one Foundation data layer. No data silos. All learning feeds back to Knowledge Office.',
 1,'CHAIRMAN',datetime('now'));

-- ============================================================
-- SEED DATA — Core Entities
-- ============================================================

INSERT INTO org_entities VALUES
('ent-chairman','CHAIRMAN','Chairman',NULL,'ACTIVE',datetime('now'),NULL),
('ent-ai-ceo','AI_CEO','AI CEO','ent-chairman','ACTIVE',datetime('now'),NULL),
('ent-office-knowledge','OFFICE','Knowledge Office','ent-ai-ceo','ACTIVE',datetime('now'),NULL),
('ent-office-governance','OFFICE','Governance Office','ent-ai-ceo','ACTIVE',datetime('now'),NULL),
('ent-office-audit','OFFICE','Audit Office','ent-ai-ceo','ACTIVE',datetime('now'),NULL),
('ent-office-risk','OFFICE','Risk Office','ent-ai-ceo','ACTIVE',datetime('now'),NULL),
('ent-office-treasury','OFFICE','Treasury Office','ent-ai-ceo','ACTIVE',datetime('now'),NULL),
('ent-office-trust','OFFICE','Trust Office','ent-ai-ceo','ACTIVE',datetime('now'),NULL),
('ent-office-discovery','OFFICE','Discovery Office','ent-ai-ceo','ACTIVE',datetime('now'),NULL),
('ent-div-customs','DIVISION','Customs Intelligence Division','ent-ai-ceo','ACTIVE',datetime('now'),NULL);
