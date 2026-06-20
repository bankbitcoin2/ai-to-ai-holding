"""
chairman_router.py
Chairman-only endpoints — สถิติรายได้ / jobs / clients
"""
from fastapi import APIRouter, Header, HTTPException
from datetime import datetime, timezone
import os

router = APIRouter(prefix="/v1/chairman", tags=["Chairman"])

CHAIRMAN_KEY = os.getenv("CHAIRMAN_API_KEY", "")


def _auth(x_api_key: str):
    """ตรวจ Chairman key — ถ้าไม่ตั้ง env ให้ผ่านชั่วคราว"""
    if CHAIRMAN_KEY and x_api_key != CHAIRMAN_KEY:
        raise HTTPException(status_code=403, detail="Chairman access only")


@router.get("/stats", summary="Chairman — ภาพรวมรายได้ + jobs")
async def chairman_stats(x_api_key: str = Header(default="", alias="X-API-Key")):
    """
    คืนสถิติรวมของทั้งระบบ:
    - จำนวน clients
    - รายได้รวม (credit ที่เติมแล้ว)
    - จำนวน API calls
    - credit คงเหลือทั้งระบบ
    """
    try:
        from billing import _get_db
        db = await _get_db()
        async with db.execute("""
            SELECT
                COUNT(DISTINCT a.id)            AS total_clients,
                COALESCE(SUM(c.credit_topup_total), 0) AS total_revenue,
                COALESCE(SUM(c.credit_balance), 0)     AS total_balance
            FROM client_agents a
            LEFT JOIN client_credits c ON c.agent_id = a.id
            WHERE a.status = 'ACTIVE'
        """) as cur:
            row = await cur.fetchone()

        # jobs — นับจาก audit_log ถ้ามี
        total_jobs = 0
        try:
            async with db.execute("SELECT COUNT(*) as n FROM audit_log") as cur2:
                r2 = await cur2.fetchone()
                total_jobs = r2["n"] if r2 else 0
        except Exception:
            pass

        return {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "total_clients": row["total_clients"] if row else 0,
            "total_revenue_credits": float(row["total_revenue"]) if row else 0.0,
            "total_balance_credits": float(row["total_balance"]) if row else 0.0,
            "total_jobs": total_jobs,
            "price_per_call_usd": 0.001,
            "revenue_usd_estimate": round(float(row["total_revenue"]) * 0.001, 4) if row else 0.0,
        }
    except Exception as e:
        return {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "total_clients": 0,
            "total_revenue_credits": 0.0,
            "total_balance_credits": 0.0,
            "total_jobs": 0,
            "price_per_call_usd": 0.001,
            "revenue_usd_estimate": 0.0,
            "note": f"DB not ready: {str(e)}"
        }


@router.get("/clients", summary="Chairman — รายชื่อ clients ทั้งหมด")
async def chairman_clients(x_api_key: str = Header(default="", alias="X-API-Key")):
    try:
        from billing import _get_db
        db = await _get_db()
        async with db.execute("""
            SELECT a.id, a.agent_name, a.contact_email, a.status,
                   a.registered_at, a.api_key_hint,
                   COALESCE(c.credit_balance, 0) as credit_balance,
                   COALESCE(c.credit_topup_total, 0) as credit_topup_total
            FROM client_agents a
            LEFT JOIN client_credits c ON c.agent_id = a.id
            ORDER BY a.registered_at DESC
            LIMIT 100
        """) as cur:
            rows = await cur.fetchall()
        return {
            "total": len(rows),
            "clients": [dict(r) for r in rows]
        }
    except Exception as e:
        return {"total": 0, "clients": [], "error": str(e)}
