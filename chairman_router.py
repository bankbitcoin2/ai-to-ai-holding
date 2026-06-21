"""
chairman_router.py - Chairman-only endpoints
"""
from fastapi import APIRouter, Header, HTTPException
from datetime import datetime, timezone
import os
import secrets

router = APIRouter(prefix="/v1/chairman", tags=["Chairman"])
CHAIRMAN_KEY = os.getenv("CHAIRMAN_API_KEY", "")


def _require_chairman_key(x_api_key: str) -> None:
    if CHAIRMAN_KEY and not secrets.compare_digest(x_api_key, CHAIRMAN_KEY):
        raise HTTPException(status_code=403, detail={
            "error": "CHAIRMAN_AUTH_FAILED",
            "message": "Chairman API key invalid",
            "constitution": "P-01: Chairman authority protected",
        })


@router.get("/stats", summary="Chairman revenue + jobs overview")
async def chairman_stats(x_api_key: str = Header(default="", alias="X-API-Key")):
    _require_chairman_key(x_api_key)
    from billing import _get_db
    db = await _get_db()
    try:
        async with db.execute(
            "SELECT COUNT(DISTINCT a.id) AS total_clients,"
            " COALESCE(SUM(c.credit_topup_total), 0) AS total_revenue,"
            " COALESCE(SUM(c.credit_balance), 0) AS total_balance"
            " FROM client_agents a"
            " LEFT JOIN client_credits c ON c.agent_id = a.id"
            " WHERE a.status = 'ACTIVE'"
        ) as cur:
            row = await cur.fetchone()

        total_jobs = 0
        try:
            async with db.execute("SELECT COUNT(*) as n FROM audit_events") as cur2:
                r2 = await cur2.fetchone()
                total_jobs = r2["n"] if r2 else 0
        except Exception:
            pass

        revenue = float(row["total_revenue"]) if row else 0.0
        from holding_config import PRICE_PER_ITEM
        return {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "total_clients": row["total_clients"] if row else 0,
            "total_revenue_usd": revenue,
            "total_balance_usd": float(row["total_balance"]) if row else 0.0,
            "total_jobs": total_jobs,
            "price_per_item_usd": PRICE_PER_ITEM,
            "revenue_usd_estimate": round(revenue, 2),
        }
    except Exception as e:
        return {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "total_clients": 0, "total_revenue_usd": 0.0,
            "total_balance_usd": 0.0, "total_jobs": 0,
            "price_per_item_usd": 1.50, "revenue_usd_estimate": 0.0,
            "note": "DB not ready: " + str(e),
        }
    finally:
        await db.close()


@router.get("/cache/stats", summary="Chairman HS cache statistics")
async def chairman_cache_stats(x_api_key: str = Header(default="", alias="X-API-Key")):
    _require_chairman_key(x_api_key)
    try:
        from cache_service import cache_stats
        stats = await cache_stats()
        saves = int(stats.get("cache_saves", 0))
        return {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "total_cached_entries": stats.get("total_entries", 0),
            "total_cache_hits": stats.get("total_hits", 0),
            "api_calls_saved": saves,
            "cost_saved_usd_estimate": round(saves * 0.002, 4),
        }
    except Exception as e:
        return {"error": str(e), "total_cached_entries": 0, "api_calls_saved": 0}


@router.get("/topups", summary="Chairman transaction history")
async def chairman_topups(
    limit: int = 50,
    x_api_key: str = Header(default="", alias="X-API-Key")
):
    _require_chairman_key(x_api_key)
    from billing import _get_db
    db = await _get_db()
    try:
        sql_topups = (
            "SELECT t.id, a.agent_name, a.contact_email,"
            " t.amount_usd, t.status, t.created_at, t.completed_at,"
            " t.stripe_session_id"
            " FROM credit_topups t"
            " LEFT JOIN client_agents a ON a.id = t.agent_id"
            " ORDER BY t.created_at DESC LIMIT $1"
        )
        async with db.execute(sql_topups, (limit,)) as cur:
            topup_rows = await cur.fetchall()

        sql_deducts = (
            "SELECT e.id, e.actor_id, e.action, e.occurred_at,"
            " a.agent_name"
            " FROM audit_events e"
            " LEFT JOIN client_agents a ON a.id = e.actor_id"
            " WHERE e.event_type = 'CREDIT_DEDUCT'"
            " ORDER BY e.occurred_at DESC LIMIT $1"
        )
        async with db.execute(sql_deducts, (limit,)) as cur2:
            deduct_rows = await cur2.fetchall()

        sql_daily = (
            "SELECT DATE(created_at) as day,"
            " COUNT(*) as txn_count,"
            " SUM(amount_usd) as total_usd"
            " FROM credit_topups"
            " WHERE status = 'completed'"
            " GROUP BY DATE(created_at)"
            " ORDER BY day DESC LIMIT 30"
        )
        async with db.execute(sql_daily) as cur3:
            daily_rows = await cur3.fetchall()

        return {
            "topups": [dict(r) for r in topup_rows],
            "deducts": [dict(r) for r in deduct_rows],
            "daily_summary": [dict(r) for r in daily_rows],
            "total_topup_count": len(topup_rows),
            "total_deduct_count": len(deduct_rows),
        }
    except Exception as e:
        return {"topups": [], "deducts": [], "daily_summary": [], "error": str(e)}
    finally:
        await db.close()


@router.get("/clients", summary="Chairman client list")
async def chairman_clients(x_api_key: str = Header(default="", alias="X-API-Key")):
    _require_chairman_key(x_api_key)
    from billing import _get_db
    db = await _get_db()
    try:
        async with db.execute(
            "SELECT a.id, a.agent_name, a.contact_email, a.status,"
            " a.registered_at, a.api_key_hint,"
            " COALESCE(c.credit_balance, 0) as credit_balance,"
            " COALESCE(c.credit_topup_total, 0) as credit_topup_total"
            " FROM client_agents a"
            " LEFT JOIN client_credits c ON c.agent_id = a.id"
            " ORDER BY a.registered_at DESC LIMIT 100"
        ) as cur:
            rows = await cur.fetchall()
        return {"total": len(rows), "clients": [dict(r) for r in rows]}
    except Exception as e:
        return {"total": 0, "clients": [], "error": str(e)}
    finally:
        await db.close()
