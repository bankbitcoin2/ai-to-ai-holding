"""
oga_router.py — Phase 26: Dynamic OGA Engine API
AI TO AI HOLDING — Customs Intelligence Division

Public:
  POST /v1/oga/check       — ตรวจ OGA requirements สำหรับ HS code
  POST /v1/oga/check-batch — ตรวจหลาย HS codes พร้อมกัน
  GET  /v1/oga/documents   — รายการเอกสารที่ต้องเตรียม
  GET  /v1/oga/agencies    — รายชื่อ 36 หน่วยงาน OGA
  GET  /v1/oga/agency      — ข้อมูลหน่วยงานเฉพาะราย
  GET  /v1/oga/chapters    — สรุป HS ที่ต้อง OGA

Chairman:
  GET /v1/chairman/oga/status — สถานะ engine
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional

from oga_engine import (
    check,
    check_batch,
    get_documents_checklist,
    get_all_agencies,
    get_agency_detail,
    get_restricted_chapters_summary,
    list_chapters,
    status as oga_status,
)

router = APIRouter(tags=["OGA (Other Government Agency)"])


# ── Request Models ───────────────────────────────────────────────────────────

class OGACheckRequest(BaseModel):
    hs_code: str = Field(..., description="HS code (เช่น 0301.99, 8517.12, 93)")

class OGABatchRequest(BaseModel):
    hs_codes: list[str] = Field(
        ..., max_length=50,
        description="รายการ HS codes (สูงสุด 50 รายการ)",
    )


# ── Public Endpoints ─────────────────────────────────────────────────────────

@router.post(
    "/v1/oga/check",
    summary="ตรวจสอบ OGA requirements",
    description="ตรวจว่า HS code ต้องขอใบอนุญาตจากหน่วยงานใดบ้าง",
)
async def oga_check(req: OGACheckRequest):
    result = check(req.hs_code.strip())
    return {"success": True, "oga_result": result}


@router.post(
    "/v1/oga/check-batch",
    summary="ตรวจ OGA หลาย HS codes",
    description="ตรวจ OGA requirements หลาย HS codes พร้อมกัน (สูงสุด 50)",
)
async def oga_check_batch(req: OGABatchRequest):
    results = check_batch(req.hs_codes)
    restricted_count = sum(1 for r in results if r.get("is_restricted"))
    return {
        "success": True,
        "total_checked": len(results),
        "restricted_count": restricted_count,
        "results": results,
    }


@router.get(
    "/v1/oga/documents",
    summary="รายการเอกสารที่ต้องเตรียม",
    description="สร้าง checklist เอกสารมาตรฐาน + เอกสาร OGA สำหรับ HS code",
)
async def oga_documents(
    hs_code: str = Query(..., description="HS code"),
):
    checklist = get_documents_checklist(hs_code.strip())
    return {"success": True, **checklist}


@router.get(
    "/v1/oga/agencies",
    summary="รายชื่อหน่วยงาน OGA ทั้ง 36 หน่วยงาน",
)
async def oga_agencies():
    agencies = get_all_agencies()
    return {
        "success": True,
        "total_agencies": len(agencies),
        "agencies": agencies,
    }


@router.get(
    "/v1/oga/agency",
    summary="ข้อมูลหน่วยงาน OGA เฉพาะราย",
)
async def oga_agency(
    code: str = Query(..., description="รหัสหน่วยงาน เช่น FDA, DLD, NBTC"),
):
    detail = get_agency_detail(code.strip())
    if not detail:
        return {"success": False, "error": f"ไม่พบหน่วยงาน: {code}"}
    return {"success": True, "agency": detail}


@router.get(
    "/v1/oga/chapters",
    summary="สรุป HS ที่ต้อง OGA",
    description="แสดง HS prefixes ทั้งหมดที่ต้องขออนุญาต OGA พร้อมจำนวนหน่วยงาน",
)
async def oga_chapters():
    summary = get_restricted_chapters_summary()
    return {
        "success": True,
        "total_restricted_prefixes": len(summary),
        "chapters": summary,
    }


# ── Chairman Endpoints ───────────────────────────────────────────────────────

@router.get(
    "/v1/chairman/oga/status",
    summary="Chairman: OGA Engine Status",
    include_in_schema=False,
)
async def chairman_oga_status():
    return {"success": True, "oga_engine": oga_status()}
