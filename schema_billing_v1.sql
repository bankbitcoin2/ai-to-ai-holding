-- schema_billing_v1.sql — Billing System
-- ใช้ separate table แทน ALTER TABLE เพื่อหลีกเลี่ยง SQLite limitation

-- ตาราง credit balance แยกต่างหาก (1:1 กับ client_agents)
CREATE TABLE IF NOT EXISTS client_credits (
    agent_id            TEXT PRIMARY KEY REFERENCES client_agents(id),
    credit_balance      REAL DEFAULT 0.0,
    credit_topup_total  REAL DEFAULT 0.0,
    updated_at          TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- ตาราง topup transactions
CREATE TABLE IF NOT EXISTS credit_topups (
    id                      TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    agent_id                TEXT NOT NULL REFERENCES client_agents(id),
    amount_usd              REAL NOT NULL,
    stripe_session_id       TEXT,
    stripe_payment_intent   TEXT,
    status                  TEXT NOT NULL DEFAULT 'pending',
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    completed_at            TEXT
);

CREATE INDEX IF NOT EXISTS idx_topups_agent ON credit_topups(agent_id);
CREATE INDEX IF NOT EXISTS idx_topups_stripe ON credit_topups(stripe_session_id);
