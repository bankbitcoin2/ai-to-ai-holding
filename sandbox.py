"""
sandbox.py — Free Trial Endpoint
- 5 calls/IP/day  |  10 calls/IP/minute
- Uses real Claude if ANTHROPIC_API_KEY set, else mock
- All errors return JSON (no plain-text 500)
"""
import os, uuid, time
from collections import defaultdict, deque
from datetime import datetime, timezone, date
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from knowledge_service import lookup_tax_rate, check_restricted

_HAS_REAL_API = bool(os.getenv("ANTHROPIC_API_KEY", ""))
if _HAS_REAL_API:
    from classification_agent import classify_item
else:
    from mock_classification_agent import classify_item

def _best_rate(t: dict) -> float:
    if not t or t.get("status") in ("unavailable","error","no_data"):
        return 0.05
    fta = t.get("best_fta")
    if fta and fta.get("rate") is not None:
        return float(fta["rate"]) / 100.0
    g = t.get("general_rate")
    return float(g) / 100.0 if g is not None else 0.05

router = APIRouter(prefix="/v1/sandbox", tags=["Sandbox (Free Trial)"])
ITEM_LIMIT   = 3
DAILY_LIMIT  = 5
MINUTE_LIMIT = 10

_daily:  dict = defaultdict(lambda: {"date": None, "count": 0})
_minute: dict = defaultdict(deque)

def _check(ip: str):
    today = date.today().isoformat()
    now   = time.monotonic()
    rec = _daily[ip]
    if rec["date"] != today:
        rec["date"] = today; rec["count"] = 0
    rec["count"] += 1
    used = rec["count"]
    if used > DAILY_LIMIT:
        raise HTTPException(429, detail={
            "error": "DAILY_LIMIT_REACHED",
            "message": f"ใช้ครบ {DAILY_LIMIT} calls ฟรีวันนี้แล้ว สมัครใช้งานจริงที่ POST /v1/register",
            "reset": "00:00 UTC"
        })
    dq = _minute[ip]
    cutoff = now - 60
    while dq and dq[0] < cutoff: dq.popleft()
    dq.append(now)
    if len(dq) > MINUTE_LIMIT:
        raise HTTPException(429, detail={
            "error": "RATE_LIMIT",
            "message": f"เรียกเร็วเกินไป สูงสุด {MINUTE_LIMIT} calls/นาที",
            "retry_after_seconds": 60
        })
    warn = None
    rem = DAILY_LIMIT - used
    if rem <= 1:
        warn = f"เหลืออีก {rem} call ฟรีวันนี้ สมัครที่ POST /v1/register เพื่อใช้ไม่จำกัด"
    return used, warn

class Item(BaseModel):
    description: str
    origin_country: Optional[str] = None
    unit_price: Optional[float] = None
    quantity: Optional[float] = None

class SandboxReq(BaseModel):
    client_id: str = "sandbox-demo"
    destination_country: Optional[str] = "TH"
    items: list[Item] = Field(..., min_length=1, max_length=ITEM_LIMIT)

class CandidateItem(BaseModel):
    rank: int
    hs_code: Optional[str]
    hs_code_11: Optional[str]       # Thai 11-digit
    hs_description: Optional[str]
    hs_description_th: Optional[str]
    confidence_score: float
    source_reference: str
    notes: Optional[str]

class ResultItem(BaseModel):
    line_number: int
    description: str
    # best candidate (backward compat)
    hs_code: Optional[str]
    hs_code_11: Optional[str]
    hs_description: Optional[str]
    hs_description_th: Optional[str]
    confidence_score: float
    source_reference: str
    duty_rate: float
    duty_amount: Optional[float]
    vat_rate: float
    vat_amount: Optional[float]
    oga_required: bool = False
    oga_agencies: list[str] = []
    notes: Optional[str]
    candidates: list[CandidateItem] = []   # ranked list >= 75%
    watermark: str = "[SANDBOX — NOT FOR PRODUCTION USE]"

class SandboxResp(BaseModel):
    sandbox_session_id: str
    client_id: str
    mode: str = "SANDBOX"
    disclaimer: str
    items: list[ResultItem]
    summary: dict
    next_step: str

@router.post("/classify", response_model=SandboxResp,
             summary="ทดสอบจำแนก HS Code ฟรี")
async def sandbox_classify(body: SandboxReq, req: Request):
    ip = (req.headers.get("x-forwarded-for","").split(",")[0].strip()
          or (req.client.host if req.client else "unknown"))
    used, warn = _check(ip)

    results, duties, scores = [], 0.0, []
    try:
        for i, item in enumerate(body.items, 1):
            cls = await classify_item(description=item.description,
                                       origin_country=item.origin_country)
            price = ((item.quantity or 1) * item.unit_price) if item.unit_price else None
            try:
                tax = lookup_tax_rate(cls.hs_code or "", item.origin_country)
            except Exception:
                tax = {"status": "unavailable"}
            dr = _best_rate(tax)
            da = round(price * dr, 2) if price else None
            vr = float(tax.get("vat_rate") or 0.07)
            va = round(price * vr, 2) if price else None
            try:
                oga = check_restricted(cls.hs_code or "")
            except Exception:
                oga = {"is_restricted": False, "requires_permits": []}
            if da: duties += da
            scores.append(cls.confidence_score)
            candidates_out = [
                CandidateItem(
                    rank=c.rank,
                    hs_code=c.hs_code,
                    hs_code_11=c.hs_code_11,
                    hs_description=c.hs_description,
                    hs_description_th=c.hs_description_th,
                    confidence_score=c.confidence_score,
                    source_reference=c.source_reference,
                    notes=c.notes,
                ) for c in cls.candidates
            ]
            best = cls.best
            results.append(ResultItem(
                line_number=i, description=item.description,
                hs_code=best.hs_code if best else None,
                hs_code_11=best.hs_code_11 if best else None,
                hs_description=best.hs_description if best else None,
                hs_description_th=best.hs_description_th if best else None,
                confidence_score=cls.confidence_score,
                source_reference=cls.source_reference,
                duty_rate=dr, duty_amount=da, vat_rate=vr, vat_amount=va,
                oga_required=bool(oga.get("is_restricted")),
                oga_agencies=[p.get("agency_abbr","") for p in oga.get("requires_permits",[]) if isinstance(p,dict)],
                notes=cls.notes,
                candidates=candidates_out,
            ))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail={"error": "CLASSIFICATION_ERROR", "message": str(e)})

    avg = round(sum(scores)/len(scores), 3)
    rem = max(0, DAILY_LIMIT - used)
    nxt = warn or (
        "Confidence good — register at POST /v1/register to go live."
        if avg >= 0.75 else
        "Low confidence — provide more product details for better results."
    )
    disc = f"SANDBOX only. [{used}/{DAILY_LIMIT} calls today, {rem} left] Production: POST /v1/customs/classify"

    return SandboxResp(
        sandbox_session_id=str(uuid.uuid4()),
        client_id=body.client_id,
        disclaimer=disc,
        items=results,
        summary={
            "total_items": len(results),
            "avg_confidence_score": avg,
            "total_duty_estimate": round(duties, 2),
            "oga_flagged": sum(1 for r in results if r.oga_required),
            "ready_for_production": avg >= 0.75,
            "free_calls_used_today": used,
            "free_calls_remaining": rem,
        },
        next_step=nxt,
    )

# ── Feedback Endpoint ─────────────────────────────────────────────────────────
class FeedbackReq(BaseModel):
    log_id: str
    status: str     # CONFIRMED | REJECTED | AMENDED
    amended_hs_code: Optional[str] = None
    feedback_by: str = "client"

@router.post("/feedback", summary="ส่ง feedback ผล HS Classification")
async def sandbox_feedback(body: FeedbackReq):
    if body.status not in ("CONFIRMED", "REJECTED", "AMENDED"):
        raise HTTPException(400, detail={"error": "INVALID_STATUS",
            "message": "status must be CONFIRMED | REJECTED | AMENDED"})
    try:
        from database import get_db
        from cache_classification import submit_feedback
        async with get_db() as db:
            ok = await submit_feedback(db, body.log_id, body.status,
                                       body.amended_hs_code, body.feedback_by)
        if not ok:
            raise HTTPException(404, detail={"error": "LOG_NOT_FOUND",
                "message": f"log_id {body.log_id} not found"})
        return {"received": True, "log_id": body.log_id, "action": body.status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail={"error": "FEEDBACK_ERROR", "message": str(e)})

# ── CKAN Probe Endpoint (debug — ดู field structure ของ tariff resource) ──────
@router.get("/probe-ckan", summary="Probe CKAN tariff resource fields")
async def probe_ckan(hs: str = "6802"):
    try:
        from knowledge_service import fetch_hs_full
        result = await fetch_hs_full(hs)
        return result
    except Exception as e:
        return {"error": str(e)}
