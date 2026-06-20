-- schema_billing_v1.sql — Billing System
-- รัน: sqlite3 holding.db < schema_billing_v1.sql

-- เพิ่ม credit_balance ใน client_agents (ถ้ายังไม่มี)
ALTER TABLE client_agents ADD COLUMN credit_balance REAL NOT NULL DEFAULT 0.0;
ALTER TABLE client_agents ADD COLUMN credit_topup_total REAL NOT NULL DEFAULT 0.0;

-- ตาราง topup transactions
CREATE TABLE IF NOT EXISTS credit_topups (
    id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    agent_id        TEXT NOT NULL REFERENCES client_agents(id),
    amount_usd      REAL NOT NULL,
    stripe_session_id TEXT,
    stripe_payment_intent TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','completed','failed','refunded')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    completed_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_topups_agent ON credit_topups(agent_id);
CREATE INDEX IF NOT EXISTS idx_topups_stripe ON credit_topups(stripe_session_id);
