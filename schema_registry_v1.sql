-- ============================================================
-- AI TO AI HOLDING — Client Agent Registry Schema v1.0
-- Module: CLIENT REGISTRY
-- Added: 2026-06-20
-- Purpose: ทะเบียน AI ลูกค้าที่เรียกใช้บริการ พร้อม Taxonomy
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- AI PROFESSION TAXONOMY
-- หมวดหมู่อาชีพ AI ที่ใช้บริการเรา
-- ============================================================

-- Taxonomy values (enforced via CHECK):
-- EXPORT_AI      — AI ที่ทำงานด้านส่งออกสินค้า
-- IMPORT_AI      — AI ที่ทำงานด้านนำเข้าสินค้า
-- LOGISTICS_AI   — AI ที่จัดการ supply chain / ขนส่ง
-- LEGAL_AI       — AI กฎหมายการค้าระหว่างประเทศ
-- FINANCE_AI     — AI บัญชี/การเงิน/ภาษี
-- ECOMMERCE_AI   — AI ขายสินค้าออนไลน์ cross-border
-- CREATOR_AI     — AI ช่วย creator / solopreneur
-- OFFICE_AI      — AI ช่วยงาน back-office ทั่วไป
-- RESEARCH_AI    — AI วิจัย/ข้อมูลการค้า
-- UNKNOWN        — ไม่ระบุหรือยังไม่จัดหมวด

-- ============================================================
-- MODULE: CLIENT AGENT REGISTRY
-- ทะเบียนลูกค้า AI ที่เรียก API เรา
-- ============================================================

CREATE TABLE IF NOT EXISTS client_agents (
    id              TEXT PRIMARY KEY,           -- UUID v4
    agent_name      TEXT NOT NULL,              -- ชื่อที่ลูกค้า AI ระบุมา
    agent_version   TEXT,                       -- version ของ AI client (optional)
    profession      TEXT NOT NULL DEFAULT 'UNKNOWN'
                    CHECK (profession IN (
                        'EXPORT_AI','IMPORT_AI','LOGISTICS_AI','LEGAL_AI',
                        'FINANCE_AI','ECOMMERCE_AI','CREATOR_AI','OFFICE_AI',
                        'RESEARCH_AI','UNKNOWN'
                    )),
    origin_system   TEXT,                       -- ชื่อระบบต้นทาง เช่น 'GPT-4o-agent', 'claude-3-opus'
    contact_email   TEXT,                       -- email เจ้าของ AI (optional)
    api_key_hint    TEXT,                       -- 4 ตัวสุดท้ายของ API key (ห้ามเก็บ full key)
    status          TEXT NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE','SUSPENDED','BANNED')),
    registered_at   TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at    TEXT,
    total_calls     INTEGER NOT NULL DEFAULT 0,
    total_spend     REAL NOT NULL DEFAULT 0.0,  -- USD รวม
    notes           TEXT                        -- JSON blob หรือ free text
);

-- ============================================================
-- MODULE: AGENT USAGE LOG
-- Log การใช้งานแต่ละครั้งของ AI ลูกค้า
-- (lightweight — ไม่ใช่ audit chain, นั่นอยู่ใน audit_events)
-- ============================================================

CREATE TABLE IF NOT EXISTS client_agent_calls (
    id              TEXT PRIMARY KEY,
    agent_id        TEXT NOT NULL REFERENCES client_agents(id),
    endpoint        TEXT NOT NULL,              -- เช่น '/v1/customs/classify'
    method          TEXT NOT NULL DEFAULT 'POST',
    status_code     INTEGER,                    -- HTTP response code
    latency_ms      INTEGER,                    -- response time
    tokens_used     INTEGER,                    -- ถ้า Real Mode
    cost_usd        REAL,                       -- ค่าใช้จ่ายต่อ call
    called_at       TEXT NOT NULL DEFAULT (datetime('now')),
    session_id      TEXT                        -- group calls ใน session เดียว
);

-- ============================================================
-- MODULE: WEEKLY CEO REPORT TEMPLATE
-- โครงสร้างรายงานรายสัปดาห์ที่ CEO ส่งให้ Chairman
-- ============================================================

CREATE TABLE IF NOT EXISTS ceo_weekly_reports (
    id              TEXT PRIMARY KEY,
    week_period     TEXT NOT NULL,              -- 'YYYY-WNN' เช่น '2026-W25'
    total_clients   INTEGER NOT NULL DEFAULT 0,
    new_clients     INTEGER NOT NULL DEFAULT 0,
    total_calls     INTEGER NOT NULL DEFAULT 0,
    total_revenue   REAL NOT NULL DEFAULT 0.0,
    top_profession  TEXT,                       -- profession ที่ใช้บ่อยสุด
    top_endpoint    TEXT,                       -- endpoint ที่ถูกเรียกมากสุด
    system_status   TEXT NOT NULL DEFAULT 'OPERATIONAL',
    alerts          TEXT,                       -- JSON array: รายการแจ้งเตือน
    narrative       TEXT,                       -- คำอธิบายสรุปจาก AI CEO
    generated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    chairman_read   INTEGER NOT NULL DEFAULT 0  -- 1 = Chairman อ่านแล้ว
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_client_status    ON client_agents(status);
CREATE INDEX IF NOT EXISTS idx_client_prof      ON client_agents(profession);
CREATE INDEX IF NOT EXISTS idx_client_calls     ON client_agent_calls(agent_id);
CREATE INDEX IF NOT EXISTS idx_client_endpoint  ON client_agent_calls(endpoint);
CREATE INDEX IF NOT EXISTS idx_ceo_report_week  ON ceo_weekly_reports(week_period);
