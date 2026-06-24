"""
whatif_router.py — Phase 24: What-If Scenario Optimizer API
AI TO AI HOLDING — Customs Intelligence Division

Public endpoints:
  POST /v1/whatif/simulate         — จำลอง 3 สถานการณ์ (เร็ว/คุ้ม/ประหยัด)
  POST /v1/whatif/fta-optimizer    — หา FTA ที่ดีที่สุด
  POST /v1/whatif/volume-impact    — จำลองผลของ volume ต่อ cost per unit
  POST /v1/whatif/duty-engineering — วิเคราะห์วิธีลดอากร

Strategic Sourcing Tool สำหรับองค์กรใหญ่
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional

from whatif_optimizer_engine import (
    simulate_scenarios,
    find_all_ftas,
    find_best_fta,
    simulate_volume_impact,
    duty_engineering_analysis,
    FTA_AGREEMENTS,
)

router = APIRouter(tags=["What-If Optimizer"])


# ── Request Models ───────────────────────────────────────────────────────────

class SimulateRequest(BaseModel):
    product_value: float = Field(..., gt=0, description="มูลค่าสินค้า (USD)")
    hs_code: str = Field(..., description="HS code (4-11 หลัก)")
    origin_country: str = Field(..., description="ประเทศต้นทาง ISO 2-letter (เช่น CN, VN, JP)")
    mfn_duty_rate: float = Field(..., ge=0, le=100, description="อัตราอากร MFN (%)")
    item_count: int = Field(1, ge=1, description="จำนวนชิ้น")
    weight_kg: float = Field(0, ge=0, description="น้ำหนักรวม (kg)")
    incoterm: str = Field("FOB", description="Incoterm ที่ใช้ (FOB/CIF/EXW ฯลฯ)")

    model_config = {"json_schema_extra": {
        "examples": [{
            "product_value": 50000, "hs_code": "8517.12",
            "origin_country": "CN", "mfn_duty_rate": 5.0,
            "item_count": 200, "weight_kg": 100
        }]
    }}


class FTARequest(BaseModel):
    origin_country: str = Field(..., description="ประเทศต้นทาง ISO 2-letter")
    mfn_duty_rate: float = Field(..., ge=0, le=100, description="อัตราอากร MFN (%)")


class VolumeRequest(BaseModel):
    product_value_per_unit: float = Field(..., gt=0, description="ราคาต่อหน่วย (USD)")
    hs_code: str = Field(..., description="HS code")
    origin_country: str = Field(..., description="ประเทศต้นทาง")
    mfn_duty_rate: float = Field(..., ge=0, le=100, description="อัตราอากร MFN (%)")
    transport_mode: str = Field("sea", description="sea / air / land")
    incoterm: str = Field("FOB", description="Incoterm")
    volumes: list[int] = Field(
        default=[50, 100, 500, 1000, 5000],
        description="จำนวนที่ต้องการจำลอง",
    )


class DutyEngineeringRequest(BaseModel):
    hs_code: str = Field(..., description="HS code")
    origin_country: str = Field(..., description="ประเทศต้นทาง")
    product_value: float = Field(..., gt=0, description="มูลค่าสินค้า (USD)")
    mfn_duty_rate: float = Field(..., ge=0, le=100, description="อัตราอากร MFN (%)")


# ── Public Endpoints ─────────────────────────────────────────────────────────

@router.post(
    "/v1/whatif/simulate",
    summary="จำลองสถานการณ์นำเข้า",
    description=(
        "เปรียบเทียบ 3 ทางเลือก: เร็วสุด (air) / คุ้มสุด (balanced) / ประหยัดสุด (sea/land) "
        "พร้อมแนะนำ FTA อัตโนมัติ แสดง cost breakdown + pros/cons"
    ),
)
async def simulate(req: SimulateRequest):
    result = simulate_scenarios(
        product_value=req.product_value,
        hs_code=req.hs_code.strip(),
        origin_country=req.origin_country.strip().upper(),
        mfn_duty_rate=req.mfn_duty_rate,
        item_count=req.item_count,
        weight_kg=req.weight_kg,
        incoterm=req.incoterm.strip().upper(),
    )
    return {"success": True, "simulation": result.to_dict()}


@router.post(
    "/v1/whatif/fta-optimizer",
    summary="หา FTA ที่ดีที่สุด",
    description="แสดง FTA ทั้งหมดที่ใช้ได้กับประเทศต้นทาง จัดอันดับตามอัตราอากรต่ำสุด",
)
async def fta_optimizer(req: FTARequest):
    country = req.origin_country.strip().upper()
    all_ftas = find_all_ftas(country, req.mfn_duty_rate)
    best = find_best_fta(country, req.mfn_duty_rate)

    return {
        "success": True,
        "origin_country": country,
        "mfn_rate_pct": req.mfn_duty_rate,
        "best_fta": best,
        "all_options": all_ftas,
        "total_ftas_available": len([f for f in all_ftas if f["fta_code"] != "MFN"]),
    }


@router.post(
    "/v1/whatif/volume-impact",
    summary="จำลองผลกระทบของ Volume",
    description="แสดงว่าถ้าเพิ่มจำนวนสั่งซื้อ cost per unit จะลดลงเท่าไหร่",
)
async def volume_impact(req: VolumeRequest):
    results = simulate_volume_impact(
        product_value_per_unit=req.product_value_per_unit,
        hs_code=req.hs_code.strip(),
        origin_country=req.origin_country.strip().upper(),
        mfn_duty_rate=req.mfn_duty_rate,
        transport_mode=req.transport_mode.strip().lower(),
        incoterm=req.incoterm.strip().upper(),
        volumes=req.volumes,
    )

    return {
        "success": True,
        "unit_price_usd": req.product_value_per_unit,
        "hs_code": req.hs_code,
        "transport_mode": req.transport_mode,
        "volume_analysis": results,
        "note": "cost_per_unit ลดลงเมื่อ volume เพิ่มขึ้น เนื่องจาก fixed costs ถูกเฉลี่ยมากขึ้น",
    }


@router.post(
    "/v1/whatif/duty-engineering",
    summary="วิเคราะห์วิธีลดอากรนำเข้า",
    description=(
        "Duty Engineering — แนะนำกลยุทธ์ลดต้นทุนอากร: "
        "FTA, Incoterm optimization, HS review, Bonded warehouse, Volume consolidation"
    ),
)
async def duty_engineering(req: DutyEngineeringRequest):
    result = duty_engineering_analysis(
        hs_code=req.hs_code.strip(),
        origin_country=req.origin_country.strip().upper(),
        product_value=req.product_value,
        mfn_rate=req.mfn_duty_rate,
    )
    return {"success": True, "analysis": result}


@router.get(
    "/v1/whatif/fta-list",
    summary="รายชื่อ FTA ที่ไทยเป็นภาคี",
    description="แสดง FTA ทั้งหมด 10 ฉบับ พร้อมประเทศสมาชิกและ form ที่ใช้",
)
async def fta_list():
    ftas = []
    for code, info in FTA_AGREEMENTS.items():
        ftas.append({
            "code": code,
            "name": info["name"],
            "form": info["form"],
            "countries": info["countries"],
            "typical_reduction_pct": round(info["typical_rate_reduction"] * 100, 0),
        })
    return {
        "success": True,
        "total": len(ftas),
        "fta_agreements": ftas,
    }
