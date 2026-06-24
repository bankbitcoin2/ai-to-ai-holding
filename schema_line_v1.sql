-- schema_line_v1.sql — Phase 19: LINE OA Integration
-- AI TO AI HOLDING — Customs Intelligence Division

-- ─── LINE User ↔ Agent Binding ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS client_line_binding (
    line_user_id        TEXT PRIMARY KEY,         -- LINE userId (U + 32 hex)
    agent_id            TEXT NOT NULL REFERENCES client_agents(id),
    api_key_hint        TEXT NOT NULL,             -- last 8 chars of API key
    line_display_name   TEXT,                      -- ชื่อที่แสดงใน LINE (optional)
    bound_at            TIMESTAMPTZ DEFAULT NOW(),
    last_used_at        TIMESTAMPTZ,
    total_queries       INT DEFAULT 0,
    status              TEXT DEFAULT 'ACTIVE'      -- ACTIVE / SUSPENDED
);

CREATE INDEX IF NOT EXISTS idx_line_agent ON client_line_binding(agent_id);

-- ─── LINE Message Log (สำหรับ debug + analytics) ──────────────────────────────

CREATE TABLE IF NOT EXISTS line_message_log (
    id                  TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    line_user_id        TEXT NOT NULL,
    message_type        TEXT NOT NULL,             -- text / image / file
    message_id          TEXT,                      -- LINE message ID
    action              TEXT,                      -- CLASSIFY / BIND / STATUS / HELP
    submission_id       TEXT,                      -- ถ้าเป็น invoice → link ไป invoice_submissions
    success             BOOLEAN DEFAULT TRUE,
    error_msg           TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_line_log_user ON line_message_log(line_user_id);
CREATE INDEX IF NOT EXISTS idx_line_log_date ON line_message_log(created_at DESC);
