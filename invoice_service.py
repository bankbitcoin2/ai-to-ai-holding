"""
invoice_service.py
Phase 8.1 — Invoice Intelligence Pipeline
classify ทุก line item + บันทึก DB + คืนสรุปทั้งใบ
"""

import uuid
import json
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
    """ใช้ classification_agent (เหมือน sandbox)"""
    try:
        from classification_agent import classify_item
        result = await classify_item(
            description=description,
            origin_country=country_origin,
        )
        if result is None:
            return {}
        # ClassificationResult is a dataclass — convert to plain dict
        return {
            "hs_code": result.hs_code,
            "hs_description": result.hs_description,
            "confidence_score": result.confidence_score,
            "reasoning": result.notes,
        }
    except Exception as e:
        return {"error": str(e)}


async def _check_fta(hs_code: str, origin: str, dest: str = "TH") -> dict:
    try:
        from knowledge_service import check_fta_eligibility
        return await check_fta_eligibility(hs_code, origin, dest) or {}
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

async def process_invoice(client_api_key: str, filename: str, parsed: dict) -> dict:
    """
    รับ parsed dict จาก invoice_parser
    → classify ทุก item → บันทึก DB → คืนสรุป
    """
    sub_id = uuid.uuid4().hex
    items_raw = parsed.get("items") or []
    dest_country = parsed.get("buyer_country") or "TH"

    pool = await _get_pool()

    # บันทึก submission header
    await _save_submission(pool, sub_id, client_api_key, filename, parsed, len(items_raw))

    results = []
    total_duty = 0.0
    total_saving = 0.0
    total_value = 0.0
    warnings = []

    for i, item in enumerate(items_raw):
        desc = item.get("description") or ""
        if not desc.strip():
            continue

        origin = item.get("country_origin") or parsed.get("seller_country") or ""

        # Classify
        cl_result = await _classify_item(desc, origin, dest_country)
        hs_ai = cl_result.get("hs_code") or cl_result.get("hs_code_6") or ""

        # FTA / OGA / Halal
        fta_result = await _check_fta(hs_ai, origin, dest_country) if hs_ai else {}
        oga_result = await _check_oga(hs_ai) if hs_ai else {}
        halal_result = await _check_halal(hs_ai, dest_country) if hs_ai else {}

        combined = {
            "classification": cl_result,
            "fta": fta_result,
            "oga": oga_result,
            "halal": halal_result,
        }

        # บันทึก item
        await _save_item(pool, sub_id, i + 1, item, combined)

        # รวมตัวเลข
        lv = _safe_float(item.get("line_value")) or 0
        total_value += lv

        duty_rate = _safe_float(fta_result.get("duty_rate") or cl_result.get("duty_rate")) or 0
        fta_rate = _safe_float(fta_result.get("fta_rate"))
        duty_est = lv * duty_rate / 100
        fta_sav = lv * (duty_rate - (fta_rate or duty_rate)) / 100 if fta_rate is not None else 0
        total_duty += duty_est
        total_saving += fta_sav

        # Warnings
        hs_declared = item.get("hs_code_declared")
        if hs_declared and hs_ai:
            if hs_declared.replace(".", "")[:6] != hs_ai.replace(".", "")[:6]:
                warnings.append({
                    "line_no": i + 1,
                    "type": "HS_MISMATCH",
                    "message": f"บรรทัด {i+1}: HS ที่ระบุ {hs_declared} ≠ AI แนะนำ {hs_ai}"
                })

        if oga_result.get("required") or oga_result.get("oga_required"):
            agencies = oga_result.get("agencies") or []
            warnings.append({
                "line_no": i + 1,
                "type": "OGA_REQUIRED",
                "message": f"บรรทัด {i+1}: ต้องขออนุญาต {', '.join(agencies)}"
            })

        conf = cl_result.get("confidence_score") or cl_result.get("confidence") or 0
        fta_elig = bool(fta_result.get("eligible"))
        oga_req = bool(oga_result.get("required") or oga_result.get("oga_required"))

        # XAI Reasoning
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

        results.append({
            "line_no": i + 1,
            "description": desc,
            "hs_code": hs_ai,
            "confidence": conf,
            "duty_rate": duty_rate,
            "duty_estimate_usd": round(duty_est, 2),
            "fta_eligible": fta_elig,
            "fta_saving_usd": round(fta_sav, 2),
            "oga_required": oga_req,
            "oga_agencies": oga_result.get("agencies") or [],
            "halal_required": bool(halal_result.get("required")),
            "reasoning": reasoning,
        })

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
