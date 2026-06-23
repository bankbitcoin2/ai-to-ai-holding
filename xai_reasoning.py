"""
xai_reasoning.py
Phase 11 — Explainable AI (XAI) Reasoning Block

generate_reasoning(description, hs_code, confidence, context) → dict

คืน:
  summary           — 1-2 ประโยคภาษาไทย (แสดงใน UI)
  chapter           — HS chapter (2 หลักแรก)
  heading           — HS heading (4 หลักแรก)
  legal_basis       — HS Note / Rule ที่ใช้ตัดสิน
  key_factors       — list of factors ที่นำมาพิจารณา
  alternative_considered — HS อื่นที่พิจารณาแล้วตัดออก
  confidence        — ทวนจาก classify
  warning           — เตือนถ้า confidence < 0.75
"""

import json
import os
import asyncio
from typing import Optional

_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")


async def generate_reasoning(
    description: str,
    hs_code: str,
    confidence: float,
    origin_country: str = "",
    dest_country: str = "TH",
    duty_rate: Optional[float] = None,
    fta_eligible: bool = False,
    oga_required: bool = False,
    context: Optional[dict] = None,
) -> dict:
    """
    สร้าง XAI reasoning block สำหรับ 1 รายการ
    ถ้า Claude unavailable → คืน fallback ที่ build จาก field ที่มี
    """
    if not hs_code:
        return _empty_reasoning(description, confidence)

    chapter = hs_code[:2] if len(hs_code) >= 2 else ""
    heading = hs_code[:4] if len(hs_code) >= 4 else hs_code

    # Fast fallback ถ้าไม่มี API key
    if not _ANTHROPIC_KEY:
        return _fallback_reasoning(description, hs_code, chapter, heading, confidence)

    try:
        result = await _claude_reasoning(
            description, hs_code, chapter, heading, confidence,
            origin_country, dest_country, duty_rate, fta_eligible, oga_required
        )
        return result
    except Exception as e:
        return _fallback_reasoning(description, hs_code, chapter, heading, confidence, error=str(e))


async def _claude_reasoning(
    description, hs_code, chapter, heading, confidence,
    origin_country, dest_country, duty_rate, fta_eligible, oga_required
) -> dict:
    import httpx

    ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
    MODEL = "claude-haiku-4-5-20251001"

    prompt = f"""You are a Thai customs classification expert. Explain why this product was classified under HS code {hs_code}.

Product description: {description}
HS Code assigned: {hs_code}
Confidence: {confidence:.0%}
Origin country: {origin_country or 'unspecified'}
Destination: {dest_country}
{f'Duty rate: {duty_rate:.1f}%' if duty_rate is not None else ''}
{'FTA eligible: YES' if fta_eligible else ''}
{'OGA/permit required: YES' if oga_required else ''}

Respond ONLY with a valid JSON object (no markdown, no explanation outside JSON):
{{
  "summary": "1-2 ประโยคภาษาไทย อธิบายเหตุผลที่เลือก HS code นี้",
  "legal_basis": "HS Note or GRI rule applied, e.g. 'GRI 1 + Note 5 to Chapter 84'",
  "key_factors": ["factor1", "factor2", "factor3"],
  "alternative_considered": "HS code ที่พิจารณาแล้วตัดออก และเหตุผล หรือ null ถ้าไม่มี"
}}

Rules:
- summary ต้องเป็นภาษาไทย กระชับ เข้าใจง่าย
- key_factors: 2-4 factors ที่ตัดสินใจ (วัสดุ, การใช้งาน, ขนาด, บรรจุภัณฑ์ ฯลฯ)
- legal_basis: ระบุ GRI (General Rule of Interpretation) หรือ HS Section/Chapter Note ที่เกี่ยวข้อง
- alternative_considered: ถ้า confidence < 0.80 ต้องระบุ HS อื่นที่ใกล้เคียง
"""

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": _ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 512,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        data = resp.json()

    raw = data["content"][0]["text"].strip()
    # strip markdown code fence if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    parsed = json.loads(raw)

    warning = None
    if confidence < 0.75:
        warning = f"ความมั่นใจต่ำ ({confidence:.0%}) — ควรตรวจสอบกับเจ้าหน้าที่ศุลกากรก่อนยื่น"
    elif confidence < 0.85:
        warning = f"ความมั่นใจปานกลาง ({confidence:.0%}) — แนะนำให้ตรวจสอบ key_factors"

    return {
        "summary": parsed.get("summary", ""),
        "chapter": chapter,
        "heading": heading,
        "legal_basis": parsed.get("legal_basis", ""),
        "key_factors": parsed.get("key_factors", []),
        "alternative_considered": parsed.get("alternative_considered"),
        "confidence": round(confidence, 4),
        "warning": warning,
    }


def _fallback_reasoning(description, hs_code, chapter, heading, confidence, error=None) -> dict:
    """Fallback เมื่อ Claude unavailable — build จาก field ที่มี"""
    warning = None
    if confidence < 0.75:
        warning = f"ความมั่นใจต่ำ ({confidence:.0%}) — ควรตรวจสอบก่อนยื่น"

    return {
        "summary": f"จัดพิกัด {hs_code} จากคำบรรยาย: {description[:80]}",
        "chapter": chapter,
        "heading": heading,
        "legal_basis": "GRI 1 (HS General Rules of Interpretation)",
        "key_factors": [description[:60]] if description else [],
        "alternative_considered": None,
        "confidence": round(confidence, 4),
        "warning": warning,
        "source": "fallback" + (f" ({error[:60]})" if error else ""),
    }


def _empty_reasoning(description, confidence) -> dict:
    return {
        "summary": "ไม่สามารถจัดพิกัดได้",
        "chapter": None,
        "heading": None,
        "legal_basis": None,
        "key_factors": [],
        "alternative_considered": None,
        "confidence": round(confidence, 4),
        "warning": "ไม่พบ HS Code — กรุณาตรวจสอบคำบรรยายสินค้า",
    }


# ── Batch reasoning สำหรับ invoice (ประหยัด API call) ────────────────────────

async def generate_reasoning_batch(items: list[dict]) -> list[dict]:
    """
    items: list of dict with keys:
      description, hs_code, confidence, origin_country, dest_country,
      duty_rate, fta_eligible, oga_required
    คืน list ของ reasoning dict ลำดับเดียวกัน
    """
    tasks = [
        generate_reasoning(
            description=it.get("description", ""),
            hs_code=it.get("hs_code", ""),
            confidence=float(it.get("confidence") or 0),
            origin_country=it.get("origin_country", ""),
            dest_country=it.get("dest_country", "TH"),
            duty_rate=it.get("duty_rate"),
            fta_eligible=bool(it.get("fta_eligible")),
            oga_required=bool(it.get("oga_required")),
        )
        for it in items
    ]
    return await asyncio.gather(*tasks)
