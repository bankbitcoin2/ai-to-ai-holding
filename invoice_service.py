"""
invoice_service.py
Phase 8.1 — Invoice Intelligence Pipeline
classify ทุก line item + บันทึก DB + คืนสรุปทั้งใบ
"""

import uuid
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional

from db_adapter import get_pool
from normalize_description import normalize as normalize_description
from xai_reasoning import generate_reasoning


def _now():
    return datetime.now(timezone.utc)


async def _get_pool():
    USE_POSTGRES = True
    return await get_pool()


# ─── Classify 1 item ─────────────────────────────────────────────────────────

async def _classify_item(description: str, country_origin: str = "", dest_country: str = "TH") -> dict:
    """Cache-first → Claude fallback (ประหยัดค่า API)"""
    # 1. ลองดู cache ก่อน — ไม่เสียค่า Claude
    try:
        from cache_classification import cache_lookup
        cached = await cache_lookup(None, description)
        if cached and cached.get("hs_code"):
            return {
                "hs_code": cached["hs_code"],
                "hs_description": cached.get("hs_description") or "",
                "confidence_score": float(cached.get("confidence_score") or 0),
                "reasoning": None,
                "_source": "CACHE",
            }
    except Exception:
        pass

    # 2. Cache miss → เรียก Claude
    try:
        from classification_agent import classify_item
        result = await classify_item(
            description=description,
            origin_country=country_origin,
        )
        if result is None:
            return {}
        cl = {
            "hs_code": result.hs_code,
            "hs_description": result.hs_description,
            "confidence_score": result.confidence_score,
            "reasoning": result.notes,
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
        from oga_engine import check_oga
        return check_oga(hs_code) or {}
    except Exception:
        return {}


async def _check_halal(hs_code: str, dest_country: str) -> dict:
    try:
        from halal_engine import check_halal_requirement
        return check_halal_requirement(hs_code, dest_country) or {}
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

    oga_agencies = oga.get("agencies") or oga.get("required_agencies") or []
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
               valuation_flag, hs_mismatch_flag,
               created_at)
            VALUES
              ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,
               $14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,
               $26,$27,$28,$29,$30,$31,$32,$33)
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
            bool(oga.get("required") or oga.get("oga_required")),
            oga_agencies,
            json.dumps(oga) if oga else None,
            bool(halal.get("required") or halal.get("halal_required")),
            halal.get("cert_body") or halal.get("certification_body"),
            False,   # valuation_flag — Phase 12
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
        oga_req = bool(oga_result.get("required") or oga_result.get("oga_required"))

        # XAI Reasoning (Claude API call)
        try:
            reasoning = await generate_reasoning(
                description=desc,
                hs_code=hs_ai,
                confidence=float(conf),
                origin_country=origin,
                dest_country=dest_country,
                duty_rate=duty_rate,
                fta_eligible=fta_elig,
                oga_required=oga_req,
            )
        except Exception:
            reasoning = None

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
            "confidence": conf,
            "duty_rate": mfn_rate,
            "applicable_rate": duty_rate,
            "duty_estimate_usd": round(duty_est, 2),
            "fta_eligible": fta_elig,
            "fta_agreement": fta_result.get("form"),
            "fta_saving_usd": round(fta_sav, 2),
            "oga_required": oga_req,
            "oga_agencies": oga_result.get("agencies") or [],
            "halal_required": bool(halal_result.get("required")),
            "halal_cert_body": halal_result.get("cert_body") or halal_result.get("certification_body"),
            "reasoning": reasoning,
            # internal fields for aggregation
            "_lv": lv, "_duty_est": duty_est, "_fta_sav": fta_sav,
            "_hs_declared": item.get("hs_code_declared"),
        }


async def process_invoice(client_api_key: str, filename: str, parsed: dict) -> dict:
    """
    รับ parsed dict จาก invoice_parser
    → classify ทุก item พร้อมกัน (asyncio.gather) → บันทึก DB → คืนสรุป
    """
    sub_id = uuid.uuid4().hex
    items_raw = [it for it in (parsed.get("items") or []) if (it.get("description") or "").strip()]
    dest_country = parsed.get("buyer_country") or "TH"
    seller_country = parsed.get("seller_country") or ""
    invoice_currency = parsed.get("currency", "USD")

    pool = await _get_pool()
    await _save_submission(pool, sub_id, client_api_key, filename, parsed, len(items_raw))

    # Process ทุก item พร้อมกัน — จำกัด 4 concurrent เพื่อไม่ให้ DB pool หมด
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
    warnings = []

    for r in item_results:
        if isinstance(r, Exception):
            continue  # skip failed items
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
                    "message": f"บรรทัด {r['line_no']}: HS ที่ระบุ {hs_declared} ≠ AI แนะนำ {hs_ai}"})
        if r.get("oga_required"):
            agencies = r.get("oga_agencies") or []
            warnings.append({"line_no": r["line_no"], "type": "OGA_REQUIRED",
                "message": f"บรรทัด {r['line_no']}: ต้องขออนุญาต {', '.join(agencies)}"})
        results.append(r)

    # sort by line_no (gather ไม่รับประกัน order)
    results.sort(key=lambda x: x.get("line_no", 0))

    await _mark_done(pool, sub_id, total_value or None, len(results))

    return {
        "submission_id": sub_id,
        "invoice_no": parsed.get("invoice_no"),
        "invoice_date": parsed.get("invoice_date"),
        "seller_country": parsed.get("seller_country"),
        "buyer_country": dest_country,
        "incoterms": parsed.get("incoterms"),
        "currency": parsed.get("currency", "USD"),
        "total_items": len(results),
        "total_value_usd": round(total_value, 2),
        "total_duty_estimate_usd": round(total_duty, 2),
        "total_fta_saving_usd": round(total_saving, 2),
        "items": results,
        "warnings": warnings,
    }


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
