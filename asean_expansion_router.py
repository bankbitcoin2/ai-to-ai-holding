"""
asean_expansion_router.py — Phase 28: ASEAN Expansion API
AI TO AI HOLDING — Customs Intelligence Division

Public:
  POST /v1/asean/compare-duties  — เปรียบเทียบอากรข้ามประเทศ
  POST /v1/asean/compliance      — ตรวจ compliance ประเทศ ASEAN
  POST /v1/asean/multi-check     — ตรวจหลายประเทศพร้อมกัน
  GET  /v1/asean/countries       — รายชื่อประเทศที่รองรับ
  GET  /v1/asean/country         — ข้อมูลเฉพาะประเทศ

Chairman:
  GET /v1/chairman/asean/status  — สถานะการขยาย
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional

from asean_expansion_engine import (
    compare_duties,
    check_compliance,
    multi_country_check,
    get_country_profile,
    get_all_countries,
    get_expansion_status,
)

router = APIRouter(tags=["ASEAN Expansion"])


# ── Request Models ───────────────────────────────────────────────────────────

class DutyCompareRequest(BaseModel):
    hs_code: str = Field(..., description="HS code (เช่น 8703, 6203)")
    countries: Optional[list[str]] = Field(
        None, description="รหัสประเทศ ISO 2-letter (ถ้าไม่ระบุ = ทุกประเทศ ASEAN)"
    )

    model_config = {"json_schema_extra": {"examples": [{
        "hs_code": "8703", "countries": ["TH", "VN", "MY", "ID"]
    }]}}


class ComplianceRequest(BaseModel):
    hs_code: str = Field(..., description="HS code")
    country_code: str = Field(..., description="รหัสประเทศ ISO 2-letter")


class MultiCheckRequest(BaseModel):
    hs_code: str = Field(..., description="HS code")
    countries: Optional[list[str]] = Field(
        None, description="รหัสประเทศ (ถ้าไม่ระบุ = ทุกประเทศ)"
    )


# ── Public Endpoints ─────────────────────────────────────────────────────────

@router.post(
    "/v1/asean/compare-duties",
    summary="เปรียบเทียบอากรข้ามประเทศ ASEAN",
    description=(
        "แสดง duty rate + VAT/GST ของแต่ละประเทศ จัดอันดับจากถูกไปแพง "
        "เหมาะสำหรับ sourcing decision"
    ),
)
async def asean_compare(req: DutyCompareRequest):
    result = compare_duties(req.hs_code.strip(), req.countries)
    return {"success": True, "duty_comparison": result.to_dict()}


@router.post(
    "/v1/asean/compliance",
    summary="ตรวจ Compliance ประเทศ ASEAN",
    description="ตรวจ duty rate, VAT, FTA ที่ใช้ได้, เอกสารที่ต้องเตรียม",
)
async def asean_compliance(req: ComplianceRequest):
    result = check_compliance(req.hs_code.strip(), req.country_code.strip())
    return {"success": True, "compliance": result.to_dict()}


@router.post(
    "/v1/asean/multi-check",
    summary="ตรวจ Compliance หลายประเทศ",
    description="ตรวจ compliance ทุกประเทศ ASEAN พร้อมกัน สำหรับ HS code เดียว",
)
async def asean_multi_check(req: MultiCheckRequest):
    results = multi_country_check(req.hs_code.strip(), req.countries)
    return {
        "success": True,
        "hs_code": req.hs_code,
        "total_countries": len(results),
        "results": results,
    }


@router.get(
    "/v1/asean/countries",
    summary="ประเทศ ASEAN ที่รองรับ",
    description="รายชื่อประเทศทั้งหมดพร้อมสถานะ (LIVE / BETA / PLANNED)",
)
async def asean_countries():
    countries = get_all_countries()
    return {
        "success": True,
        "total": len(countries),
        "countries": countries,
    }


@router.get(
    "/v1/asean/country",
    summary="ข้อมูลประเทศ ASEAN",
)
async def asean_country(
    code: str = Query(..., description="รหัสประเทศ ISO 2-letter (TH/VN/MY/ID/PH/SG)"),
):
    profile = get_country_profile(code.strip())
    if not profile:
        return {"success": False, "error": f"ไม่รองรับประเทศ: {code}"}
    return {"success": True, "country": profile}


# ── Chairman Endpoints ───────────────────────────────────────────────────────

@router.get(
    "/v1/chairman/asean/status",
    summary="Chairman: ASEAN Expansion Status",
    include_in_schema=False,
)
async def chairman_asean_status():
    status = get_expansion_status()
    return {"success": True, "expansion_status": status}
