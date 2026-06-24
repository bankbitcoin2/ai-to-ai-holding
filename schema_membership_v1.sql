-- schema_membership_v1.sql — Phase 18: Membership Tier System
-- AI TO AI HOLDING — Customs Intelligence Division
--
-- Tiers: VIP → Gold → Platinum → Diamond → SuperPremium
-- Auto-calculate จาก usage data monthly
-- Discount apply ตอนหัก credit

-- ─── Membership Tier Definitions ──────────────────────────────────────────────
-- ตาราง reference: ไม่ค่อยเปลี่ยน — seed ตอน init

CREATE TABLE IF NOT EXISTS membership_tiers (
    tier_level          TEXT PRIMARY KEY,        -- VIP, GOLD, PLATINUM, DIAMOND, SUPER_PREMIUM
    display_name        TEXT NOT NULL,
    display_name_th     TEXT NOT NULL,
    rank_order          INT NOT NULL,            -- 1=VIP, 2=GOLD, ... 5=SUPER_PREMIUM
    min_queries_month   INT NOT NULL DEFAULT 0,  -- minimum queries/month to qualify
    min_trade_value_thb NUMERIC(18,2) DEFAULT 0, -- minimum trade value THB/month
    discount_pct        NUMERIC(5,2) DEFAULT 0,  -- ส่วนลด API (0.05 = 5%)
    rate_limit_boost    INT DEFAULT 0,           -- เพิ่ม rate limit (requests/min)
    features            JSONB,                   -- สิทธิพิเศษเพิ่มเติม
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Seed tier definitions
INSERT INTO membership_tiers (tier_level, display_name, display_name_th, rank_order,
    min_queries_month, min_trade_value_thb, discount_pct, rate_limit_boost, features)
VALUES
    ('VIP', 'VIP', 'สมาชิก VIP', 1,
     0, 0, 0.00, 0,
     '{"access": "basic", "support": "community", "xai_detail": "standard"}'),
    ('GOLD', 'Gold', 'สมาชิก Gold', 2,
     100, 100000, 0.05, 5,
     '{"access": "priority_queue", "support": "email", "xai_detail": "standard"}'),
    ('PLATINUM', 'Platinum', 'สมาชิก Platinum', 3,
     500, 500000, 0.10, 15,
     '{"access": "priority_queue", "support": "dedicated", "xai_detail": "detailed"}'),
    ('DIAMOND', 'Diamond', 'สมาชิก Diamond', 4,
     2000, 2000000, 0.15, 30,
     '{"access": "custom_rules", "support": "dedicated_24h", "xai_detail": "detailed", "custom_normalize": true}'),
    ('SUPER_PREMIUM', 'SuperPremium', 'สมาชิก SuperPremium', 5,
     10000, 10000000, 0.20, 60,
     '{"access": "white_label", "support": "dedicated_24h", "xai_detail": "full_audit", "custom_normalize": true, "audit_report": true}')
ON CONFLICT (tier_level) DO NOTHING;

-- ─── Client Current Tier ──────────────────────────────────────────────────────
-- เพิ่ม column ใน client_agents (ใช้ separate table เพื่อไม่ ALTER ตาราง production)

CREATE TABLE IF NOT EXISTS client_membership (
    agent_id            TEXT PRIMARY KEY REFERENCES client_agents(id),
    tier_level          TEXT NOT NULL DEFAULT 'VIP' REFERENCES membership_tiers(tier_level),
    tier_since          TIMESTAMPTZ DEFAULT NOW(),
    queries_this_month  INT DEFAULT 0,
    trade_value_month   NUMERIC(18,2) DEFAULT 0,  -- THB
    last_evaluated      TIMESTAMPTZ,
    next_evaluation     TIMESTAMPTZ,
    manual_override     BOOLEAN DEFAULT FALSE,     -- Chairman set tier manually
    override_reason     TEXT,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_membership_tier ON client_membership(tier_level);

-- ─── Tier History ─────────────────────────────────────────────────────────────
-- บันทึกทุกครั้งที่ tier เปลี่ยน

CREATE TABLE IF NOT EXISTS client_tier_history (
    id                  TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    agent_id            TEXT NOT NULL REFERENCES client_agents(id),
    old_tier            TEXT REFERENCES membership_tiers(tier_level),
    new_tier            TEXT NOT NULL REFERENCES membership_tiers(tier_level),
    reason              TEXT NOT NULL,             -- AUTO_UPGRADE, AUTO_DOWNGRADE, MANUAL, INITIAL
    queries_at_change   INT DEFAULT 0,
    trade_value_at_change NUMERIC(18,2) DEFAULT 0,
    changed_at          TIMESTAMPTZ DEFAULT NOW(),
    changed_by          TEXT DEFAULT 'SYSTEM'      -- SYSTEM or CHAIRMAN
);

CREATE INDEX IF NOT EXISTS idx_tier_history_agent ON client_tier_history(agent_id);
CREATE INDEX IF NOT EXISTS idx_tier_history_date ON client_tier_history(changed_at DESC);
