"""
sandbox.py — Free Trial Endpoint
- 5 calls/IP/day  |  10 calls/IP/minute
- Uses real Claude if ANTHROPIC_API_KEY set, else mock
- All errors return JSON (no plain-text 500)
"""
import asyncio
import os, uuid, time
from collections import defaultdict, deque
from datetime import datetime, timezone, date
from typing import Optional

import time
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from knowledge_service import lookup_tax_rate, check_restricted

_HAS_REAL_API = bool(os.getenv("ANTHROPIC_API_KEY", ""))
if _HAS_REAL_API:
    from classification_agent import classify_item
else:
    from mock_classification_agent import classify_item

_CLASSIFY_SEM = asyncio.Semaphore(5)

def _best_rate(t: dict) -> float:
    if not t or t.get("status") in ("unavailable","error","no_data"):
        return 0.05
    fta = t.get("best_fta")
    if fta and fta.get("rate") is not None:
        return float(fta["rate"]) / 100.0
    g = t.get("general_rate")
    return float(g) / 100.0 if g is not None else 0.05

router = APIRouter(prefix="/v1/sandbox", tags=["Sandbox (Free Trial)"])
ITEM_LIMIT   = 5
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

class OGAPermit(BaseModel):
    agency_abbr: str
    name_th: Optional[str] = None
    name_en: Optional[str] = None
    url: Optional[str] = None
    permit_type: Optional[str] = None

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
    oga_permits: list[OGAPermit] = []
    oga_note_th: Optional[str] = None
    oga_note_en: Optional[str] = None
    oga_risk_level: Optional[str] = None
    # Halal
    halal_required: bool = False
    halal_risk_level: Optional[str] = None
    halal_authority: Optional[str] = None
    halal_note: Optional[str] = None
    # FTA info
    fta_eligible: bool = False
    fta_form: Optional[str] = None
    fta_note_th: Optional[str] = None
    fta_eligible_countries: list[str] = []
    fta_details: list[dict] = []
    # Financial estimates
    fta_mfn_rate: Optional[float] = None        # MFN rate ก่อน FTA
    fta_saving_amount: Optional[float] = None   # ประหยัดได้ถ้าใช้ FTA
    import_total_estimate: Optional[float] = None  # duty + VAT รวม
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

    from cache_service import cache_get, cache_set as _cache_set
    from knowledge_service import get_hs_description as _get_desc, get_fta_form as _get_fta, get_hs_description_db as _get_desc_db, get_fta_form_db as _get_fta_db, _fta_note_th
    from knowledge_service import lookup_tax_rate, check_restricted, check_halal

    results, duties, scores = [], 0.0, []
    _t_start = time.time()

    # ── Phase 1: classify ทุก item parallel (cache-first, semaphore 5) ──
    async def _classify_one_sb(item):
        _cached = await cache_get(item.description, item.origin_country)
        if _cached:
            _db_d_c = await _get_desc_db(_cached.get("hs_code", ""))
            _th_desc = _db_d_c.get("th") or None
            _en_desc = _db_d_c.get("en") or _cached.get("hs_description")
            _conf = float(_cached.get("confidence_score", 0.85))
            _src = _cached.get("source_reference", "Cache")
            _notes_c = _cached.get("notes")
            _hs_c = _cached.get("hs_code")
            class _FakeBest:
                rank = 1; hs_code = _hs_c; hs_code_11 = None
                hs_description = _en_desc; hs_description_th = _th_desc
                confidence_score = _conf; source_reference = _src; notes = _notes_c
            _best_inst = _FakeBest()
            class _FakeCls:
                hs_code = _hs_c; confidence_score = _conf
                source_reference = _src; notes = _notes_c
                best = _best_inst; candidates = [_best_inst]
            return _FakeCls()
        # Cache miss → Claude ผ่าน semaphore
        async with _CLASSIFY_SEM:
            cls = await classify_item(description=item.description,
                                      origin_country=item.origin_country)
        for _c in cls.candidates:
            if _c.hs_code and not _c.hs_description_th:
                try:
                    _cd = await _get_desc_db(_c.hs_code)
                    if _cd.get("th"): _c.hs_description_th = _cd["th"]
                    if _cd.get("en") and not _c.hs_description: _c.hs_description = _cd["en"]
                except Exception:
                    pass
        if cls.hs_code and cls.confidence_score >= 0.75:
            try:
                await _cache_set(
                    description=item.description, origin_country=item.origin_country,
                    hs_code=cls.hs_code,
                    hs_description=cls.hs_description if hasattr(cls, "hs_description") else (cls.best.hs_description if cls.best else None),
                    confidence_score=cls.confidence_score,
                    source_reference=cls.source_reference, notes=cls.notes,
                    model_used="claude" if _HAS_REAL_API else "mock",
                )
            except Exception as _ce:
                print(f"[CACHE] save warning: {_ce}")
        return cls

    cls_results = await asyncio.gather(*[_classify_one_sb(item) for item in body.items])

    try:
        for i, (item, cls) in enumerate(zip(body.items, cls_results), 1):
            price = ((item.quantity or 1) * item.unit_price) if item.unit_price else None
            try:
                tax = lookup_tax_rate(cls.hs_code or "", item.origin_country)
            except Exception:
                tax = {"status": "unavailable"}
            # ── Enrich FTA จาก DB/bundled ──────────────────────────────
            _fta_info: dict = {"eligible": False, "form": None, "all_eligible_countries": [], "fta_details": []}
            if cls.hs_code:
                try:
                    _fta_db = await _get_fta_db(cls.hs_code, item.origin_country or "")
                    if _fta_db.get("eligible") or _fta_db.get("all_eligible_countries"):
                        _fta_info = _fta_db
                        tax["fta_form"] = _fta_db.get("form")
                        tax["fta_eligible_countries"] = _fta_db.get("all_eligible_countries", [])
                        tax["fta_source"] = _fta_db.get("source", "bundled")
                except Exception:
                    pass
            dr = _best_rate(tax)
            da = round(price * dr, 2) if price else None
            vr = float(tax.get("vat_rate") or 0.07)
            va = round(price * vr, 2) if price else None
            # FTA saving estimate
            _mfn_rate = float(tax.get("mfn_rate") or tax.get("general_rate") or dr)
            _fta_saving = round(price * (_mfn_rate - dr), 2) if (price and _fta_info.get("eligible") and _mfn_rate > dr) else None
            _import_total = round((da or 0) + (va or 0), 2) if (da is not None or va is not None) else None
            try:
                oga = check_restricted(cls.hs_code or "")
            except Exception:
                oga = {"is_restricted": False, "requires_permits": []}
            _halal: dict = {"halal_required": False, "risk_level": "NONE"}
            try:
                _halal = check_halal(cls.hs_code or "", body.destination_country or "TH")
            except Exception:
                pass
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
            permits_raw = [p for p in oga.get("requires_permits", []) if isinstance(p, dict)]
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
                oga_agencies=[p.get("agency_abbr", "") for p in permits_raw],
                oga_permits=[
                    OGAPermit(
                        agency_abbr=p.get("agency_abbr", ""),
                        name_th=p.get("name_th"),
                        name_en=p.get("name_en"),
                        url=p.get("url"),
                        permit_type=p.get("permit_type"),
                    ) for p in permits_raw
                ],
                oga_note_th=oga.get("note_th"),
                oga_note_en=oga.get("note_en"),
                oga_risk_level=oga.get("risk_level"),
                fta_eligible=bool(_fta_info.get("eligible")),
                fta_form=_fta_info.get("form"),
                fta_note_th=_fta_note_th(_fta_info.get("form")),
                fta_eligible_countries=_fta_info.get("all_eligible_countries", []),
                fta_details=_fta_info.get("fta_details", []),
                fta_mfn_rate=_mfn_rate if _fta_info.get("eligible") else None,
                fta_saving_amount=_fta_saving,
                import_total_estimate=_import_total,
                halal_required=bool(_halal.get("halal_required")),
                halal_risk_level=_halal.get("risk_level"),
                halal_authority=(_halal.get("destination_info") or {}).get("authority"),
                halal_note=_halal.get("notes"),
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

    # ── Log call ─────────────────────────────────────────────────────────
    try:
        from billing import log_agent_call
        _latency = int((time.time() - _t_start) * 1000)
        await log_agent_call(
            agent_id="sandbox",
            endpoint="/v1/sandbox/classify",
            status_code=200,
            latency_ms=_latency,
            session_id=str(body.items[0].description[:32]) if body.items else None
        )
    except Exception:
        pass
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
            "halal_flagged": sum(1 for r in results if r.halal_required),
            "fta_eligible": sum(1 for r in results if r.fta_eligible),
            "fta_saving_total": round(sum(r.fta_saving_amount or 0 for r in results), 2),
            "import_total_estimate": round(sum(r.import_total_estimate or 0 for r in results), 2),
            "oga_high_risk": sum(1 for r in results if r.oga_risk_level == "HIGH"),
            "ready_for_production": avg >= 0.75,
            "free_calls_used_today": used,
            "free_calls_remaining": rem,
        },
        next_step=nxt,
    )

# ── Feedback Endpoint ─────────────────────────────────────────────────────────

class FeedbackReq(BaseModel):
    log_id: str = Field(..., description="log_id จาก classify response candidates")
    status: str = Field(..., description="CONFIRMED | REJECTED | AMENDED")
    amended_hs_code: Optional[str] = Field(None, description="HS code ที่ถูกต้อง (กรณี AMENDED)")
    feedback_by: str = Field("client", description="ผู้ส่ง feedback")


@router.post("/feedback", summary="ส่ง feedback ผล HS Classification — ปรับ learning loop")
async def sandbox_feedback(body: FeedbackReq):
    """
    ส่ง feedback กลับระบบ:
    - CONFIRMED  → boost confidence +0.05, source → CONFIRMED
    - REJECTED   → reduce confidence -0.10, source → REJECTED
    - AMENDED    → บันทึก hs_code ที่ถูกต้อง, source → CONFIRMED
    ผลถูก process ทันทีผ่าน cache_feedback_queue
    """
    if body.status not in ("CONFIRMED", "REJECTED", "AMENDED"):
        raise HTTPException(400, detail={"error": "INVALID_STATUS",
            "message": "status must be CONFIRMED | REJECTED | AMENDED"})
    try:
        from cache_classification import submit_feedback
        ok = await submit_feedback(None, body.log_id, body.status,
                                   body.amended_hs_code, body.feedback_by)
        if not ok:
            raise HTTPException(404, detail={"error": "LOG_NOT_FOUND",
                "message": f"log_id '{body.log_id}' not found or invalid"})
        return {
            "received": True,
            "log_id": body.log_id,
            "action": body.status,
            "effect": (
                "confidence boosted → CONFIRMED" if body.status == "CONFIRMED"
                else "confidence reduced → REJECTED" if body.status == "REJECTED"
                else f"cache updated with hs_code={body.amended_hs_code} → CONFIRMED"
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail={"error": "FEEDBACK_ERROR", "message": str(e)})


# ── Halal Countries Endpoint ──────────────────────────────────────────────────

@router.get("/halal-countries", summary="รายชื่อประเทศที่ต้องการ Halal Certification (21 ประเทศ)")
async def halal_countries(region: Optional[str] = None):
    """
    คืนรายชื่อ 21 ประเทศที่กำหนดให้สินค้าต้องมี Halal Certification
    พร้อม authority และ region
    - region filter: GCC | SEA | Middle East | South Asia | North Africa | West Africa
    """
    try:
        from halal_engine import HALAL_MANDATORY_COUNTRIES
        data = [
            {
                "code":      code,
                "name":      info["name"],
                "region":    info["region"],
                "authority": info["authority"],
            }
            for code, info in HALAL_MANDATORY_COUNTRIES.items()
            if (region is None or info["region"].lower() == region.lower())
        ]
        regions = sorted({info["region"] for info in HALAL_MANDATORY_COUNTRIES.values()})
        return {
            "total":     len(data),
            "regions":   regions,
            "countries": data,
        }
    except Exception as e:
        raise HTTPException(500, detail={"error": "HALAL_ENGINE_ERROR", "message": str(e)})


# ── CKAN Probe Endpoint (debug) ───────────────────────────────────────────────
@router.get("/probe-ckan", summary="Probe CKAN tariff resource fields")
async def probe_ckan(hs: str = "6802"):
    try:
        from knowledge_service import fetch_hs_full
        result = await fetch_hs_full(hs)
        return result
    except Exception as e:
        return {"error": str(e)}
