"""
client_analytics.py — Phase 16: Customer Analytics Dashboard
AI TO AI HOLDING — Customs Intelligence Division

Query engine สำหรับดึงข้อมูลการใช้งานของลูกค้า:
- Invoice count, total value, FTA savings
- Credit topup vs usage
- Items classified, top HS codes
- Country breakdown

Endpoints:
  GET /v1/client/analytics      — ลูกค้าเห็นข้อมูลตัวเอง
  GET /v1/chairman/analytics/all — Chairman เห็นทุก client
"""

from datetime import datetime, timezone
from typing import Optional


# ── Client Self-Analytics ──────────────────────────────────────────────────────

async def get_client_analytics(pool, api_key_hint: str, agent_id: str,
                               period: str = "all") -> dict:
    """
    ดึง analytics สำหรับ client คนเดียว
    period: "month" (30 วัน), "year" (365 วัน), "all"
    """
    date_filter = _build_date_filter(period)

    async with pool.acquire() as conn:
        # 1. Invoice summary
        inv = await conn.fetchrow(f"""
            SELECT
                COUNT(*)                        AS invoice_count,
                COALESCE(SUM(item_count), 0)    AS total_items,
                COALESCE(SUM(total_value), 0)   AS total_value,
                MIN(created_at)                 AS first_invoice,
                MAX(created_at)                 AS last_invoice
            FROM invoice_submissions
            WHERE RIGHT(client_api_key, 8) = $1
              AND status IN ('DONE', 'PROCESSING')
              {date_filter}
        """, api_key_hint)

        # 2. Item-level stats: FTA savings, duty, confidence
        items = await conn.fetchrow(f"""
            SELECT
                COUNT(*)                                AS classified_items,
                COALESCE(SUM(ii.fta_saving_usd), 0)    AS total_fta_saving,
                COALESCE(SUM(ii.duty_estimate_usd), 0) AS total_duty_estimate,
                COALESCE(AVG(ii.confidence), 0)         AS avg_confidence,
                COUNT(*) FILTER (WHERE ii.fta_eligible) AS fta_eligible_items,
                COUNT(*) FILTER (WHERE ii.oga_required) AS oga_required_items,
                COUNT(*) FILTER (WHERE ii.valuation_flag) AS valuation_flagged
            FROM invoice_items ii
            JOIN invoice_submissions s ON s.id = ii.submission_id
            WHERE RIGHT(s.client_api_key, 8) = $1
              {date_filter.replace("created_at", "s.created_at")}
        """, api_key_hint)

        # 3. Credit balance + topup history
        credit = await conn.fetchrow("""
            SELECT
                COALESCE(credit_balance, 0)      AS credit_balance,
                COALESCE(credit_topup_total, 0)  AS credit_topup_total
            FROM client_credits
            WHERE agent_id = $1
        """, agent_id)

        topup_count = await conn.fetchval("""
            SELECT COUNT(*) FROM credit_topups
            WHERE agent_id = $1 AND status = 'completed'
        """, agent_id)

        # 4. Top 5 HS codes used
        top_hs = await conn.fetch(f"""
            SELECT
                ii.hs_code_ai           AS hs_code,
                COUNT(*)                AS usage_count,
                COALESCE(SUM(ii.line_value), 0) AS total_value
            FROM invoice_items ii
            JOIN invoice_submissions s ON s.id = ii.submission_id
            WHERE RIGHT(s.client_api_key, 8) = $1
              AND ii.hs_code_ai IS NOT NULL
              {date_filter.replace("created_at", "s.created_at")}
            GROUP BY ii.hs_code_ai
            ORDER BY usage_count DESC
            LIMIT 5
        """, api_key_hint)

        # 5. Top origin countries
        top_countries = await conn.fetch(f"""
            SELECT
                ii.country_origin       AS country,
                COUNT(*)                AS item_count,
                COALESCE(SUM(ii.line_value), 0) AS total_value
            FROM invoice_items ii
            JOIN invoice_submissions s ON s.id = ii.submission_id
            WHERE RIGHT(s.client_api_key, 8) = $1
              AND ii.country_origin IS NOT NULL
              {date_filter.replace("created_at", "s.created_at")}
            GROUP BY ii.country_origin
            ORDER BY item_count DESC
            LIMIT 5
        """, api_key_hint)

        # 6. Monthly trend (last 6 months)
        monthly = await conn.fetch("""
            SELECT
                TO_CHAR(created_at, 'YYYY-MM')  AS month,
                COUNT(*)                         AS invoice_count,
                COALESCE(SUM(item_count), 0)     AS item_count,
                COALESCE(SUM(total_value), 0)    AS total_value
            FROM invoice_submissions
            WHERE RIGHT(client_api_key, 8) = $1
              AND status IN ('DONE', 'PROCESSING')
              AND created_at >= NOW() - INTERVAL '6 months'
            GROUP BY TO_CHAR(created_at, 'YYYY-MM')
            ORDER BY month DESC
        """, api_key_hint)

    return {
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "invoices": {
            "count": inv["invoice_count"],
            "total_items": inv["total_items"],
            "total_value_usd": float(inv["total_value"]),
            "first_invoice": inv["first_invoice"].isoformat() if inv["first_invoice"] else None,
            "last_invoice": inv["last_invoice"].isoformat() if inv["last_invoice"] else None,
        },
        "classification": {
            "classified_items": items["classified_items"],
            "avg_confidence": round(float(items["avg_confidence"]), 4),
            "fta_eligible_items": items["fta_eligible_items"],
            "oga_required_items": items["oga_required_items"],
            "valuation_flagged": items["valuation_flagged"],
        },
        "savings": {
            "total_fta_saving_usd": float(items["total_fta_saving"]),
            "total_duty_estimate_usd": float(items["total_duty_estimate"]),
        },
        "credits": {
            "balance_usd": float(credit["credit_balance"]) if credit else 0.0,
            "topup_total_usd": float(credit["credit_topup_total"]) if credit else 0.0,
            "topup_count": topup_count or 0,
        },
        "top_hs_codes": [
            {"hs_code": r["hs_code"], "count": r["usage_count"],
             "value_usd": float(r["total_value"])}
            for r in top_hs
        ],
        "top_countries": [
            {"country": r["country"], "items": r["item_count"],
             "value_usd": float(r["total_value"])}
            for r in top_countries
        ],
        "monthly_trend": [
            {"month": r["month"], "invoices": r["invoice_count"],
             "items": r["item_count"], "value_usd": float(r["total_value"])}
            for r in monthly
        ],
    }


# ── Chairman: All-Clients Overview ─────────────────────────────────────────────

async def get_all_clients_analytics(pool, period: str = "all") -> dict:
    """Chairman view: summary ของทุก client"""
    date_filter = _build_date_filter(period)

    async with pool.acquire() as conn:
        # 1. Platform totals
        totals = await conn.fetchrow(f"""
            SELECT
                COUNT(DISTINCT RIGHT(client_api_key, 8)) AS active_clients,
                COUNT(*)                        AS total_invoices,
                COALESCE(SUM(item_count), 0)    AS total_items,
                COALESCE(SUM(total_value), 0)   AS total_value
            FROM invoice_submissions
            WHERE status IN ('DONE', 'PROCESSING')
              {date_filter}
        """)

        # 2. FTA savings platform-wide
        savings = await conn.fetchrow(f"""
            SELECT
                COALESCE(SUM(ii.fta_saving_usd), 0)    AS total_fta_saving,
                COALESCE(SUM(ii.duty_estimate_usd), 0) AS total_duty_estimate,
                COUNT(*) FILTER (WHERE ii.fta_eligible) AS fta_items,
                COALESCE(AVG(ii.confidence), 0)         AS avg_confidence
            FROM invoice_items ii
            JOIN invoice_submissions s ON s.id = ii.submission_id
            WHERE s.status IN ('DONE', 'PROCESSING')
              {date_filter.replace("created_at", "s.created_at")}
        """)

        # 3. Revenue: total credit topups
        revenue = await conn.fetchrow("""
            SELECT
                COALESCE(SUM(amount_usd), 0) AS total_topup,
                COUNT(*)                     AS topup_count,
                COUNT(DISTINCT agent_id)     AS paying_clients
            FROM credit_topups
            WHERE status = 'completed'
        """)

        # 4. Per-client breakdown (top 20 by invoice count)
        clients = await conn.fetch(f"""
            SELECT
                ca.agent_name,
                ca.profession,
                ca.contact_email,
                ca.registered_at,
                COUNT(s.id)                         AS invoice_count,
                COALESCE(SUM(s.item_count), 0)      AS item_count,
                COALESCE(SUM(s.total_value), 0)     AS total_value,
                COALESCE(cc.credit_balance, 0)       AS credit_balance,
                COALESCE(cc.credit_topup_total, 0)   AS credit_topup
            FROM client_agents ca
            LEFT JOIN invoice_submissions s
                ON RIGHT(s.client_api_key, 8) = ca.api_key_hint
                AND s.status IN ('DONE', 'PROCESSING')
                {date_filter.replace("created_at", "s.created_at").replace("AND", "AND") if date_filter else ""}
            LEFT JOIN client_credits cc ON cc.agent_id = ca.id
            WHERE ca.status = 'ACTIVE'
            GROUP BY ca.id, ca.agent_name, ca.profession, ca.contact_email,
                     ca.registered_at, cc.credit_balance, cc.credit_topup_total
            ORDER BY invoice_count DESC
            LIMIT 20
        """)

        # 5. Monthly platform trend (last 12 months)
        monthly = await conn.fetch("""
            SELECT
                TO_CHAR(created_at, 'YYYY-MM')  AS month,
                COUNT(DISTINCT RIGHT(client_api_key, 8)) AS active_clients,
                COUNT(*)                         AS invoice_count,
                COALESCE(SUM(item_count), 0)     AS item_count,
                COALESCE(SUM(total_value), 0)    AS total_value
            FROM invoice_submissions
            WHERE status IN ('DONE', 'PROCESSING')
              AND created_at >= NOW() - INTERVAL '12 months'
            GROUP BY TO_CHAR(created_at, 'YYYY-MM')
            ORDER BY month DESC
        """)

        # 6. Top HS codes platform-wide
        top_hs = await conn.fetch(f"""
            SELECT
                ii.hs_code_ai       AS hs_code,
                COUNT(*)            AS usage_count,
                COUNT(DISTINCT RIGHT(s.client_api_key, 8)) AS client_count
            FROM invoice_items ii
            JOIN invoice_submissions s ON s.id = ii.submission_id
            WHERE ii.hs_code_ai IS NOT NULL
              AND s.status IN ('DONE', 'PROCESSING')
              {date_filter.replace("created_at", "s.created_at")}
            GROUP BY ii.hs_code_ai
            ORDER BY usage_count DESC
            LIMIT 10
        """)

    return {
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": {
            "active_clients": totals["active_clients"],
            "total_invoices": totals["total_invoices"],
            "total_items": totals["total_items"],
            "total_value_usd": float(totals["total_value"]),
            "avg_confidence": round(float(savings["avg_confidence"]), 4),
        },
        "savings": {
            "total_fta_saving_usd": float(savings["total_fta_saving"]),
            "total_duty_estimate_usd": float(savings["total_duty_estimate"]),
            "fta_eligible_items": savings["fta_items"],
        },
        "revenue": {
            "total_topup_usd": float(revenue["total_topup"]),
            "topup_count": revenue["topup_count"],
            "paying_clients": revenue["paying_clients"],
        },
        "clients": [
            {
                "agent_name": r["agent_name"],
                "profession": r["profession"],
                "email": r["contact_email"],
                "registered": r["registered_at"],
                "invoices": r["invoice_count"],
                "items": r["item_count"],
                "value_usd": float(r["total_value"]),
                "credit_balance": float(r["credit_balance"]),
                "credit_topup": float(r["credit_topup"]),
            }
            for r in clients
        ],
        "monthly_trend": [
            {"month": r["month"], "active_clients": r["active_clients"],
             "invoices": r["invoice_count"], "items": r["item_count"],
             "value_usd": float(r["total_value"])}
            for r in monthly
        ],
        "top_hs_codes": [
            {"hs_code": r["hs_code"], "count": r["usage_count"],
             "clients": r["client_count"]}
            for r in top_hs
        ],
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_date_filter(period: str) -> str:
    """สร้าง SQL WHERE clause สำหรับกรองตามช่วงเวลา"""
    if period == "month":
        return "AND created_at >= NOW() - INTERVAL '30 days'"
    elif period == "year":
        return "AND created_at >= NOW() - INTERVAL '365 days'"
    return ""  # "all" — no filter
