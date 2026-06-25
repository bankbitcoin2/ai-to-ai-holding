"""
cbam_carbon_router.py — Phase 27: CBAM Carbon Tracker API
AI TO AI HOLDING — Customs Intelligence Division

Public:
  POST /v1/carbon/calculate     — คำนวณ Carbon Footprint
  POST /v1/carbon/report        — สร้าง Carbon Report หลายสินค้า
  GET  /v1/carbon/cbam-check    — ตรวจ EU CBAM applicability
  GET  /v1/carbon/emission-factor — ดึง emission factor
  GET  /v1/carbon/cbam-sectors  — รายการ sectors ภายใต้ CBAM
  GET  /v1/carbon/grid-factors  — Grid emission factors ทุกประเทศ
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional

from cbam_carbon_engine import (
    calculate_carbon_footprint,
    generate_carbon_report,
    check_cbam_applicability,
    get_emission_factor,
    get_cbam_sectors,
    get_grid_factors,
)

router = APIRouter(tags=["Carbon Tracker (CBAM)"])


# ── Request Models ───────────────────────────────────────────────────────────

class CarbonCalcRequest(BaseModel):
    hs_code: str = Field(..., description="HS code")
    weight_kg: float = Field(..., gt=0, description="น้ำหนักสินค้า (kg)")
    origin_country: str = Field("CN", description="ประเทศผลิต ISO 2-letter")
    product_description: str = Field("", description="คำอธิบายสินค้า")
    emission_factor: Optional[float] = Field(
        None, ge=0, description="Custom emission factor (kg CO₂e/tonne) — ถ้ามีจากผู้ผลิต"
    )

    model_config = {"json_schema_extra": {"examples": [{
        "hs_code": "7208", "weight_kg": 25000,
        "origin_country": "CN", "product_description": "Hot-rolled steel coil"
    }]}}


class CarbonReportRequest(BaseModel):
    items: list[dict] = Field(
        ..., max_length=100,
        description="รายการสินค้า: [{hs_code, weight_kg, origin_country, description}]",
    )
    reporting_period: str = Field("Q1 2026", description="ช่วงเวลารายงาน")


# ── Public Endpoints ─────────────────────────────────────────────────────────

@router.post(
    "/v1/carbon/calculate",
    summary="คำนวณ Carbon Footprint",
    description=(
        "คำนวณ CO₂ emissions ของสินค้า ทั้ง Scope 1 (direct) และ Scope 2 (electricity) "
        "พร้อมประมาณค่า CBAM certificate ถ้าอยู่ภายใต้ EU CBAM"
    ),
)
async def carbon_calculate(req: CarbonCalcRequest):
    fp = calculate_carbon_footprint(
        hs_code=req.hs_code.strip(),
        weight_kg=req.weight_kg,
        origin_country=req.origin_country.strip().upper(),
        product_description=req.product_description,
        custom_emission_factor=req.emission_factor,
    )
    return {"success": True, "carbon_footprint": fp.to_dict()}


@router.post(
    "/v1/carbon/report",
    summary="สร้าง Carbon Report",
    description=(
        "สร้างรายงาน Carbon ภาพรวมจากหลายสินค้า "
        "เหมาะสำหรับยื่นรายงาน EU CBAM quarterly"
    ),
)
async def carbon_report(req: CarbonReportRequest):
    report = generate_carbon_report(req.items, req.reporting_period)
    return {"success": True, "carbon_report": report.to_dict()}


@router.get(
    "/v1/carbon/cbam-check",
    summary="ตรวจ EU CBAM",
    description="ตรวจว่า HS code อยู่ภายใต้ EU CBAM Phase 1 หรือไม่",
)
async def cbam_check(
    hs_code: str = Query(..., description="HS code"),
):
    result = check_cbam_applicability(hs_code.strip())
    return {"success": True, **result}


@router.get(
    "/v1/carbon/emission-factor",
    summary="ดึง Emission Factor",
    description="ดึง default emission factor สำหรับ HS code (kg CO₂e per tonne)",
)
async def emission_factor(
    hs_code: str = Query(..., description="HS code"),
):
    result = get_emission_factor(hs_code.strip())
    return {"success": True, **result}


@router.get(
    "/v1/carbon/cbam-sectors",
    summary="EU CBAM Sectors",
    description="รายการ sectors ทั้งหมดที่อยู่ภายใต้ EU CBAM Phase 1 (2026)",
)
async def cbam_sectors():
    sectors = get_cbam_sectors()
    return {"success": True, "total": len(sectors), "sectors": sectors}


@router.get(
    "/v1/carbon/grid-factors",
    summary="Grid Emission Factors",
    description="ค่า CO₂ emissions ต่อ MWh ของแต่ละประเทศ — ใช้คำนวณ Scope 2",
)
async def grid_factors():
    return {"success": True, **get_grid_factors()}
