"""
pricing_router.py — Phase 17: Pricing & Currency Endpoints
AI TO AI HOLDING — Customs Intelligence Division

Public:
  GET /v1/pricing/tiers         — ดูราคาแต่ละ tier
  GET /v1/exchange-rates        — อัตราแลกเปลี่ยนปัจจุบัน
  GET /v1/exchange-rates/convert — แปลงสกุลเงิน

Chairman-only:
  GET /v1/chairman/pricing/costs — ดูโครงสร้างต้นทุน
"""

from fastapi import APIRouter, HTTPException, Query

from pricing_engine import get_all_tiers, get_cost_breakdown_info, calculate_price
from currency_service import get_rate_snapshot, convert, SUPPORTED_CURRENCIES

router = APIRouter(tags=["Pricing & Currency"])


# ── Public: Pricing Tiers ──────────────────────────────────────────────────────

@router.get("/v1/pricing/tiers", summary="ดูราคาแต่ละ tier")
async def list_pricing_tiers():
    """แสดง pricing tiers ทั้งหมดพร้อมรายละเอียด"""
    return {
        "success": True,
        "tiers": get_all_tiers(),
        "note": "ราคาเป็น USD — ดูอัตราแลกเปลี่ยนที่ GET /v1/exchange-rates",
    }


@router.get("/v1/pricing/estimate", summary="ประมาณราคาก่อนใช้งาน")
async def estimate_price(
    items: int = Query(..., ge=1, le=500, description="จำนวน items ใน invoice"),
    tier: str = Query("STANDARD", description="Pricing tier"),
):
    """คำนวณราคาประมาณสำหรับ invoice ที่จะส่ง"""
    result = calculate_price(item_count=items, tier=tier)
    return {"success": True, "estimate": result}


# ── Public: Exchange Rates ─────────────────────────────────────────────────────

@router.get("/v1/exchange-rates", summary="อัตราแลกเปลี่ยนปัจจุบัน")
async def exchange_rates(
    base: str = Query("USD", description="สกุลเงินฐาน"),
):
    """
    ดึงอัตราแลกเปลี่ยนเทียบกับสกุลเงินฐาน
    รองรับ: USD, THB, CNY, JPY, EUR, KRW, SGD, MYR, VND, IDR, TWD, HKD, GBP, AUD
    Cache 1 ชั่วโมง
    """
    base = base.upper().strip()
    if base not in SUPPORTED_CURRENCIES:
        raise HTTPException(400, f"ไม่รองรับสกุล {base} — รองรับ: {', '.join(SUPPORTED_CURRENCIES)}")
    snapshot = await get_rate_snapshot(base)
    return {"success": True, "data": snapshot}


@router.get("/v1/exchange-rates/convert", summary="แปลงสกุลเงิน")
async def convert_currency(
    amount: float = Query(..., gt=0, description="จำนวนเงิน"),
    from_currency: str = Query("USD", alias="from", description="สกุลเงินต้นทาง"),
    to_currency: str = Query("THB", alias="to", description="สกุลเงินปลายทาง"),
):
    """แปลงจำนวนเงินระหว่างสกุล"""
    fr = from_currency.upper().strip()
    to = to_currency.upper().strip()

    result = await convert(amount, fr, to)
    if result is None:
        raise HTTPException(503, "ไม่สามารถดึงอัตราแลกเปลี่ยนได้ กรุณาลองใหม่")

    return {
        "success": True,
        "from": fr,
        "to": to,
        "amount": amount,
        "converted": result,
        "note": "อัตราแลกเปลี่ยนเป็นเรทกลางตลาด ไม่ใช่เรทธนาคาร",
    }


# ── Chairman: Cost Analysis ────────────────────────────────────────────────────
# IP restriction handled by SecurityMiddleware (/v1/chairman/* prefix)

@router.get("/v1/chairman/pricing/costs", summary="[Chairman] โครงสร้างต้นทุน")
async def chairman_costs():
    """แสดงต้นทุนจริงต่อ call + margin analysis"""
    return {
        "success": True,
        "data": get_cost_breakdown_info(),
        "tiers": get_all_tiers(),
    }
