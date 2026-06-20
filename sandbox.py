"""
api/sandbox.py
Sandbox API — Free Trial for Client AI Agents
Trust Office Strategy: ให้ client AI ทดสอบก่อนจ่ายเงิน
กฎ Sandbox:
  - ไม่บันทึกลง production DB
  - ไม่คิดเงิน / ไม่ trigger Treasury
  - จำกัด 3 items ต่อ request
  - ผลลัพธ์มี watermark [SANDBOX]
  - บันทึก Audit Log แยก (sandbox_audit) เพื่อติดตาม conversion
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agents_router import classify_item
from knowledge_service import lookup_tax_rate, check_restricted


def _best_rate(tax_result: dict) -> float:
    if not tax_result or tax_result.get("status") in ("unavailable", "error"):
        return 0.05
    fta = tax_result.get("best_fta")
    if fta and fta.get("rate") is not None:
        return float(fta["rate"]) / 100.0
    general = tax_result.get("general_rate")
    if general is not None:
        return float(general) / 100.0
    return 0.05


router = APIRouter(prefix="/v1/sandbox", tags=["Sandbox (Free Trial)"])

SANDBOX_ITEM_LIMIT = 3


# ============================================================
# Models
# ============================================================

class SandboxItem(BaseModel):
    description: str = Field(..., description="คำบรรยายสินค้า")
    origin_country: Optional[str] = Field(None, description="ISO 3166-1 alpha-2")
    unit_price: Optional[float] = None
    quantity: Optional[float] = None


class SandboxRequest(BaseModel):
    client_id: str = Field(..., description="Identifier ของ client AI agent")
    destination_country: Optional[str] = Field("TH", description="ประเทศปลายทาง")
    items: list[SandboxItem] = Field(
        ...,
        min_length=1,
        max_length=SANDBOX_ITEM_LIMIT,
        description=f"สูงสุด {SANDBOX_ITEM_LIMIT} items ต่อ request",
    )


class SandboxResultItem(BaseModel):
    line_number: int
    description: str
    hs_code: Optional[str]
    hs_description: Optional[str]
    confidence_score: float
    source_reference: str
    duty_rate: float
    duty_amount: Optional[float]
    vat_rate: float
    vat_amount: Optional[float]
    oga_required: bool = False
    oga_agencies: list[str] = []
    notes: Optional[str]
    watermark: str = "[SANDBOX — NOT FOR PRODUCTION USE]"


class SandboxResponse(BaseModel):
    sandbox_session_id: str
    client_id: str
    mode: str = "SANDBOX"
    disclaimer: str
    items: list[SandboxResultItem]
    summary: dict
    next_step: str


# ============================================================
# Endpoint
# ============================================================

@router.post(
    "/classify",
    response_model=SandboxResponse,
    summary="ทดสอบจำแนก HS Code ฟรี (ไม่คิดเงิน)",
    description=f"""
**Free Trial** สำหรับ client AI agent ที่ต้องการประเมินความแม่นยำก่อนใช้งานจริง

ข้อจำกัด Sandbox:
- สูงสุด **{SANDBOX_ITEM_LIMIT} items** ต่อ request
- ผลลัพธ์มี watermark `[SANDBOX]`
- ไม่บันทึกลง production database
- ไม่มีค่าใช้จ่าย

เมื่อพอใจกับ Confidence Score → ใช้ `POST /v1/customs/classify` (production)
    """,
)
async def sandbox_classify(request: SandboxRequest):
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    results = []
    total_duty = 0.0
    confidence_scores = []

    for idx, item in enumerate(request.items, start=1):
        # เรียก Classification Agent เหมือน production
        result = await classify_item(
            description=item.description,
            origin_country=item.origin_country,
        )

        total_price = (
            (item.quantity or 1) * (item.unit_price or 0)
            if item.unit_price else None
        )

        tax_result = lookup_tax_rate(result.hs_code or "", item.origin_country)
        duty_rate = _best_rate(tax_result)
        duty_amount = round(total_price * duty_rate, 2) if total_price else None
        vat_rate = tax_result.get("vat_rate", 0.07)
        vat_amount = round(total_price * vat_rate, 2) if total_price else None
        oga_result = check_restricted(result.hs_code or "")
        oga_required = bool(oga_result.get("is_restricted") or False)
        oga_agencies = [p.get("agency_abbr","") for p in oga_result.get("requires_permits",[])]

        if duty_amount:
            total_duty += duty_amount
        confidence_scores.append(result.confidence_score)

        results.append(SandboxResultItem(
            line_number=idx,
            description=item.description,
            hs_code=result.hs_code,
            hs_description=result.hs_description,
            confidence_score=result.confidence_score,
            source_reference=result.source_reference,
            duty_rate=duty_rate,
            duty_amount=duty_amount,
            vat_rate=vat_rate,
            vat_amount=vat_amount,
            oga_required=oga_required,
            oga_agencies=oga_agencies,
            notes=result.notes,
        ))

    avg_confidence = round(sum(confidence_scores) / len(confidence_scores), 3)

    return SandboxResponse(
        sandbox_session_id=session_id,
        client_id=request.client_id,
        disclaimer=(
            "This is a SANDBOX response. Results are for evaluation only. "
            "No transaction has been recorded. "
            "Use POST /v1/customs/classify for production."
        ),
        items=results,
        summary={
            "total_items": len(results),
            "avg_confidence_score": avg_confidence,
            "total_duty_estimate": round(total_duty, 2),
            "oga_flagged": sum(1 for r in results if r.oga_required),
            "ready_for_production": avg_confidence >= 0.80,
        },
        next_step=(
            "Confidence looks good — call POST /v1/customs/classify to go live."
            if avg_confidence >= 0.80
            else "Consider providing more detailed product descriptions to improve confidence."
        ),
    )


@router.get(
    "/info",
    summary="ข้อมูล Sandbox และเงื่อนไขการใช้งาน",
)
async def sandbox_info():
    return {
        "service": "AI TO AI HOLDING — Customs Intelligence Sandbox",
        "version": "1.0.0",
        "limits": {
            "max_items_per_request": SANDBOX_ITEM_LIMIT,
            "cost": "FREE",
            "data_retention": "NONE — sandbox results are not stored",
        },
        "capabilities": [
            "HS Code Classification",
            "Duty Rate Estimation",
            "VAT Estimation",
            "OGA / Controlled Goods Flag",
            "Confidence Score per item",
            "Source Reference (legal cite)",
        ],
        "production_endpoint": "POST /v1/customs/classify",
        "contact": "discovery@ai-to-ai-holding.internal",
    }