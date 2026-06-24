"""
invoice_service.py
Phase 8.1 — Invoice Intelligence Pipeline
Phase 15  — Validation Layer + Cache Reasoning + Rate Limit
Phase 17  — Tiered Pricing + Credit Deduction + Currency
classify ทุก line item + บันทึก DB + คืนสรุปทั้งใบ
"""

import uuid
import json
import hashlib
import asyncio
from datetime import datetime, timezone
from collections import defaultdict, deque
from typing import Optional

from db_adapter import get_pool
from normalize_description import normalize as normalize_description
from xai_reasoning import generate_reasoning


def _now():
    return datetime.now(timezone.utc)


async def _get_pool():
    USE_POSTGRES = True
    return await get_pool()


# ─── Phase 15.1: Invoice Validation Layer ────────────────────────────────────

def _validate_items(items: list, parsed: dict) -> dict:
    """
    ตรวจสอบ items ก่อนส่ง Claude — ประหยัดค่า API
    Returns: {"valid": [...], "blocked": [...], "warnings": [...]}
    """
    valid = []
    blocked = []
    warnings = []

    invoice_total = _safe_float(parsed.get("total_value"))

    for i, item in enumerate(items):
        line_no = i + 1
        desc = (item.get("description") or "").strip()
        lv = _safe_float(item.get("line_value"))
        qty = _safe_float(item.get("qty"))
        up = _safe_float(item.get("unit_price"))

        # BLOCK: description ว่างหรือสั้นเกินไป
        word_count = len(desc.split()) if desc else 0
        if word_count < 2:
            blocked.append({
                "line_no": line_no,
                "reason": "EMPTY_DESCRIPTION",
                "message": f"บรรทัด {line_no}: คำบรรยายสินค้าสั้นเกินไป ({word_count} คำ) — ต้องมีอย่างน้อย 2 คำ",
            })
            continue

        # BLOCK: ไม่มีมูลค่าเลย (ไม่มี line_value และไม่มีทั้ง qty + unit_price)
        has_value = lv is not None or (qty is not None and up is not None)
        if not has_value:
            blocked.append({
                "line_no": line_no,
                "reason": "NO_VALUE",
                "message": f"บรรทัด {line_no}: ไม่มีมูลค่าสินค้า (ต้องมี line_value หรือ qty + unit_price)",
            })
            continue

        # WARN: ไม่มี country_origin
        if not (item.get("country_origin") or "").strip():
            seller_country = parsed.get("seller_country") or ""
            if seller_country:
                warnings.append({
                    "line_no": line_no,
                    "type": "MISSING_ORIGIN",
                    "message": f"บรรทัด {line_no}: ไม่มีประเทศแหล่งกำเนิด — ใช้ประเทศผู้ขาย ({seller_country}) แทน",
                })
            else:
                warnings.append({
                    "line_no": line_no,
                    "type": "MISSING_ORIGIN",
                    "message": f"บรรทัด {line_no}: ไม่มีประเทศแหล่งกำเนิด — FTA อาจประเมินไม่ได้",
                })

        valid.append(item)

    # WARN: ผลรวม line_value ≠ invoice total เกิน 10%
    if invoice_total and valid:
        sum_lv = sum(
            _safe_float(it.get("line_value")) or (
                (_safe_float(it.get("qty")) or 0) * (_safe_float(it.get("unit_price")) or 0)
            )
            for it in valid
        )
        if sum_lv > 0 and abs(sum_lv - invoice_total) / invoice_total > 0.10:
            warnings.append({
                "line_no": 0,
                "type": "TOTAL_MISMATCH",
                "message": f"ผลรวมมูลค่ารายการ ({sum_lv:,.2f}) ≠ ยอดรวม invoice ({invoice_total:,.2f}) — ต่างกันเกิน 10%",
            })

    return {"valid": valid, "blocked": blocked, "warnings": warnings}


# ─── Phase 15.3: XAI Reasoning Cache ─────────────────────────────────────────

_reasoning_cache: dict = {}  # key → reasoning dict (in-memory, reset on restart)

def _reasoning_cache_key(hs_code: str, origin: str, dest: str) -> str:
    """Cache key สำหรับ XAI reasoning — เพราะ HS+origin+dest เดียวกัน → reasoning เหมือนกัน"""
    raw = f"{hs_code}|{origin}|{dest}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


async def _get_cached_reasoning(
    description: str, hs_code: str, confidence: float,
    origin: str, dest: str, duty_rate, fta_eligible: bool, oga_required: bool,
) -> dict:
    """ดึง reasoning จาก cache ถ้ามี — ไม่งั้นเรียก Claude แล้ว cache"""
    if not hs_code:
        return await generate_reasoning(
            description=description, hs_code=hs_code, confidence=confidence,
            origin_country=origin, dest_country=dest, duty_rate=duty_rate,
            fta_eligible=fta_eligible, oga_required=oga_required,
        )

    ckey = _reasoning_cache_key(hs_code, origin, dest)
    cached = _reasoning_cache.get(ckey)
    if cached:
        # อัพเดต confidence + warning ตาม item ปัจจุบัน
        result = dict(cached)
        result["confidence"] = round(confidence, 4)
        if confidence < 0.75:
            result["warning"] = f"ความมั่นใจต่ำ ({confidence:.0%}) — ควรตรวจสอบกับเจ้าหน้าที่ศุลกากรก่อนยื่น"
        elif confidence < 0.85:
            result["warning"] = f"ความมั่นใจปานกลาง ({confidence:.0%}) — แนะนำให้ตรวจสอบ key_factors"
        else:
            result["warning"] = None
        result["_source"] = "REASONING_CACHE"
        return result

    # Cache miss → เรียก Claude
    result = await generate_reasoning(
        description=description, hs_code=hs_code, confidence=confidence,
        origin_country=origin, dest_country=dest, duty_rate=duty_rate,
        fta_eligible=fta_eligible, oga_required=oga_required,
    )
    _reasoning_cache[ckey] = result
    return result


# ─── Phase 15.5: Per-User Invoice Rate Limit ─────────────────────────────────

_user_invoice_log: dict = defaultdict(deque)  # api_key → deque of timestamps
INVOICE_RATE_LIMIT_PER_MIN = 5    # max 5 invoices/min per user
INVOICE_RATE_LIMIT_PER_DAY = 100  # max 100 invoices/day per user

def _check_invoice_rate_limit(api_key: str) -> Optional[str]:
    """ตรวจ rate limit — return error message ถ้าเกิน, None ถ้าผ่าน"""
    now = _now().timestamp()
    log = _user_invoice_log[api_key]

    # ลบ entries เก่ากว่า 24 ชม.
    while log and now - log[0] > 86400:
        log.popleft()

    # เช็ค per-day
    if len(log) >= INVOICE_RATE_LIMIT_PER_DAY:
        return f"เกินโควตา {INVOICE_RATE_LIMIT_PER_DAY} invoices/วัน — กรุณารอ 24 ชม. หรืออัพเกรดแพ็กเกจ"

    # เช็ค per-minute
    one_min_ago = now - 60
    recent = sum(1 for t in log if t > one_min_ago)
    if recent >= INVOICE_RATE_LIMIT_PER_MIN:
        return f"เกินโควตา {INVOICE_RATE_LIMIT_PER_MIN} invoices/นาที — กรุณารอสักครู่"

    # ผ่าน — บันทึก
    log.append(now)
    return None


# ─── Classify 1 item ─────────────────────────────────────────────────────────

async def _classify_item(description: str, country_origin: str = "", dest_country: str = "TH") -> dict:
    """Cache-first → Claude fallback (ประหยัดค่า API)"""
    # 1. ลองดู cache ก่อน — ไม่เสียค่า Claude
    CACHE_CONFIDENCE_THRESHOLD = 0.80  # ต่ำกว่านี้ → ส่ง Claude ตรวจอีกรอบ
    try:
        from cache_classification import cache_lookup
        cached = await cache_lookup(None, description)
        if cached and cached.get("hs_code"):
            conf = float(cached.get("confidence_score") or 0)
            if conf >= CACHE_CONFIDENCE_THRESHOLD:
                # มั่นใจ → ใช้ cache เลย ฟรี
                return {
                    "hs_code": cached["hs_code"],
                    "hs_description": cached.get("hs_description") or "",
                    "confidence_score": conf,
                    "reasoning": None,
                    "_source": "CACHE",
                }
            # มีในคลังแต่มั่นใจน้อย → ส่ง Claude ตรวจ (fall through)
    except Exception:
        pass

    # 2. Cache miss หรือ low-conf → เรียก Claude
    _cache_fallback = None  # เก็บ cache ไว้ fallback ถ้า Claude error
    try:
        from cache_classification import cache_lookup as _cl2
        _cached2 = await _cl2(None, description)
        if _cached2 and _cached2.get("hs_code"):
            _cache_fallback = {
                "hs_code": _cached2["hs_code"],
                "hs_description": _cached2.get("hs_description") or "",
                "confidence_score": float(_cached2.get("confidence_score") or 0),
                "reasoning": None,
                "_source": "CACHE_FALLBACK",
            }
    except Exception:
        pass

    try:
        from agents_router import classify_item
        result = await classify_item(
            description=description,
            origin_country=country_origin,
        )
        if result is None:
            return _cache_fallback or {}

        # Phase 15.2: เก็บ top 3 candidates
        top3 = []
        if hasattr(result, "candidates") and result.candidates:
            for c in result.candidates[:3]:
                top3.append({
                    "rank": c.rank,
                    "hs_code": c.hs_code,
                    "hs_description": c.hs_description,
                    "hs_description_th": getattr(c, "hs_description_th", None),
                    "confidence_score": c.confidence_score,
                    "source_reference": c.source_reference,
                })

        cl = {
            "hs_code": result.hs_code,
            "hs_description": result.hs_description,
            "confidence_score": result.confidence_score,
            "reasoning": result.notes,
            "candidates": top3,  # Phase 15.2
            "_source": "CLAUDE",
        }
        # 3. บันทึกลง cache — ครั้งต่อไปไม่ต้องจ่าย
        try:
            from cache_classification import cache_save
            await cache_save(None, description, {
                "hs_code": result.hs_code,
                "hs_description": result.hs_description,
                "confidence_score": result.confidence_score,
            }, source="CLAUDE")
        except Exception:
            pass
        return cl
    except Exception as e:
        # Claude error (quota/timeout) → fallback ใช้ cache เดิมแม้ confidence ต่ำ
        if _cache_fallback:
            return _cache_fallback
        return {"error": str(e)}


async def _check_fta(hs_code: str, origin: str, dest: str = "TH") -> dict:
    try:
        from knowledge_service import get_fta_form
        result = get_fta_form(hs_code, origin) or {}
        return result
    except Exception:
        return {}


async def _lookup_duty_rate(hs_code: str, origin: str) -> dict:
    try:
        from knowledge_service import lookup_tax_rate
        return lookup_tax_rate(hs_code, origin) or {}
    except Exception:
        return {}


async def _check_oga(hs_code: str) -> dict:
    try:
        from oga_engine import check as oga_check
        return oga_check(hs_code) or {}
    except Exception:
        return {}


async def _check_halal(hs_code: str, dest_country: str) -> dict:
    try:
        from halal_engine import check as halal_check
        return halal_check(hs_code, dest_country) or {}
    except Exception:
        return {}


# ─── Save to DB ───────────────────────────────────────────────────────────────

async def _save_submission(pool, sub_id: str, client_key: str, filename: str,
                           parsed: dict, item_count: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO invoice_submissions
              (id, client_api_key, filename, file_type,
               invoice_no, invoice_date, seller_name, seller_country,
               buyer_name, buyer_country, incoterms, currency,
               total_value, item_count, status, raw_text, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,'PROCESSING',$15,$16)
            ON CONFLICT (id) DO NOTHING
        """,
            sub_id,
            client_key,
            filename,
            parsed.get("file_type", "UNKNOWN"),
            parsed.get("invoice_no"),
            _parse_date(parsed.get("invoice_date")),
            parsed.get("seller_name"),
            parsed.get("seller_country"),
            parsed.get("buyer_name"),
            parsed.get("buyer_country"),
            parsed.get("incoterms"),
            parsed.get("currency", "USD"),
            None,
            item_count,
            parsed.get("raw_text", "")[:5000],
            _now(),
        )


async def _save_item(pool, sub_id: str, line_no: int, item: dict, result: dict) -> None:
    cl = result.get("classification", result)
    fta = result.get("fta", {})
    oga = result.get("oga", {})
    halal = result.get("halal", {})

    hs_ai = cl.get("hs_code") or cl.get("hs_code_6")
    hs_declared = item.get("hs_code_declared")
    hs_match = None
    hs_mismatch = False
    if hs_declared and hs_ai:
        hs_match = hs_declared.replace(".", "")[:6] == hs_ai.replace(".", "")[:6]
        hs_mismatch = not hs_match

    unit_price = _safe_float(item.get("unit_price"))
    qty = _safe_float(item.get("qty"))
    line_value = _safe_float(item.get("line_value")) or (
        (unit_price * qty) if unit_price and qty else None
    )

    duty_rate = _safe_float(fta.get("duty_rate") or cl.get("duty_rate"))
    cif_usd = line_value  # TODO: convert currency if needed
    duty_est = (cif_usd * duty_rate / 100) if cif_usd and duty_rate else None
    fta_rate = _safe_float(fta.get("fta_rate"))
    fta_saving = None
    if cif_usd and duty_rate is not None and fta_rate is not None:
        fta_saving = cif_usd * (duty_rate - fta_rate) / 100

    _oga_permits = oga.get("requires_permits") or []
    oga_agencies = [p.get("agency_abbr") for p in _oga_permits if p.get("agency_abbr")]
    if isinstance(oga_agencies, str):
        oga_agencies = [oga_agencies]

    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO invoice_items
              (id, submission_id, line_no,
               description, description_norm,
               hs_code_declared, qty, unit, unit_price, line_value, currency,
               country_origin, marks_numbers,
               hs_code_ai, hs_code_final, hs_match, confidence, reasoning,
               cif_value_usd, duty_rate, duty_estimate_usd,
               fta_eligible, fta_agreement, fta_rate, fta_saving_usd,
               oga_required, oga_agencies, oga_details,
               halal_required, halal_cert_body,
               valuation_flag, valuation_note, hs_mismatch_flag,
               created_at)
            VALUES
              ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,
               $14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,
               $26,$27,$28,$29,$30,$31,$32,$33,$34)
            ON CONFLICT (id) DO NOTHING
        """,
            uuid.uuid4().hex,
            sub_id,
            line_no,
            item.get("description"),
            normalize_description(item.get("description", "")),
            hs_declared,
            qty,
            item.get("unit"),
            unit_price,
            line_value,
            item.get("currency"),
            item.get("country_origin"),
            item.get("marks_numbers"),
            hs_ai,
            hs_declared if (hs_match) else hs_ai,
            hs_match,
            _safe_float(cl.get("confidence_score") or cl.get("confidence")),
            cl.get("reasoning") or cl.get("explanation"),
            cif_usd,
            duty_rate,
            duty_est,
            bool(fta.get("eligible") or fta.get("fta_eligible")),
            fta.get("agreement") or fta.get("fta_name"),
            fta_rate,
            fta_saving,
            bool(oga.get("is_restricted")),
            oga_agencies,
            json.dumps(oga) if oga else None,
            bool(halal.get("halal_required")),
            halal.get("cert_body") or halal.get("certification_body"),
            False,   # valuation_flag — Phase 12
            None,    # valuation_note — Phase 12
            hs_mismatch,
            _now(),
        )


async def _mark_done(pool, sub_id: str, total_value: Optional[float], item_count: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE invoice_submissions
            SET status='DONE', total_value=$1, item_count=$2, completed_at=$3
            WHERE id=$4
        """, total_value, item_count, _now(), sub_id)


async def _mark_error(pool, sub_id: str, msg: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE invoice_submissions
            SET status='ERROR', error_msg=$1, completed_at=$2
            WHERE id=$3
        """, msg[:500], _now(), sub_id)


# ─── Main process function ────────────────────────────────────────────────────

async def _process_one_item(
    sem: asyncio.Semaphore,
    pool, sub_id: str,
    line_no: int, item: dict,
    dest_country: str, seller_country: str, invoice_currency: str
) -> dict:
    """Process 1 item ภายใต้ semaphore — classify + duty + FTA + OGA + Halal + XAI"""
    async with sem:
        desc = item.get("description") or ""
        origin = item.get("country_origin") or seller_country or ""

        # Classify (Claude API call)
        cl_result = await _classify_item(desc, origin, dest_country)
        hs_ai = cl_result.get("hs_code") or ""

        # Knowledge lookups — run FTA/OGA/Halal ขนานกัน (ทุกฟังก์ชันมี try/except ใน)
        tax_result = await _lookup_duty_rate(hs_ai, origin) if hs_ai else {}
        fta_result, oga_result, halal_result = await asyncio.gather(
            _check_fta(hs_ai, origin, dest_country),
            _check_oga(hs_ai),
            _check_halal(hs_ai, dest_country),
        )

        # เติม duty/fta rates
        if tax_result:
            cl_result["duty_rate"] = tax_result.get("mfn_rate")
            cl_result["applicable_rate"] = tax_result.get("applicable_rate")
        if fta_result.get("eligible") and tax_result:
            fta_result["duty_rate"] = tax_result.get("mfn_rate")
            fta_result["fta_rate"] = tax_result.get("fta_rate") or tax_result.get("applicable_rate")
            fta_result["agreement"] = fta_result.get("form")
            fta_result["fta_eligible"] = True

        # คำนวณตัวเลข
        lv = _safe_float(item.get("line_value")) or 0
        mfn_rate = _safe_float(cl_result.get("duty_rate")) or 0
        applicable_rate = _safe_float(cl_result.get("applicable_rate"))
        duty_rate = applicable_rate if applicable_rate is not None else mfn_rate
        duty_est = lv * duty_rate / 100
        fta_sav = lv * (mfn_rate - duty_rate) / 100 if mfn_rate > duty_rate else 0

        conf = cl_result.get("confidence_score") or cl_result.get("confidence") or 0
        fta_elig = bool(fta_result.get("eligible"))
        oga_req = bool(oga_result.get("is_restricted"))

        # XAI Reasoning — Phase 15.3: ใช้ cache (HS+origin+dest เดียวกัน = reasoning เดียวกัน)
        try:
            reasoning = await _get_cached_reasoning(
                description=desc, hs_code=hs_ai, confidence=float(conf),
                origin=origin, dest=dest_country, duty_rate=duty_rate,
                fta_eligible=fta_elig, oga_required=oga_req,
            )
        except Exception:
            reasoning = None

        # Phase 15.4: Log candidates สำหรับ learning feedback loop
        if cl_result.get("candidates") and cl_result.get("_source") == "CLAUDE":
            try:
                from cache_classification import log_candidates
                await log_candidates(None, sub_id, "PRODUCTION", desc, cl_result["candidates"])
            except Exception:
                pass

        # Save to DB
        combined = {"classification": cl_result, "fta": fta_result, "oga": oga_result, "halal": halal_result}
        await _save_item(pool, sub_id, line_no, item, combined)

        return {
            "line_no": line_no,
            "description": desc,
            "hs_code_declared": item.get("hs_code_declared"),
            "qty": item.get("qty"),
            "unit": item.get("unit"),
            "unit_price": item.get("unit_price"),
            "line_value": item.get("line_value"),
            "currency": item.get("currency") or invoice_currency,
            "country_origin": origin,
            "hs_code": hs_ai,
            "candidates": cl_result.get("candidates", []),  # Phase 15.2: Top 3
            "confidence": conf,
            "duty_rate": mfn_rate,
            "applicable_rate": duty_rate,
            "duty_estimate_usd": round(duty_est, 2),
            "fta_eligible": fta_elig,
            "fta_agreement": fta_result.get("form"),
            "fta_saving_usd": round(fta_sav, 2),
            "oga_required": oga_req,
            "oga_risk_level": oga_result.get("risk_level") or "HIGH",
            "oga_note_th": oga_result.get("note_th") or "",
            "oga_note_en": oga_result.get("note_en") or "",
            "oga_agencies": [p.get("agency_abbr") for p in (oga_result.get("requires_permits") or []) if p.get("agency_abbr")],
            "oga_permits": oga_result.get("requires_permits") or [],
            "halal_required": bool(halal_result.get("halal_required")),
            "halal_cert_body": halal_result.get("cert_body") or halal_result.get("certification_body"),
            "reasoning": reasoning,
            # internal fields for aggregation
            "_lv": lv, "_duty_est": duty_est, "_fta_sav": fta_sav,
            "_hs_declared": item.get("hs_code_declared"),
        }


async def process_invoice(client_api_key: str, filename: str, parsed: dict) -> dict:
    """
    รับ parsed dict จาก invoice_parser
    → validate → classify ทุก item พร้อมกัน (asyncio.gather) → บันทึก DB → คืนสรุป
    """
    # Phase 15.5: Rate limit check
    rate_err = _check_invoice_rate_limit(client_api_key)
    if rate_err:
        return {"error": rate_err, "error_code": "RATE_LIMIT", "items": [], "warnings": []}

    sub_id = uuid.uuid4().hex
    items_all = [it for it in (parsed.get("items") or []) if (it.get("description") or "").strip()]
    dest_country = parsed.get("buyer_country") or "TH"
    seller_country = parsed.get("seller_country") or ""
    invoice_currency = parsed.get("currency", "USD")

    # Phase 15.1: Validate items before sending to Claude
    validation = _validate_items(items_all, parsed)
    items_raw = validation["valid"]
    blocked_items = validation["blocked"]
    pre_warnings = validation["warnings"]

    pool = await _get_pool()
    await _save_submission(pool, sub_id, client_api_key, filename, parsed, len(items_raw))

    # Process ทุก valid item พร้อมกัน — จำกัด 4 concurrent เพื่อไม่ให้ DB pool หมด
    sem = asyncio.Semaphore(4)
    tasks = [
        _process_one_item(sem, pool, sub_id, i + 1, item, dest_country, seller_country, invoice_currency)
        for i, item in enumerate(items_raw)
    ]
    item_results = await asyncio.gather(*tasks, return_exceptions=True)

    # รวมผล + สร้าง warnings
    results = []
    total_duty = 0.0
    total_saving = 0.0
    total_value = 0.0
    warnings = list(pre_warnings)  # เริ่มจาก validation warnings

    # เพิ่ม blocked items เป็น warnings
    for b in blocked_items:
        warnings.append({"line_no": b["line_no"], "type": b["reason"], "message": b["message"]})

    for idx, r in enumerate(item_results):
        if isinstance(r, Exception):
            line_no = idx + 1
            desc = (items_raw[idx].get("description") or "")[:60] if idx < len(items_raw) else ""
            warnings.append({"line_no": line_no, "type": "ITEM_ERROR",
                "message": f"บรรทัด {line_no} — \"{desc}\" ประมวลผลไม่สำเร็จ ({str(r)[:80]}) "
                           f"→ กรุณาตรวจสอบด้วย Sandbox (/v1/classify)"})
            continue
        lv = r.pop("_lv", 0)
        duty_est = r.pop("_duty_est", 0)
        fta_sav = r.pop("_fta_sav", 0)
        hs_declared = r.pop("_hs_declared", None)
        total_value += lv
        total_duty += duty_est
        total_saving += fta_sav

        hs_ai = r.get("hs_code") or ""
        if hs_declared and hs_ai:
            if hs_declared.replace(".", "")[:6] != hs_ai.replace(".", "")[:6]:
                warnings.append({"line_no": r["line_no"], "type": "HS_MISMATCH",
                    "declared_hs": hs_declared, "ai_hs": hs_ai,
                    "desc": (r.get("description") or "")[:60],
                    "message": f"บรรทัด {r['line_no']}: HS ที่ระบุ {hs_declared} ≠ AI แนะนำ {hs_ai}"})
        if r.get("oga_required"):
            agencies = r.get("oga_agencies") or []
            warnings.append({"line_no": r["line_no"], "type": "OGA_REQUIRED",
                "agencies": agencies,
                "message": f"บรรทัด {r['line_no']}: ต้องขออนุญาต {', '.join(agencies)}"})
        results.append(r)

    # sort by line_no (gather ไม่รับประกัน order)
    results.sort(key=lambda x: x.get("line_no", 0))

    await _mark_done(pool, sub_id, total_value or None, len(results))

    # Phase 17: Credit deduction + exchange rate snapshot
    billing_info = await _deduct_credit(pool, client_api_key, len(results))
    exchange_snapshot = await _get_exchange_snapshot(invoice_currency)

    return {
        "submission_id": sub_id,
        "invoice_no": parsed.get("invoice_no"),
        "invoice_date": parsed.get("invoice_date"),
        "seller_country": parsed.get("seller_country"),
        "buyer_country": dest_country,
        "incoterms": parsed.get("incoterms"),
        "currency": parsed.get("currency", "USD"),
        "total_items": len(results),
        "total_blocked": len(blocked_items),
        "total_value_usd": round(total_value, 2),
        "total_duty_estimate_usd": round(total_duty, 2),
        "total_fta_saving_usd": round(total_saving, 2),
        "billing": billing_info,
        "exchange_rate": exchange_snapshot,
        "items": results,
        "warnings": warnings,
    }


# ─── Phase 17: Credit Deduction + Exchange Rate ──────────────────────────────

async def _deduct_credit(pool, client_api_key: str, item_count: int) -> dict:
    """
    หักเครดิตลูกค้าหลัง classify — ใช้ pricing_engine คำนวณราคาตาม tier
    คืน billing summary (ไม่ raise ถ้าหักไม่ได้ — แค่เตือน)
    """
    if item_count <= 0:
        return {"charged": False, "reason": "no_items"}
    try:
        from pricing_engine import get_deduct_amount
        hint = client_api_key[-8:]
        async with pool.acquire() as conn:
            # ดึง agent_id + tier จาก client_agents
            row = await conn.fetchrow(
                "SELECT id, profession FROM client_agents "
                "WHERE api_key_hint=$1 AND status='ACTIVE'", hint
            )
            if not row:
                return {"charged": False, "reason": "agent_not_found"}

            agent_id = row["id"]
            # Phase 18: ดึง membership discount
            tier = "STANDARD"
            membership_discount = 0.0
            try:
                from membership_engine import get_discount_for_agent, increment_usage
                membership_discount = await get_discount_for_agent(pool, agent_id)
            except Exception:
                pass
            amount = get_deduct_amount(item_count, tier=tier,
                                       membership_discount=membership_discount)

            # ตรวจ balance ก่อนหัก
            credit_row = await conn.fetchrow(
                "SELECT credit_balance FROM client_credits WHERE agent_id=$1",
                agent_id
            )
            balance = float(credit_row["credit_balance"]) if credit_row else 0.0

            if balance < amount:
                return {
                    "charged": False,
                    "reason": "insufficient_credit",
                    "required": amount,
                    "balance": balance,
                    "warning": "เครดิตไม่พอ — เติมเงินที่ POST /v1/billing/topup",
                }

            # หักเครดิต
            await conn.execute(
                "UPDATE client_credits SET credit_balance = credit_balance - $1 WHERE agent_id = $2",
                amount, agent_id
            )

            new_balance = balance - amount

            # Phase 18: increment usage counter for membership evaluation
            try:
                from membership_engine import increment_usage
                await increment_usage(pool, agent_id, item_count)
            except Exception:
                pass

            return {
                "charged": True,
                "amount_usd": amount,
                "tier": tier,
                "membership_discount_pct": round(membership_discount * 100, 1),
                "items_charged": item_count,
                "balance_before": round(balance, 4),
                "balance_after": round(new_balance, 4),
            }
    except Exception as e:
        # billing ไม่ควร block classification flow
        print(f"[BILLING] deduct error: {e}")
        return {"charged": False, "reason": f"error: {str(e)[:80]}"}


async def _get_exchange_snapshot(invoice_currency: str) -> Optional[dict]:
    """ดึง exchange rate snapshot ณ เวลาทำรายการ"""
    try:
        from currency_service import record_transaction_rate
        if invoice_currency.upper() != "USD":
            return await record_transaction_rate(invoice_currency, "USD")
        return {"from_currency": "USD", "to_currency": "USD", "rate": 1.0,
                "source": "identity"}
    except Exception as e:
        print(f"[CURRENCY] snapshot error: {e}")
        return None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _safe_float(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _parse_date(s):
    if not s:
        return None
    try:
        from datetime import date
        return date.fromisoformat(str(s)[:10])
    except Exception:
        pass
    return None
