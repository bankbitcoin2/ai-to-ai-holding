"""
membership_engine.py — Phase 18: Membership Tier System
AI TO AI HOLDING — Customs Intelligence Division

Tiers (ascending):
  VIP            — สมัคร + เติม credit (default)
  GOLD           — ≥100 queries/mo หรือ ≥฿100K trade value
  PLATINUM       — ≥500 queries/mo หรือ ≥฿500K
  DIAMOND        — ≥2,000 queries/mo หรือ ≥฿2M
  SUPER_PREMIUM  — ≥10,000 queries/mo หรือ ≥฿10M

Engine:
  1. evaluate_tier()     — คำนวณ tier จาก usage data
  2. ensure_membership() — สร้าง membership record ถ้ายังไม่มี
  3. get_discount()      — ดึง discount % สำหรับ billing
  4. evaluate_all()      — Chairman: re-evaluate ทุก client (monthly cron)
  5. set_tier_manual()   — Chairman: override tier
"""

from datetime import datetime, timezone
from typing import Optional

# Tier thresholds (matching schema_membership_v1.sql seed)
TIER_THRESHOLDS = [
    # (tier_level, min_queries, min_trade_thb, discount)
    ("SUPER_PREMIUM", 10000, 10_000_000, 0.20),
    ("DIAMOND",        2000,  2_000_000, 0.15),
    ("PLATINUM",        500,    500_000, 0.10),
    ("GOLD",            100,    100_000, 0.05),
    ("VIP",               0,          0, 0.00),
]

TIER_RANK = {
    "VIP": 1, "GOLD": 2, "PLATINUM": 3, "DIAMOND": 4, "SUPER_PREMIUM": 5
}


# ── Core: Evaluate Tier ────────────────────────────────────────────────────────

def calculate_tier(queries_month: int, trade_value_thb: float) -> str:
    """
    คำนวณ tier ที่เหมาะสมจาก usage data
    เงื่อนไข: queries >= threshold OR trade_value >= threshold → ได้ tier นั้น
    """
    for tier, min_q, min_v, _ in TIER_THRESHOLDS:
        if queries_month >= min_q or trade_value_thb >= min_v:
            return tier
    return "VIP"


def get_tier_discount(tier_level: str) -> float:
    """คืน discount % (0.0 - 0.20) ตาม tier"""
    for t, _, _, disc in TIER_THRESHOLDS:
        if t == tier_level.upper():
            return disc
    return 0.0


def get_tier_info(tier_level: str) -> dict:
    """คืนรายละเอียด tier"""
    for t, min_q, min_v, disc in TIER_THRESHOLDS:
        if t == tier_level.upper():
            return {
                "tier": t,
                "rank": TIER_RANK.get(t, 0),
                "min_queries_month": min_q,
                "min_trade_value_thb": min_v,
                "discount_pct": disc,
            }
    return {"tier": "VIP", "rank": 1, "min_queries_month": 0,
            "min_trade_value_thb": 0, "discount_pct": 0.0}


# ── DB Operations ──────────────────────────────────────────────────────────────

async def ensure_membership(pool, agent_id: str) -> dict:
    """สร้าง membership record ถ้ายังไม่มี — คืน current membership"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM client_membership WHERE agent_id = $1", agent_id
        )
        if row:
            return dict(row)

        # สร้างใหม่ — default VIP
        now = datetime.now(timezone.utc).isoformat()
        await conn.execute("""
            INSERT INTO client_membership
              (agent_id, tier_level, tier_since, queries_this_month,
               trade_value_month, last_evaluated, next_evaluation, updated_at)
            VALUES ($1, 'VIP', $2, 0, 0, $2, $2, $2)
            ON CONFLICT (agent_id) DO NOTHING
        """, agent_id, now)

        # Log initial tier
        await _log_tier_change(conn, agent_id, None, "VIP", "INITIAL", 0, 0)

        return {
            "agent_id": agent_id, "tier_level": "VIP",
            "queries_this_month": 0, "trade_value_month": 0,
            "manual_override": False,
        }


async def get_client_membership(pool, agent_id: str) -> dict:
    """ดึง membership info พร้อม progress ไป tier ถัดไป"""
    mem = await ensure_membership(pool, agent_id)
    tier = mem.get("tier_level", "VIP") if isinstance(mem, dict) else mem["tier_level"]
    queries = int(mem.get("queries_this_month", 0) or 0)
    trade_val = float(mem.get("trade_value_month", 0) or 0)
    discount = get_tier_discount(tier)

    # หา next tier + progress
    current_rank = TIER_RANK.get(tier, 1)
    next_tier = None
    progress = None

    for t, min_q, min_v, _ in reversed(TIER_THRESHOLDS):
        if TIER_RANK.get(t, 0) == current_rank + 1:
            next_tier = t
            # Progress = max(query_progress, value_progress)
            q_pct = min(queries / max(min_q, 1) * 100, 100) if min_q > 0 else 100
            v_pct = min(trade_val / max(min_v, 1) * 100, 100) if min_v > 0 else 100
            progress = {
                "next_tier": t,
                "queries_progress_pct": round(max(q_pct, 0), 1),
                "queries_current": queries,
                "queries_needed": min_q,
                "trade_value_progress_pct": round(max(v_pct, 0), 1),
                "trade_value_current": trade_val,
                "trade_value_needed": min_v,
                "note": "ต้องผ่านเงื่อนไข queries หรือ trade value อย่างใดอย่างหนึ่ง",
            }
            break

    return {
        "agent_id": agent_id,
        "tier": tier,
        "tier_display": tier.replace("_", " ").title(),
        "rank": current_rank,
        "discount_pct": discount,
        "queries_this_month": queries,
        "trade_value_month_thb": trade_val,
        "manual_override": bool(mem.get("manual_override", False)),
        "tier_since": str(mem.get("tier_since", "")),
        "next_tier_progress": progress,
    }


async def increment_usage(pool, agent_id: str, item_count: int,
                          trade_value_thb: float = 0) -> None:
    """เพิ่ม usage counter หลัง process invoice — เรียกจาก invoice_service"""
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE client_membership
                SET queries_this_month = queries_this_month + $2,
                    trade_value_month = trade_value_month + $3,
                    updated_at = $4
                WHERE agent_id = $1
            """, agent_id, item_count, trade_value_thb,
                datetime.now(timezone.utc).isoformat())
    except Exception as e:
        print(f"[MEMBERSHIP] increment_usage error: {e}")


async def evaluate_tier_for_client(pool, agent_id: str) -> dict:
    """
    Re-evaluate tier สำหรับ client คนเดียว
    คืน: {"changed": bool, "old": str, "new": str}
    """
    async with pool.acquire() as conn:
        mem = await conn.fetchrow(
            "SELECT * FROM client_membership WHERE agent_id = $1", agent_id
        )
        if not mem:
            await ensure_membership(pool, agent_id)
            return {"changed": False, "old": "VIP", "new": "VIP"}

        # ถ้า manual override — ไม่เปลี่ยน
        if mem["manual_override"]:
            return {"changed": False, "old": mem["tier_level"],
                    "new": mem["tier_level"], "reason": "manual_override"}

        old_tier = mem["tier_level"]
        queries = int(mem["queries_this_month"] or 0)
        trade_val = float(mem["trade_value_month"] or 0)

        new_tier = calculate_tier(queries, trade_val)

        now = datetime.now(timezone.utc).isoformat()
        if new_tier != old_tier:
            old_rank = TIER_RANK.get(old_tier, 1)
            new_rank = TIER_RANK.get(new_tier, 1)
            reason = "AUTO_UPGRADE" if new_rank > old_rank else "AUTO_DOWNGRADE"

            await conn.execute("""
                UPDATE client_membership
                SET tier_level = $2, tier_since = $3, last_evaluated = $3, updated_at = $3
                WHERE agent_id = $1
            """, agent_id, new_tier, now)

            await _log_tier_change(conn, agent_id, old_tier, new_tier,
                                   reason, queries, trade_val)

            return {"changed": True, "old": old_tier, "new": new_tier, "reason": reason}

        # ไม่เปลี่ยน — update last_evaluated
        await conn.execute(
            "UPDATE client_membership SET last_evaluated = $2 WHERE agent_id = $1",
            agent_id, now
        )
        return {"changed": False, "old": old_tier, "new": old_tier}


async def evaluate_all_clients(pool) -> dict:
    """
    Chairman: re-evaluate ทุก client — เรียกเดือนละครั้ง
    คืน summary: upgrades, downgrades, unchanged
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT agent_id FROM client_membership WHERE manual_override = FALSE"
        )

    upgrades = []
    downgrades = []
    unchanged = 0

    for row in rows:
        result = await evaluate_tier_for_client(pool, row["agent_id"])
        if result["changed"]:
            entry = {"agent_id": row["agent_id"],
                     "old": result["old"], "new": result["new"]}
            if result.get("reason") == "AUTO_UPGRADE":
                upgrades.append(entry)
            else:
                downgrades.append(entry)
        else:
            unchanged += 1

    return {
        "evaluated": len(rows),
        "upgrades": upgrades,
        "downgrades": downgrades,
        "unchanged": unchanged,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }


async def reset_monthly_counters(pool) -> int:
    """
    รีเซ็ต queries_this_month + trade_value_month ทุกต้นเดือน
    เรียกก่อน evaluate_all_clients
    คืน: จำนวน records ที่ reset
    """
    async with pool.acquire() as conn:
        result = await conn.execute("""
            UPDATE client_membership
            SET queries_this_month = 0,
                trade_value_month = 0,
                updated_at = $1
        """, datetime.now(timezone.utc).isoformat())
        # asyncpg returns "UPDATE N"
        count = int(result.split()[-1]) if result else 0
    return count


async def set_tier_manual(pool, agent_id: str, tier_level: str,
                          reason: str = "") -> dict:
    """Chairman: override tier ด้วยมือ"""
    tier_level = tier_level.upper()
    if tier_level not in TIER_RANK:
        return {"error": f"Invalid tier: {tier_level}"}

    async with pool.acquire() as conn:
        mem = await conn.fetchrow(
            "SELECT tier_level FROM client_membership WHERE agent_id = $1", agent_id
        )
        if not mem:
            await ensure_membership(pool, agent_id)
            mem = {"tier_level": "VIP"}

        old_tier = mem["tier_level"]
        now = datetime.now(timezone.utc).isoformat()

        await conn.execute("""
            UPDATE client_membership
            SET tier_level = $2, tier_since = $3, manual_override = TRUE,
                override_reason = $4, last_evaluated = $3, updated_at = $3
            WHERE agent_id = $1
        """, agent_id, tier_level, now, reason or "Chairman manual override")

        await _log_tier_change(conn, agent_id, old_tier, tier_level,
                               "MANUAL", 0, 0, changed_by="CHAIRMAN")

    return {"success": True, "old": old_tier, "new": tier_level, "manual_override": True}


# ── Get Discount for Billing ───────────────────────────────────────────────────

async def get_discount_for_agent(pool, agent_id: str) -> float:
    """
    ดึง discount % สำหรับ agent — ใช้ใน invoice_service._deduct_credit
    คืน 0.0 - 0.20
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT tier_level FROM client_membership WHERE agent_id = $1",
                agent_id
            )
        if row:
            return get_tier_discount(row["tier_level"])
    except Exception:
        pass
    return 0.0


# ── Internal ───────────────────────────────────────────────────────────────────

async def _log_tier_change(conn, agent_id: str, old_tier: Optional[str],
                           new_tier: str, reason: str,
                           queries: int, trade_val: float,
                           changed_by: str = "SYSTEM") -> None:
    """บันทึก tier change history"""
    try:
        import uuid
        await conn.execute("""
            INSERT INTO client_tier_history
              (id, agent_id, old_tier, new_tier, reason,
               queries_at_change, trade_value_at_change, changed_at, changed_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """, str(uuid.uuid4()), agent_id, old_tier, new_tier, reason,
            queries, trade_val,
            datetime.now(timezone.utc).isoformat(), changed_by)
    except Exception as e:
        print(f"[MEMBERSHIP] log error: {e}")
