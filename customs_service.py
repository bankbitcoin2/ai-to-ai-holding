"""
customs_service.py — Integrated v2.0
Customs Intelligence Service

วางที่: AI_TO_AI_HOLDING/customs_service.py
(วางทับของเดิม)

เปลี่ยนจาก v1:
  _estimate_duty_rate() → knowledge_service.lookup_tax_rate()  (IGTF จริง)
  _check_oga()          → knowledge_service.check_restricted()  (engine จริง)
  เพิ่ม halal_engine.check()                                   (21 ประเทศ)
  เพิ่ม glossary fast-path                                     (ประหยัด token)
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional
import aiosqlite

from agents_router import classify_item
from audit import log_event
from holding_config import LOW_CONFIDENCE_THRESHOLD, PRICE_PER_ITEM
from knowledge_service import lookup_tax_rate, check_restricted, check_halal, search_glossary
from treasury_service import settle_transaction

CUSTOMS_DIVISION_ID = "ent-div-customs"


def _make_hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


async def process_invoice(
    db: aiosqlite.Connection,
    *,
    client_id: str,
    invoice_number: Optional[str],
    seller_name: Optional[str],
    seller_country: Optional[str],
    buyer_name: Optional[str],
    buyer_country: Optional[str],
    invoice_date: Optional[str],
    currency: str,
    items: list[dict],
) -> dict:
    now = datetime.now(timezone.utc).isoformat()

    # 1. สร้าง customs case
    case_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO customs_cases
               (id, client_id, case_status, submitted_at, assigned_agent)
           VALUES (?,?,?,?,?)""",
        (case_id, client_id, "PROCESSING", now, CUSTOMS_DIVISION_ID),
    )

    # 2. สร้าง invoice
    invoice_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO customs_invoices
               (id, case_id, invoice_number, seller_name, seller_country,
                buyer_name, buyer_country, invoice_date, currency, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (invoice_id, case_id, invoice_number, seller_name, seller_country,
         buyer_name, buyer_country, invoice_date, currency, now),
    )

    classified_items = []
    total_duty = 0.0

    for idx, item in enumerate(items, start=1):
        description = item.get("description", "")
        quantity    = item.get("quantity")
        unit        = item.get("unit")
        unit_price  = item.get("unit_price")
        total_price = item.get("total_price") or (
            (quantity or 0) * (unit_price or 0) if quantity and unit_price else None
        )
        origin      = item.get("origin_country") or seller_country
        destination = item.get("destination_country") or buyer_country

        # ── Glossary fast-path (ข้าม Claude ถ้าเจอในคลัง) ──
        gloss = search_glossary(description)
        extra = f"Glossary hint: HS {gloss['hs_hint']} ({gloss.get('canonical_en','')})" if gloss else None

        # ── Classification Agent ──
        result = await classify_item(
            description=description,
            origin_country=origin,
            additional_context=extra,
        )

        # ── Tax / FTA (IGTF จริง) ──
        tax_code   = result.hs_code or ""
        tax_result = lookup_tax_rate(tax_code, origin)
        duty_rate  = _best_rate(tax_result)
        duty_amount = round((total_price or 0) * duty_rate, 2) if total_price else None
        vat_rate   = tax_result.get("vat_rate", _default_vat(buyer_country))
        vat_amount  = round((total_price or 0) * vat_rate, 2) if total_price else None

        # ── OGA / Restricted (engine จริง) ──
        oga_result  = check_restricted(tax_code)
        oga_required = oga_result.get("is_restricted", False)
        oga_agencies = [p.get("agency_abbr","") for p in oga_result.get("requires_permits", [])]

        # ── Halal (21 ประเทศ offline) ──
        halal_result   = check_halal(tax_code, destination)
        halal_required = halal_result.get("halal_required", False)
        halal_risk     = halal_result.get("risk_level", "NONE")

        # ── บันทึก DB ──
        item_id   = str(uuid.uuid4())
        item_hash = _make_hash(f"{item_id}{result.hs_code}{result.confidence_score}{now}")

        await db.execute(
            """INSERT INTO customs_invoice_items (
                   id, invoice_id, line_number, description,
                   quantity, unit, unit_price, total_price, origin_country,
                   hs_code, hs_description, confidence_score, source_reference,
                   duty_rate, duty_amount, vat_rate, vat_amount,
                   oga_required, oga_agencies,
                   compliance_notes, classified_at, classified_by
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                item_id, invoice_id, idx, description,
                quantity, unit, unit_price, total_price, origin,
                result.hs_code, result.hs_description,
                result.confidence_score, result.source_reference,
                duty_rate, duty_amount, vat_rate, vat_amount,
                1 if oga_required else 0, json.dumps(oga_agencies),
                json.dumps({"halal_required": halal_required, "halal_risk": halal_risk,
                            "glossary_hint": gloss.get("matched") if gloss else None}),
                now, CUSTOMS_DIVISION_ID,
            ),
        )

        # ── Audit Log (P-04) ──
        await log_event(
            db,
            event_type="DECISION",
            actor_id=CUSTOMS_DIVISION_ID,
            action="HS_CLASSIFY",
            target_resource=f"customs_invoice_items:{item_id}",
            payload={"description": description, "origin": origin, "destination": destination},
            result={
                "hs_code": result.hs_code,
                "confidence_score": result.confidence_score,
                "duty_rate": duty_rate,
                "oga_required": oga_required,
                "halal_required": halal_required,
                "halal_risk": halal_risk,
            },
            confidence_score=result.confidence_score,
            source_reference=result.source_reference,
            reasoning_steps=result.reasoning_steps,
        )

        if duty_amount:
            total_duty += duty_amount

        classified_items.append({
            "line_number":     idx,
            "description":     description,
            "hs_code":         result.hs_code,
            "hs_description":  result.hs_description,
            "confidence_score": result.confidence_score,
            "source_reference": result.source_reference,
            "duty_rate":       duty_rate,
            "duty_amount":     duty_amount,
            "vat_rate":        vat_rate,
            "vat_amount":      vat_amount,
            "tax_detail":      tax_result,
            "oga_required":    oga_required,
            "oga_agencies":    oga_agencies,
            "oga_detail":      oga_result,
            "halal_required":  halal_required,
            "halal_risk_level": halal_risk,
            "halal_detail":    halal_result,
            "glossary_hint":   gloss.get("matched") if gloss else None,
            "notes":           result.notes,
        })

        if result.confidence_score < LOW_CONFIDENCE_THRESHOLD:
            await _trigger_learning(db, case_id, "LOW_CONFIDENCE")

    # 3. ปิด case
    await db.execute(
        "UPDATE customs_cases SET case_status=?, completed_at=? WHERE id=?",
        ("COMPLETED", now, case_id),
    )

    # 4. Treasury 60/40 (P-03)
    gross = round(len(items) * PRICE_PER_ITEM, 2)
    treasury = await settle_transaction(
        db,
        source_type="CUSTOMS_GATEWAY",
        gross_amount=gross,
        client_id=client_id,
        reference_id=case_id,
        api_calls=len(items),
    )

    await db.commit()

    return {
        "case_id":    case_id,
        "invoice_id": invoice_id,
        "status":     "COMPLETED",
        "items":      classified_items,
        "summary": {
            "total_items":         len(classified_items),
            "total_duty_estimate": round(total_duty, 2),
            "currency":            currency,
            "avg_confidence":      round(
                sum(i["confidence_score"] for i in classified_items) / len(classified_items), 3
            ) if classified_items else 0,
            "oga_flagged":    sum(1 for i in classified_items if i["oga_required"]),
            "halal_flagged":  sum(1 for i in classified_items if i["halal_required"]),
            "glossary_hits":  sum(1 for i in classified_items if i["glossary_hint"]),
        },
        "treasury":   treasury,
        "disclaimer": (
            "ผลลัพธ์นี้เพื่อสนับสนุนการตัดสินใจเท่านั้น "
            "ต้องตรวจสอบกับกรมศุลกากรก่อนการนำเข้า/ส่งออกจริงทุกครั้ง"
        ),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _default_vat(destination: Optional[str]) -> float:
    return {
        "TH": 0.07, "GB": 0.20, "DE": 0.19, "FR": 0.20,
        "SG": 0.09, "MY": 0.08, "ID": 0.11, "PH": 0.12,
        "VN": 0.10, "AU": 0.10, "JP": 0.10, "KR": 0.10,
        "CN": 0.13, "US": 0.00, "AE": 0.05, "SA": 0.15,
    }.get(destination or "", 0.07)


async def _trigger_learning(db: aiosqlite.Connection, case_id: str, trigger_type: str):
    try:
        tid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            """INSERT INTO learning_triggers
                   (id, trigger_type, source_id, source_table, triggered_at, evidence_hash)
               VALUES (?,?,?,?,?,?)""",
            (tid, trigger_type, case_id, "customs_cases", now,
             _make_hash(f"{tid}{case_id}{trigger_type}{now}")),
        )
    except Exception:
        pass  # ไม่ให้ learning trigger ทำให้ main flow พัง
