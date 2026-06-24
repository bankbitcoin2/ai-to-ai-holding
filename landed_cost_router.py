"""
landed_cost_router.py — Phase 21: Landed Cost API Endpoints
AI TO AI HOLDING — Customs Intelligence Division

Endpoints:
  POST /v1/landed-cost/calculate     — คำนวณ Landed Cost (ต้อง API Key + credit)
  POST /v1/landed-cost/compare       — เปรียบเทียบ Incoterms (ต้อง API Key + credit)
  GET  /v1/landed-cost/incoterms     — รายการ Incoterms 2020 (public)
  GET  /v1/landed-cost/freight-rates  — อัตราค่าขนส่งอ้างอิง (public)
  GET  /v1/landed-cost/ports         — ท่าเรือ/สนามบินไทย (public)
  GET  /v1/landed-cost/insurance     — ประมาณค่าประกัน (public)
"""

from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Query, Request, HTTPException
from pydantic import BaseModel, Field

from landed_cost_engine import (
    calculate_landed_cost, compare_incoterms, get_all_incoterms,
    get_incoterm_info, LocalCharges, INCOTERMS,
)
from freight_rate_service import (
    get_freight_rate, get_insurance_rate, get_local_charges,
    get_all_ports, get_transit_time,
)

router = APIRouter(prefix="/v1/landed-cost", tags=["Landed Cost"])


# ── Request Models ────────────────────────────────────────────────────────────

class LandedCostRequest(BaseModel):
    product_value: float = Field(..., gt=0, description="Goods value in source currency")
    currency: str = Field(default="USD", description="Source currency (USD/THB/CNY etc.)")
    currency_rate: Optional[float] = Field(default=None, description="Rate: 1 USD = ? source currency")
    incoterm: str = Field(default="FOB", description="Incoterms 2020 code")
    hs_code: str = Field(default="", description="HS code for duty lookup")
    origin_country: str = Field(default="", description="ISO country code (e.g. CN, VN, JP)")
    transport_mode: str = Field(default="sea", description="sea / air / land")
    item_count: int = Field(default=1, ge=1, description="Number of items")
    weight_kg: float = Field(default=0, ge=0, description="Total weight in kg")
    # Optional overrides
    freight_cost: Optional[float] = Field(default=None, description="Override freight cost (USD)")
    insurance_cost: Optional[float] = Field(default=None, description="Override insurance cost (USD)")
    duty_rate: Optional[float] = Field(default=None, ge=0, description="Applied duty rate %")
    fta_name: Optional[str] = Field(default=None, description="FTA agreement name")
    mfn_rate: Optional[float] = Field(default=None, ge=0, description="MFN rate % (for savings calc)")


class CompareRequest(BaseModel):
    quotes: dict[str, float] = Field(
        ..., description="Incoterm → price mapping, e.g. {\"FOB\": 10000, \"CIF\": 11500}"
    )
    hs_code: str = Field(default="")
    origin_country: str = Field(default="")
    transport_mode: str = Field(default="sea")
    item_count: int = Field(default=1, ge=1)
    weight_kg: float = Field(default=0, ge=0)
    duty_rate: float = Field(default=0, ge=0)
    mfn_rate: Optional[float] = Field(default=None, ge=0)
    freight_cost: Optional[float] = Field(default=None)
    insurance_cost: Optional[float] = Field(default=None)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/calculate")
async def api_calculate_landed_cost(body: LandedCostRequest, request: Request):
    """
    คำนวณ Total Landed Cost สินค้านำเข้าไทย
    รวม: Product + Freight + Insurance + Duty + VAT 7% + Local Charges
    """
    # Validate incoterm
    if body.incoterm.upper() not in INCOTERMS:
        raise HTTPException(400, f"Unknown Incoterm: {body.incoterm}. Supported: {list(INCOTERMS.keys())}")

    try:
        result = calculate_landed_cost(
            product_value=body.product_value,
            incoterm=body.incoterm,
            hs_code=body.hs_code,
            origin_country=body.origin_country,
            transport_mode=body.transport_mode,
            item_count=body.item_count,
            weight_kg=body.weight_kg,
            freight_cost=body.freight_cost,
            insurance_cost=body.insurance_cost,
            duty_rate=body.duty_rate,
            fta_name=body.fta_name,
            mfn_rate=body.mfn_rate,
            currency=body.currency,
            currency_rate=body.currency_rate,
        )
        return {
            "status": "success",
            "landed_cost": result.to_dict(),
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Calculation error: {str(e)}")


@router.post("/compare")
async def api_compare_incoterms(body: CompareRequest, request: Request):
    """
    เปรียบเทียบ Landed Cost จากหลาย Incoterm quotes
    เรียงจากถูกสุดไปแพงสุด พร้อม recommendation
    """
    if not body.quotes or len(body.quotes) < 2:
        raise HTTPException(400, "Need at least 2 Incoterm quotes to compare")

    try:
        results = compare_incoterms(
            product_values=body.quotes,
            hs_code=body.hs_code,
            origin_country=body.origin_country,
            transport_mode=body.transport_mode,
            item_count=body.item_count,
            weight_kg=body.weight_kg,
            duty_rate=body.duty_rate,
            mfn_rate=body.mfn_rate,
            freight_cost=body.freight_cost,
            insurance_cost=body.insurance_cost,
        )
        return {
            "status": "success",
            "comparison_count": len(results),
            "results": results,
        }
    except Exception as e:
        raise HTTPException(500, f"Comparison error: {str(e)}")


@router.get("/incoterms")
async def api_list_incoterms():
    """รายการ Incoterms 2020 ทั้งหมด พร้อมรายละเอียดความรับผิดชอบผู้ซื้อ"""
    return {
        "status": "success",
        "count": len(INCOTERMS),
        "incoterms": get_all_incoterms(),
    }


@router.get("/incoterms/{code}")
async def api_get_incoterm(code: str):
    """รายละเอียด Incoterm เฉพาะตัว"""
    info = get_incoterm_info(code)
    if not info:
        raise HTTPException(404, f"Incoterm not found: {code}")
    return {
        "status": "success",
        "incoterm": {
            "code": info.code,
            "name": info.name,
            "group": info.group,
            "any_mode": info.any_mode,
            "description_th": info.description_th,
            "buyer_pays": {
                "export_clearance": info.buyer_pays_export,
                "freight": info.buyer_pays_freight,
                "insurance": info.buyer_pays_insurance,
                "import_duty": info.buyer_pays_import_duty,
                "delivery_to_warehouse": info.buyer_pays_delivery,
            }
        }
    }


@router.get("/freight-rates")
async def api_freight_rates(
    mode: str = Query("sea", description="Transport mode: sea/air/land"),
    origin_country: str = Query("CN", description="Origin country code"),
    weight_kg: float = Query(0, ge=0, description="Shipment weight kg"),
    cbm: float = Query(0, ge=0, description="Volume in CBM (sea only)"),
):
    """อัตราค่าขนส่งอ้างอิง + ประมาณการ"""
    return {
        "status": "success",
        "freight_rate": get_freight_rate(mode, origin_country, weight_kg, cbm),
    }


@router.get("/ports")
async def api_list_ports():
    """รายชื่อท่าเรือ/สนามบิน/ด่านศุลกากรไทย"""
    return {
        "status": "success",
        "ports": get_all_ports(),
    }


@router.get("/ports/{port_id}/charges")
async def api_port_charges(
    port_id: str,
    mode: str = Query("sea", description="Transport mode"),
):
    """ค่าใช้จ่ายท้องถิ่น ณ ท่าเรือ/สนามบิน"""
    result = get_local_charges(mode, port_id)
    return {"status": "success", "local_charges": result}


@router.get("/insurance")
async def api_insurance_estimate(
    goods_value: float = Query(..., gt=0, description="Goods value USD"),
    freight_cost: float = Query(0, ge=0, description="Freight cost USD"),
    cargo_type: str = Query("general", description="general/fragile/perishable/hazardous/high_value/bulk"),
):
    """ประมาณค่าเบี้ยประกันสินค้า"""
    return {
        "status": "success",
        "insurance": get_insurance_rate(goods_value, freight_cost, cargo_type),
    }


@router.get("/transit-time")
async def api_transit_time(
    mode: str = Query("sea"),
    origin_country: str = Query("CN"),
):
    """ระยะเวลาขนส่งโดยประมาณ"""
    return {
        "status": "success",
        "transit": get_transit_time(mode, origin_country),
    }
