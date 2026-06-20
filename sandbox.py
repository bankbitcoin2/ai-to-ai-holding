"""
api/sandbox.py
Sandbox API — Free Trial for Client AI Agents
กฎ Sandbox:
  - ไม่บันทึกลง production DB / ไม่คิดเงิน
  - จำกัด 3 items ต่อ request
  - จำกัด 5 calls/IP/วัน + 10 calls/IP/นาที
  - Sandbox ใช้ Claude จริงเสมอถ้ามี API key (ไม่ใช้ mock)
  - ผลลัพธ์มี watermark [SANDBOX]
"""
import os
import uuid
import time
from collections import defaultdict, deque
from datetime import datetime, timezone, date
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from knowledge_service import lookup_tax_rate, check_restricted

# ── ใช้ Claude จริงถ้ามี API key มิฉะนั้น fallback mock ──────
_HAS_REAL_API = bool(os.getenv("ANTHROPIC_API_KEY", ""))
if _HAS_REAL_API:
    from classification_agent import classify_item
else:
    from mock_classification_agent import classify_item


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
DAILY_LIMIT  = 5    # calls/IP/วัน
MINUTE_LIMIT = 10   # calls/IP/นาที

# ── In-memory rate limiter ─────────────────────────────────────
_daily:  dict = defaultdict(lambda: {"date": None, "count": 0})
_minute: dict = defaultdict(deque)


def _check_limits(ip: str):
    """คืน (calls_used_today, warning_msg|None) หรือ raise 429"""
    today = date.today().isoformat()
    now   = time.monotonic()

    # daily
    rec = _daily[ip]
    if rec["date"] != today:
        rec["date"]  = today
        rec["count"] = 0
    rec["count"] += 1
    used = rec["count"]

    if used > DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "SANDBOX_DAILY_LIMIT",
                "message": f"ใช้ครบ {DAILY_LIMIT} calls ฟรีวันนี้แล้ว — สมัครใช้งานจริงที่ POST /v1/register",
                "calls_used": used,
                "daily_limit": DAILY_LIMIT,
                "reset": "00:00 UTC",
            },
        )

    # per-minute
    dq = _minute[ip]
    cutoff = now - 60
    while dq and dq[0] < cutoff:
        dq.popleft()
    dq.append(now)
    if len(dq) > MINUTE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "RATE_LIMIT",
                "message": f"เรียกเร็วเกินไป — สูงสุด {MINUTE_LIMIT} calls/นาที",
                "retry_after_seconds": 60,
            },
        )

    warning = None
    if used >= DAILY_LIMIT - 1:
        remaining = DAILY_LIMIT - used
        warning = (
            f"⚠️ นี่คือ call ฟรีสุดท้ายของวันนี้ — สมัครเพื่อใช้ไม่จำกัดที่ POST /v1/register"
            if remaining <= 0
            else f"⚠️ เหลืออีก {remaining} call ฟรีวันนี้ — สมัครเพื่อใช้ไม่จำกัดที่ POST /v1/register"
        )

    return used, warning


# ── Models ────────────────────────────────────────────────────

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


# ── Endpoint ──────────────────────────────────────────────────

@router.post(
    "/classify",
    response_model=SandboxResponse,
    summary="ทดสอบจำแนก HS Code ฟรี (ไม่คิดเงิน)",
)
async def sandbox_classify(request: SandboxRequest, req: Request):
    # rate limit
    client_ip = (
        req.headers.get("x-forwarded-for", "")
        .split(",")[0].strip()
        or (req.client.host if req.client else "unknown")
    )
    calls_used, warning = _check_limits(client_ip)

    session_id = str(uuid.uuid4())
    results = []
    total_duty = 0.0
    confidence_scores = []

    for idx, item in enumerate(request.items, start=1):
        result = await classify_item(
            description=item.description,
            origin_country=item.origin_country,
        )

        total_price = (
            (item.quantity or 1) * (item.unit_price or 0)
            if item.unit_price else None
        )

        tax_result  = lookup_tax_rate(result.hs_code or "", item.origin_country)
        duty_rate   = _best_rate(tax_result)
        duty_amount = round(total_price * duty_rate, 2) if total_price else None
        vat_rate    = tax_result.get("vat_rate", 0.07)
        vat_amount  = round(total_price * vat_rate, 2) if total_price else None
        oga_result  = check_restricted(result.hs_code or "")
        oga_required = bool(oga_result.get("is_restricted") or False)
        oga_agencies = [p.get("agency_abbr", "") for p in oga_result.get("requires_permits", [])]

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
    remaining = max(0, DAILY_LIMIT - calls_used)

    next_step = warning or (
        "Confidence looks good — register at POST /v1/register to go live."
        if avg_confidence >= 0.80
        else "Consider providing more detailed product descriptions to improve confidence."
    )

    return SandboxResponse(
        sandbox_session_id=session_id,
        client_id=request.client_id,
        disclaimer=(
            f"SANDBOX — for evaluation only. No charge. "
            f"[{calls_used}/{DAILY_LIMIT} free calls used today, {remaining} remaining] "
            f"Production: POST /v1/customs/classify"
        ),
        items=results,
        summary={
            "total_items": len(results),
            "avg_confidence_score": avg_confidence,
            "total_duty_estimate": round(total_duty, 2),
            "oga_flagged": sum(1 for r in results if r.oga_required),
            "ready_for_production": avg_confidence >= 0.80,
            "free_calls_used_today": calls_used,
            "free_calls_remaining": remaining,
        },
        next_step=next_step,
    )


@router.get("/info", summary="ข้อมูล Sandbox และเงื่อนไขการใช้งาน")
async def sandbox_info():
    return {
        "service": "AI TO AI HOLDING — Customs Intelligence Sandbox",
        "version": "2.0.0",
        "engine": "Claude Sonnet (real)" if _HAS_REAL_API else "Mock (keyword matching)",
        "limits": {
            "max_items_per_request": SANDBOX_ITEM_LIMIT,
            "free_calls_per_day_per_ip": DAILY_LIMIT,
            "rate_limit_per_minute": MINUTE_LIMIT,
            "cost": "FREE",
            "data_retention": "NONE",
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
        "register_endpoint": "POST /v1/register",
        "contact": "discovery@ai-to-ai-holding.internal",
    }
