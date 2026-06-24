"""
client_analytics_router.py — Phase 16: Analytics Endpoints
AI TO AI HOLDING — Customs Intelligence Division

GET /v1/client/analytics       — ลูกค้าเห็นข้อมูลตัวเอง (ต้องมี X-API-Key)
GET /v1/chairman/analytics/all — Chairman เห็นทุก client (IP-restricted via SecurityMiddleware)
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.security import APIKeyHeader

from db_adapter import get_pool
from client_analytics import get_client_analytics, get_all_clients_analytics

# ── Router ─────────────────────────────────────────────────────────────────────

router = APIRouter(tags=["Analytics"])
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _resolve_agent(api_key: str = Depends(API_KEY_HEADER)):
    """Authenticate client → return (api_key_hint, agent_id)"""
    if not api_key:
        raise HTTPException(status_code=401, detail="X-API-Key required")
    hint = api_key[-8:]
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM client_agents WHERE api_key_hint=$1 AND status='ACTIVE'",
            hint
        )
    if not row:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return hint, row["id"]


# ── Client Endpoint ────────────────────────────────────────────────────────────

@router.get("/v1/client/analytics", summary="สถิติการใช้งานของฉัน")
async def client_analytics(
    period: str = Query("all", regex="^(month|year|all)$",
                        description="ช่วงเวลา: month (30 วัน), year (365 วัน), all"),
    agent=Depends(_resolve_agent),
):
    """
    ดึงสถิติการใช้งานของลูกค้า:
    - จำนวน invoice / items classified
    - มูลค่ารวม / FTA savings
    - Credit balance & topup history
    - Top HS codes / countries
    - Monthly trend (6 เดือนล่าสุด)
    """
    hint, agent_id = agent
    pool = await get_pool()
    try:
        data = await get_client_analytics(pool, hint, agent_id, period)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics error: {str(e)[:120]}")
    return {"success": True, "data": data}


# ── Chairman Endpoint ──────────────────────────────────────────────────────────
# IP restriction handled by SecurityMiddleware (/v1/chairman/* prefix)

@router.get("/v1/chairman/analytics/all", summary="[Chairman] ภาพรวมทุก client")
async def chairman_analytics(
    period: str = Query("all", regex="^(month|year|all)$",
                        description="ช่วงเวลา: month, year, all"),
):
    """
    Chairman-only: ภาพรวม platform
    - จำนวน active clients / invoices / items
    - Revenue (credit topups)
    - FTA savings platform-wide
    - Per-client breakdown (top 20)
    - Monthly trend (12 เดือน)
    - Top HS codes
    """
    pool = await get_pool()
    try:
        data = await get_all_clients_analytics(pool, period)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics error: {str(e)[:120]}")
    return {"success": True, "data": data}
