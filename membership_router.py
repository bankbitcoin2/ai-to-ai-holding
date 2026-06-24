"""
membership_router.py — Phase 18: Membership Tier Endpoints
AI TO AI HOLDING — Customs Intelligence Division

Client:
  GET  /v1/client/membership              — ดู tier + progress ไป tier ถัดไป

Chairman:
  GET  /v1/chairman/membership/all        — ดู tier ทุก client
  POST /v1/chairman/membership/evaluate   — re-evaluate ทุก client
  POST /v1/chairman/membership/set-tier   — override tier ด้วยมือ
  POST /v1/chairman/membership/reset      — reset monthly counters
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from db_adapter import get_pool
from membership_engine import (
    get_client_membership, evaluate_all_clients,
    set_tier_manual, reset_monthly_counters,
    ensure_membership, TIER_THRESHOLDS, TIER_RANK,
)

router = APIRouter(tags=["Membership"])
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _resolve_agent(api_key: str = Depends(API_KEY_HEADER)):
    """Authenticate → return agent_id"""
    if not api_key:
        raise HTTPException(401, "X-API-Key required")
    hint = api_key[-8:]
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM client_agents WHERE api_key_hint=$1 AND status='ACTIVE'",
            hint
        )
    if not row:
        raise HTTPException(401, "Invalid API Key")
    return row["id"]


# ── Client Endpoint ────────────────────────────────────────────────────────────

@router.get("/v1/client/membership", summary="ดู membership tier ของฉัน")
async def client_membership(agent_id: str = Depends(_resolve_agent)):
    """
    แสดง tier ปัจจุบัน, discount, progress ไป tier ถัดไป
    """
    pool = await get_pool()
    await ensure_membership(pool, agent_id)
    data = await get_client_membership(pool, agent_id)
    return {"success": True, "data": data}


# ── Chairman Endpoints ─────────────────────────────────────────────────────────
# IP restriction via SecurityMiddleware (/v1/chairman/*)

@router.get("/v1/chairman/membership/all", summary="[Chairman] ดู tier ทุก client",
            include_in_schema=False)
async def chairman_all_membership():
    """ดึง membership ทุก client พร้อม tier + usage"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT ca.agent_name, ca.contact_email, ca.profession,
                   COALESCE(cm.tier_level, 'VIP') AS tier_level,
                   COALESCE(cm.queries_this_month, 0) AS queries_month,
                   COALESCE(cm.trade_value_month, 0) AS trade_value_month,
                   cm.tier_since, cm.manual_override, cm.last_evaluated,
                   COALESCE(cc.credit_balance, 0) AS credit_balance
            FROM client_agents ca
            LEFT JOIN client_membership cm ON cm.agent_id = ca.id
            LEFT JOIN client_credits cc ON cc.agent_id = ca.id
            WHERE ca.status = 'ACTIVE'
            ORDER BY COALESCE(cm.queries_this_month, 0) DESC
        """)

    # Tier summary
    tier_counts = {}
    for r in rows:
        t = r["tier_level"]
        tier_counts[t] = tier_counts.get(t, 0) + 1

    return {
        "success": True,
        "summary": {
            "total_clients": len(rows),
            "tier_distribution": tier_counts,
        },
        "clients": [
            {
                "agent_name": r["agent_name"],
                "email": r["contact_email"],
                "profession": r["profession"],
                "tier": r["tier_level"],
                "queries_month": r["queries_month"],
                "trade_value_month": float(r["trade_value_month"]),
                "credit_balance": float(r["credit_balance"]),
                "tier_since": str(r["tier_since"] or ""),
                "manual_override": bool(r["manual_override"]) if r["manual_override"] is not None else False,
            }
            for r in rows
        ],
    }


@router.post("/v1/chairman/membership/evaluate",
             summary="[Chairman] Re-evaluate tier ทุก client",
             include_in_schema=False)
async def chairman_evaluate():
    """คำนวณ tier ใหม่จาก usage data — upgrade/downgrade อัตโนมัติ"""
    pool = await get_pool()
    result = await evaluate_all_clients(pool)
    return {"success": True, "data": result}


class SetTierRequest(BaseModel):
    agent_id: str = Field(..., description="Agent ID ที่ต้องการ override")
    tier_level: str = Field(..., description="VIP / GOLD / PLATINUM / DIAMOND / SUPER_PREMIUM")
    reason: str = Field(default="", description="เหตุผลที่ override")


@router.post("/v1/chairman/membership/set-tier",
             summary="[Chairman] Override tier ด้วยมือ",
             include_in_schema=False)
async def chairman_set_tier(req: SetTierRequest):
    """ตั้ง tier ด้วยมือ — ลูกค้าจะไม่ถูก auto-evaluate จนกว่าจะปลด override"""
    pool = await get_pool()
    result = await set_tier_manual(pool, req.agent_id, req.tier_level, req.reason)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return {"success": True, "data": result}


@router.post("/v1/chairman/membership/reset",
             summary="[Chairman] Reset monthly counters",
             include_in_schema=False)
async def chairman_reset_counters():
    """รีเซ็ต queries_this_month + trade_value_month (เรียกต้นเดือน)"""
    pool = await get_pool()
    count = await reset_monthly_counters(pool)
    return {"success": True, "reset_count": count,
            "note": "เรียก /evaluate หลัง reset เพื่อ re-calculate tiers"}
