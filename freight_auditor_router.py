"""
freight_auditor_router.py — Phase 23: Freight Rate Auditor API
AI TO AI HOLDING — Customs Intelligence Division

Public endpoints:
  POST /v1/freight-audit/check          — ตรวจบิลค่าขนส่ง
  POST /v1/freight-audit/compare        — เปรียบเทียบใบเสนอราคา
  GET  /v1/freight-audit/charges        — รายชื่อ charge categories
  GET  /v1/freight-audit/market-rates   — ดู market rate card

Premium feature — ขายเป็น add-on สำหรับ Procurement/CFO
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional

from freight_auditor_engine import (
    audit_freight_bill,
    compare_forwarder_quotes,
    get_charge_categories,
    get_market_rate_card,
    ChargeLineItem,
    OVERCHARGE_THRESHOLD,
)

router = APIRouter(tags=["Freight Auditor"])


# ── Request Models ───────────────────────────────────────────────────────────

class ChargeItem(BaseModel):
    charge_type: str = Field(..., description="ประเภทค่าใช้จ่าย (เช่น thc_origin, do_fee)")
    description: str = Field("", description="ชื่อรายการตามบิลจริง")
    amount_usd: float = Field(..., gt=0, description="จำนวนเงิน (USD)")
    quantity: int = Field(1, ge=1, description="จำนวน (เช่น วัน สำหรับ demurrage)")

    model_config = {"json_schema_extra": {
        "examples": [{"charge_type": "thc_origin", "description": "THC Origin", "amount_usd": 150}]
    }}


class AuditRequest(BaseModel):
    charges: list[ChargeItem] = Field(..., min_length=1, max_length=50,
                                      description="รายการค่าใช้จ่ายจากบิล")
    shipment_mode: str = Field("sea", description="sea / air / land")
    origin_region: str = Field("default",
        description="ภูมิภาคต้นทาง: asean / east_asia / south_asia / europe / americas / oceania")
    weight_kg: float = Field(0, ge=0, description="น้ำหนักสินค้า (kg) — ใช้กับ per-kg rates")


class ForwarderQuote(BaseModel):
    name: str = Field(..., description="ชื่อ Forwarder")
    charges: list[ChargeItem] = Field(..., min_length=1, description="รายการค่าใช้จ่าย")


class CompareQuotesRequest(BaseModel):
    quotes: list[ForwarderQuote] = Field(..., min_length=2, max_length=5,
                                         description="ใบเสนอราคา 2-5 ราย")
    shipment_mode: str = Field("sea", description="sea / air / land")
    origin_region: str = Field("default", description="ภูมิภาคต้นทาง")


# ── Public Endpoints ─────────────────────────────────────────────────────────

@router.post(
    "/v1/freight-audit/check",
    summary="ตรวจบิลค่าขนส่ง",
    description=(
        "ส่งรายการค่าใช้จ่ายจากบิลชิปปิ้ง → ระบบเทียบกับอัตราตลาด → "
        "flag รายการที่แพงเกิน + แนะนำ savings "
        f"(threshold: >{int(OVERCHARGE_THRESHOLD*100)}% เหนือ typical = flag)"
    ),
)
async def audit_bill(req: AuditRequest):
    charges = [
        ChargeLineItem(
            charge_type=c.charge_type.strip().lower(),
            description=c.description or c.charge_type,
            amount_usd=c.amount_usd,
            quantity=c.quantity,
        )
        for c in req.charges
    ]

    report = audit_freight_bill(
        charges,
        shipment_mode=req.shipment_mode.strip().lower(),
        origin_region=req.origin_region.strip().lower(),
        weight_kg=req.weight_kg,
    )

    return {"success": True, "audit_report": report.to_dict()}


@router.post(
    "/v1/freight-audit/compare",
    summary="เปรียบเทียบใบเสนอราคา Forwarder",
    description="ส่งใบเสนอราคา 2-5 ราย → ระบบจัดอันดับ + วิเคราะห์ส่วนต่าง",
)
async def compare_quotes(req: CompareQuotesRequest):
    quotes_data = [
        {
            "name": q.name,
            "charges": [
                {
                    "charge_type": c.charge_type.strip().lower(),
                    "description": c.description,
                    "amount_usd": c.amount_usd,
                    "quantity": c.quantity,
                }
                for c in q.charges
            ],
        }
        for q in req.quotes
    ]

    result = compare_forwarder_quotes(
        quotes_data,
        shipment_mode=req.shipment_mode.strip().lower(),
        origin_region=req.origin_region.strip().lower(),
    )

    return {"success": True, "comparison": result}


@router.get(
    "/v1/freight-audit/charges",
    summary="รายชื่อ charge categories",
    description="แสดงประเภทค่าใช้จ่ายทั้งหมดที่ระบบรองรับ สำหรับใช้ใน charge_type field",
)
async def list_charge_types(
    mode: str = Query("", description="กรองตาม mode: sea / air / land (ว่าง = ทั้งหมด)"),
):
    categories = get_charge_categories(mode.strip().lower())
    return {
        "success": True,
        "total": len(categories),
        "categories": categories,
    }


@router.get(
    "/v1/freight-audit/market-rates",
    summary="ดู Market Rate Card",
    description="แสดงอัตราค่าขนส่งตลาดอ้างอิง (min / typical / max) สำหรับ mode + region",
)
async def market_rates(
    mode: str = Query("sea", description="sea / air"),
    region: str = Query("default",
        description="ภูมิภาค: asean / east_asia / south_asia / europe / americas / oceania / default"),
):
    card = get_market_rate_card(mode.strip().lower(), region.strip().lower())
    return {
        "success": True,
        "mode": mode,
        "region": region,
        "total": len(card),
        "rates": card,
        "note": "อัตราเป็น USD — อ้างอิงเฉลี่ยตลาด 2025-2026",
    }
