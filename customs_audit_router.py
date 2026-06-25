"""
customs_audit_router.py — Phase 25: Customs Audit Insurance API
AI TO AI HOLDING — Customs Intelligence Division

Public:
  POST /v1/audit-risk/assess       — ประเมิน Audit Risk Score
  GET  /v1/audit-risk/report-card  — Compliance Report Card

Chairman only:
  GET /v1/chairman/audit-risk/overview — ภาพรวมทั้ง platform
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional

from customs_audit_engine import (
    calculate_audit_risk,
    get_compliance_report_card,
    get_platform_risk_overview,
    HIGH_RISK_CHAPTERS,
    HIGH_RISK_COUNTRIES,
    RISK_WEIGHTS,
)

router = APIRouter(tags=["Audit Risk Insurance"])


# ── Request Models ───────────────────────────────────────────────────────────

class AuditRiskRequest(BaseModel):
    client_api_key_hint: str = Field(
        ..., description="ส่วนท้ายของ API Key (ใช้ match กับ DB)"
    )
    period_months: int = Field(
        12, ge=1, le=60, description="ช่วงเวลาที่ประเมิน (เดือน)"
    )


# ── Public Endpoints ─────────────────────────────────────────────────────────

@router.post(
    "/v1/audit-risk/assess",
    summary="ประเมิน Customs Audit Risk Score",
    description=(
        "วิเคราะห์ประวัตินำเข้าย้อนหลัง → คำนวณ Audit Risk Score 0-100 "
        "พร้อมเกรด A-F และคำแนะนำ"
    ),
)
async def assess_audit_risk(req: AuditRiskRequest):
    from db_adapter import get_pool
    pool = await get_pool()
    report = await calculate_audit_risk(
        pool, req.client_api_key_hint, req.period_months
    )
    return {"success": True, "audit_risk": report.to_dict()}


@router.get(
    "/v1/audit-risk/report-card",
    summary="Compliance Report Card",
    description="สรุปสถานะ compliance ภาพรวม — เหมาะส่ง CFO",
)
async def report_card(
    client_key: str = Query(..., description="API Key hint"),
):
    from db_adapter import get_pool
    pool = await get_pool()
    card = await get_compliance_report_card(pool, client_key)
    return {"success": True, **card}


@router.get(
    "/v1/audit-risk/risk-factors",
    summary="รายการปัจจัยเสี่ยงที่ใช้ประเมิน",
    description="แสดงปัจจัยเสี่ยง 7 ตัว + น้ำหนัก + HS chapters เสี่ยง",
)
async def risk_factors():
    return {
        "success": True,
        "risk_weights": RISK_WEIGHTS,
        "high_risk_chapters": HIGH_RISK_CHAPTERS,
        "high_risk_countries": {
            k: {"risk_level": v, "label": "สูง" if v >= 7 else "ปานกลาง"}
            for k, v in HIGH_RISK_COUNTRIES.items()
        },
    }


# ── Chairman Endpoints ───────────────────────────────────────────────────────

@router.get(
    "/v1/chairman/audit-risk/overview",
    summary="Chairman: Audit Risk Overview",
    include_in_schema=False,
)
async def chairman_risk_overview():
    from db_adapter import get_pool
    pool = await get_pool()
    overview = await get_platform_risk_overview(pool)
    return {"success": True, "platform_risk": overview}
