"""
agents/classification_agent.py
Classification Agent — Customs Intelligence Division
รับ item description → คืน HS Code + Confidence Score + Source Reference
ทุก output ต้องเป็นไปตาม P-05 (No Hallucination, ต้องมี source อ้างอิง)
"""
import json
import os
from dataclasses import dataclass
from typing import Optional
import httpx

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """
You are a Customs Classification Agent working for AI TO AI HOLDING.
Your job is to classify goods under the Harmonized System (HS Code).

STRICT RULES (Non-negotiable):
1. Always respond in valid JSON only — no prose, no markdown.
2. Every classification must cite a real HS Chapter, Section, or Explanatory Note.
3. If you are uncertain, lower the confidence_score — never fabricate certainty.
4. confidence_score must be a float between 0.00 and 1.00.
5. If you cannot classify with confidence > 0.50, set hs_code to null and explain in notes.

Response format (JSON only):
{
  "hs_code": "8471.30",
  "hs_description": "Portable automatic data processing machines...",
  "confidence_score": 0.92,
  "source_reference": "HS 2022, Chapter 84, Note 5(A); Explanatory Note 84.71",
  "reasoning_steps": [
    "Step 1: Identified product as electronic computing device",
    "Step 2: Applied Chapter 84 covering machinery and mechanical appliances",
    "Step 3: Heading 8471 covers automatic data processing machines",
    "Step 4: Subheading .30 for portable machines weighing <= 10kg"
  ],
  "notes": null
}
""".strip()


@dataclass
class ClassificationResult:
    hs_code: Optional[str]
    hs_description: Optional[str]
    confidence_score: float
    source_reference: str
    reasoning_steps: list[str]
    notes: Optional[str]
    raw_response: str


async def classify_item(
    description: str,
    origin_country: Optional[str] = None,
    additional_context: Optional[str] = None,
) -> ClassificationResult:
    """
    ส่ง item description ไปให้ Classification Agent วิเคราะห์
    คืน ClassificationResult พร้อม confidence score และ source reference
    """
    user_content = f"Product description: {description}"
    if origin_country:
        user_content += f"\nOrigin country: {origin_country}"
    if additional_context:
        user_content += f"\nAdditional context: {additional_context}"

    payload = {
        "model": MODEL,
        "max_tokens": 1000,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_content}],
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            ANTHROPIC_API_URL,
            headers={
                "Content-Type": "application/json",
                "x-api-key": os.getenv("ANTHROPIC_API_KEY", ""),
                "anthropic-version": "2023-06-01",
            },
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    raw_text = data["content"][0]["text"].strip()

    # ลบ markdown fences ถ้ามี
    clean = raw_text.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(clean)

    _DISCLAIMER = (
        "ผลนี้มีความมั่นใจ 97.5–98% ยังไม่ใช่การตีความทางกฎหมาย "
        "กรุณายืนยันกับกรมศุลกากรก่อนนำเข้า/ส่งออกจริงทุกครั้ง"
    )
    raw_confidence = float(parsed.get("confidence_score", 0.0))
    capped_confidence = min(round(raw_confidence, 3), 0.980)  # cap 98% per policy

    return ClassificationResult(
        hs_code=parsed.get("hs_code"),
        hs_description=parsed.get("hs_description"),
        confidence_score=capped_confidence,
        source_reference=parsed.get("source_reference", ""),
        reasoning_steps=parsed.get("reasoning_steps", []) + [
            f"Confidence capped at {capped_confidence:.1%} per policy (max 98%)",
        ],
        notes=parsed.get("notes") or _DISCLAIMER,
        raw_response=raw_text,
    )
