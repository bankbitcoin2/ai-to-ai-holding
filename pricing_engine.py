"""
pricing_engine.py — Phase 17: Tiered Pricing + Cost Analysis
AI TO AI HOLDING — Customs Intelligence Division

Pricing Tiers:
  STANDARD    — $0.50/query (ลูกค้าทั่วไป, default)
  VAN         — $0.015/call (VAN/Software integration, volume)
  VOLUME      — $0.003/call (high-volume partners)
  ENTERPRISE  — $200-500/mo flat (unlimited within quota)

ระบบนี้:
1. คำนวณราคาต่อ item ตาม tier ของลูกค้า
2. วิเคราะห์ต้นทุนจริงต่อ call (Claude API + infra)
3. คำนวณ margin
4. รองรับ membership discount (Phase 18 จะ wire เข้า)

Usage:
    price = calculate_price(item_count=8, tier="STANDARD")
    cost  = estimate_cost(item_count=8)
    margin = price - cost
"""

import os
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone


# ── Pricing Tiers ──────────────────────────────────────────────────────────────

@dataclass
class PricingTier:
    name: str
    display_name: str
    price_per_item: float       # USD ต่อ item
    monthly_fee: float          # USD/month (0 = pay-per-use)
    monthly_quota: int          # items/month ที่รวมใน monthly fee (0 = unlimited pay-per-use)
    overage_rate: float         # USD/item เกิน quota
    description: str
    min_volume: int             # minimum monthly items เพื่อ qualify

TIERS: dict[str, PricingTier] = {
    "STANDARD": PricingTier(
        name="STANDARD",
        display_name="Standard",
        price_per_item=0.50,
        monthly_fee=0.0,
        monthly_quota=0,
        overage_rate=0.50,
        description="Pay-per-query สำหรับลูกค้าทั่วไป",
        min_volume=0,
    ),
    "VAN": PricingTier(
        name="VAN",
        display_name="VAN / Software",
        price_per_item=0.015,
        monthly_fee=0.0,
        monthly_quota=0,
        overage_rate=0.015,
        description="VAN/Software integration — volume rate",
        min_volume=500,
    ),
    "VOLUME": PricingTier(
        name="VOLUME",
        display_name="Volume Partner",
        price_per_item=0.003,
        monthly_fee=0.0,
        monthly_quota=0,
        overage_rate=0.003,
        description="High-volume partner rate",
        min_volume=5000,
    ),
    "ENTERPRISE_S": PricingTier(
        name="ENTERPRISE_S",
        display_name="Enterprise S",
        price_per_item=0.0,
        monthly_fee=200.0,
        monthly_quota=2000,
        overage_rate=0.08,
        description="Enterprise Small — $200/mo, 2,000 items included",
        min_volume=0,
    ),
    "ENTERPRISE_M": PricingTier(
        name="ENTERPRISE_M",
        display_name="Enterprise M",
        price_per_item=0.0,
        monthly_fee=350.0,
        monthly_quota=5000,
        overage_rate=0.05,
        description="Enterprise Medium — $350/mo, 5,000 items included",
        min_volume=0,
    ),
    "ENTERPRISE_L": PricingTier(
        name="ENTERPRISE_L",
        display_name="Enterprise L",
        price_per_item=0.0,
        monthly_fee=500.0,
        monthly_quota=15000,
        overage_rate=0.025,
        description="Enterprise Large — $500/mo, 15,000 items included",
        min_volume=0,
    ),
}

# Default tier จาก env (backward compatible กับ PRICE_PER_ITEM)
_DEFAULT_TIER = os.getenv("DEFAULT_PRICING_TIER", "STANDARD")


# ── Cost Analysis ──────────────────────────────────────────────────────────────

@dataclass
class CostBreakdown:
    """ต้นทุนจริงต่อ invoice"""
    claude_classify: float      # Claude Sonnet per item (~$0.003-0.02)
    claude_xai: float           # Claude Haiku XAI per item (~$0.001)
    db_lookup: float            # DB + cache overhead
    infrastructure: float       # Railway pro-rated per call
    total_per_item: float
    total_per_invoice: float
    item_count: int


# ต้นทุนโดยประมาณ (ปรับได้ผ่าน env)
_COST_CLASSIFY = float(os.getenv("COST_CLASSIFY_PER_ITEM", "0.012"))    # Claude Sonnet avg
_COST_XAI = float(os.getenv("COST_XAI_PER_ITEM", "0.001"))             # Claude Haiku
_COST_DB = float(os.getenv("COST_DB_PER_ITEM", "0.0005"))              # DB lookup overhead
_COST_INFRA_MONTHLY = float(os.getenv("COST_INFRA_MONTHLY", "20.0"))   # Railway ~$20/mo
_EST_MONTHLY_ITEMS = float(os.getenv("EST_MONTHLY_ITEMS", "5000"))      # estimated volume


def estimate_cost(item_count: int) -> CostBreakdown:
    """วิเคราะห์ต้นทุนจริงต่อ invoice"""
    infra_per_item = _COST_INFRA_MONTHLY / max(_EST_MONTHLY_ITEMS, 1)
    total_per_item = _COST_CLASSIFY + _COST_XAI + _COST_DB + infra_per_item
    return CostBreakdown(
        claude_classify=round(_COST_CLASSIFY * item_count, 4),
        claude_xai=round(_COST_XAI * item_count, 4),
        db_lookup=round(_COST_DB * item_count, 4),
        infrastructure=round(infra_per_item * item_count, 4),
        total_per_item=round(total_per_item, 4),
        total_per_invoice=round(total_per_item * item_count, 4),
        item_count=item_count,
    )


# ── Price Calculation ──────────────────────────────────────────────────────────

def calculate_price(item_count: int, tier: str = None,
                    membership_discount: float = 0.0,
                    monthly_usage: int = 0) -> dict:
    """
    คำนวณราคาสำหรับ 1 invoice

    Args:
        item_count: จำนวน items ใน invoice
        tier: pricing tier name (default from env)
        membership_discount: ส่วนลดจาก membership tier (0.0 - 0.20)
        monthly_usage: items ที่ใช้ไปแล้วในเดือนนี้ (สำหรับ enterprise quota)

    Returns:
        dict with price breakdown
    """
    tier_name = (tier or _DEFAULT_TIER).upper()
    t = TIERS.get(tier_name, TIERS["STANDARD"])

    if t.monthly_fee > 0 and t.monthly_quota > 0:
        # Enterprise: ดูว่าเกิน quota ไหม
        remaining_quota = max(0, t.monthly_quota - monthly_usage)
        covered = min(item_count, remaining_quota)
        overage = max(0, item_count - remaining_quota)
        gross = round(overage * t.overage_rate, 4)
    else:
        # Pay-per-use
        covered = 0
        overage = item_count
        gross = round(item_count * t.price_per_item, 4)

    # Apply membership discount
    discount = round(gross * min(membership_discount, 0.20), 4)
    net = round(gross - discount, 4)

    # Cost analysis
    cost = estimate_cost(item_count)
    margin = round(net - cost.total_per_invoice, 4)

    return {
        "tier": tier_name,
        "tier_display": t.display_name,
        "item_count": item_count,
        "price_per_item": t.price_per_item if t.monthly_fee == 0 else t.overage_rate,
        "covered_by_quota": covered,
        "overage_items": overage,
        "gross_usd": gross,
        "membership_discount": discount,
        "discount_pct": round(membership_discount * 100, 1),
        "net_usd": net,
        "cost_estimate_usd": cost.total_per_invoice,
        "margin_usd": margin,
        "margin_pct": round((margin / net * 100) if net > 0 else 0, 1),
    }


def get_deduct_amount(item_count: int, tier: str = None,
                      membership_discount: float = 0.0,
                      monthly_usage: int = 0) -> float:
    """
    คืนจำนวนเงิน USD ที่ต้องหักจาก credit
    ใช้แทน PRICE_PER_ITEM * item_count แบบเดิม
    """
    result = calculate_price(item_count, tier, membership_discount, monthly_usage)
    return result["net_usd"]


# ── Tier Info for API ──────────────────────────────────────────────────────────

def get_all_tiers() -> list[dict]:
    """คืนรายการ tiers ทั้งหมด (สำหรับแสดงใน API docs / pricing page)"""
    return [
        {
            "name": t.name,
            "display_name": t.display_name,
            "price_per_item": t.price_per_item,
            "monthly_fee": t.monthly_fee,
            "monthly_quota": t.monthly_quota,
            "overage_rate": t.overage_rate,
            "description": t.description,
            "min_volume": t.min_volume,
        }
        for t in TIERS.values()
    ]


def get_cost_breakdown_info() -> dict:
    """คืนโครงสร้างต้นทุน (Chairman only)"""
    cost = estimate_cost(1)
    return {
        "per_item": {
            "claude_classify": _COST_CLASSIFY,
            "claude_xai": _COST_XAI,
            "db_lookup": _COST_DB,
            "infrastructure": round(_COST_INFRA_MONTHLY / max(_EST_MONTHLY_ITEMS, 1), 4),
            "total": cost.total_per_item,
        },
        "monthly_infrastructure": _COST_INFRA_MONTHLY,
        "estimated_monthly_volume": _EST_MONTHLY_ITEMS,
        "avg_items_per_invoice": 8,
        "avg_cost_per_invoice": round(cost.total_per_item * 8, 4),
        "note": "ต้นทุนประมาณการ — ปรับได้ผ่าน env vars",
    }
