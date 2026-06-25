"""
valuation_router.py — Project Valuation API Endpoints
AI TO AI HOLDING — Customs Intelligence Division

Chairman-only endpoints สำหรับดูมูลค่าโครงการ
ทุก endpoint ซ่อนจาก Swagger /docs (include_in_schema=False)
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from typing import Optional

import valuation_engine as ve

router = APIRouter(tags=["Valuation"])


# ── Chairman Only Endpoints ───────────────────────────────────────────────────

@router.get("/v1/chairman/valuation/full", include_in_schema=False)
async def get_full_valuation(
    base_value: float = Query(15_000_000, description="มูลค่าตั้งต้น (บาท)"),
):
    """
    ประเมินมูลค่าโครงการทั้งหมด — 12 มิติ 3 วิธีการ
    Chairman Only
    """
    result = ve.calculate_full_valuation(base_value_thb=base_value)
    return JSONResponse(content={
        "status": "success",
        "data": result.to_dict(),
    })


@router.get("/v1/chairman/valuation/litigation", include_in_schema=False)
async def get_litigation_value():
    """
    มูลค่าเรียกร้องทางกฎหมาย หากถูกลอกเลียนแบบ
    Chairman Only
    """
    result = ve.calculate_litigation_value()
    return JSONResponse(content={
        "status": "success",
        "data": result,
    })


@router.get("/v1/chairman/valuation/features", include_in_schema=False)
async def get_feature_portfolio():
    """
    มูลค่าเฉพาะตัวของแต่ละฟีเจอร์
    Chairman Only
    """
    result = ve.get_feature_portfolio()
    return JSONResponse(content={
        "status": "success",
        "data": result,
    })


@router.get("/v1/chairman/valuation/growth", include_in_schema=False)
async def get_growth_projection(
    current_users: int = Query(50, description="จำนวนผู้ใช้ปัจจุบัน"),
    monthly_growth: float = Query(0.08, description="อัตราเติบโตรายเดือน (0.08 = 8%)"),
    months: int = Query(60, description="จำนวนเดือนที่จำลอง"),
):
    """
    จำลองมูลค่าตามการเติบโตของผู้ใช้
    Chairman Only
    """
    result = ve.project_growth(
        current_users=current_users,
        monthly_growth_rate=monthly_growth,
        months=months,
    )
    return JSONResponse(content={
        "status": "success",
        "data": result,
    })


@router.get("/v1/chairman/valuation/summary", include_in_schema=False)
async def get_valuation_summary():
    """
    สรุปมูลค่าโครงการ — Chairman Dashboard
    Chairman Only
    """
    result = ve.get_valuation_summary()
    return JSONResponse(content={
        "status": "success",
        "data": result,
    })
