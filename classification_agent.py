"""
classification_agent.py
Classification Agent - Customs Intelligence Division
"""
import json
import os
from dataclasses import dataclass
from typing import Optional
import httpx

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a Customs Classification Agent working for AI TO AI HOLDING.
Your job is to classify goods under the Harmonized System (HS Code).

STRICT RULES (Non-negotiable):
1. Always respond in valid JSON only - no prose, no markdown.
2. Every classification must cite a real HS Chapter, Section, or Explanatory Note.
3. If you are uncertain, lower the confidence_score - never fabricate certainty.
4. confidence_score must be a float between 0.00 and 1.00.
5. Return UP TO 5 candidate classifications ranked by confidence_score descending.
6. Only include candidates with confidence_score >= 0.75.
7. If no candidate reaches 0.75, return the single best candidate anyway.

Response format - return a JSON array (ranked best first):
[
  {
    "hs_code": "8471.30",
    "hs_description": "Portable automatic data processing machines...",
    "confidence_score": 0.92,
    "source_reference": "HS 2022, Chapter 84, Note 5(A); Explanatory Note 84.71",
    "reasoning_steps": ["Step 1: ...", "Step 2: ..."],
    "notes": null
  },
  {
    "hs_code": "8471.49",
    "hs_description": "Other automatic data processing machines...",
    "confidence_score": 0.78,
    "source_reference": "HS 2022, Chapter 84, Heading 84.71",
    "reasoning_steps": ["Alternative if device is not portable"],
    "notes": "Consider if weight > 10kg"
  }
]"""

_DISCLAIMER = (
    "This is a preliminary estimate only. Not a legal determination. "
    "Please verify with customs authorities before actual import/export."
)

CONFIDENCE_THRESHOLD = 0.75


@dataclass
class CandidateResult:
    rank: int
    hs_code: Optional[str]
    hs_code_11: Optional[str]
    hs_description: Optional[str]
    hs_description_th: Optional[str]
    confidence_score: float
    source_reference: str
    reasoning_steps: list
    notes: Optional[str]


@dataclass
class ClassificationResult:
    candidates: list
    best: Optional[CandidateResult]
    raw_response: str

    @property
    def hs_code(self): return self.best.hs_code if self.best else None
    @property
    def hs_description(self): return self.best.hs_description if self.best else None
    @property
    def confidence_score(self): return self.best.confidence_score if self.best else 0.0
    @property
    def source_reference(self): return self.best.source_reference if self.best else ""
    @property
    def reasoning_steps(self): return self.best.reasoning_steps if self.best else []
    @property
    def notes(self): return self.best.notes if self.best else _DISCLAIMER


async def _enrich_with_ckan(candidates: list) -> list:
    from knowledge_service import fetch_hs_candidates
    enriched = []
    for rank, c in enumerate(candidates, 1):
        hs6 = (c.get("hs_code") or "").replace(".", "")[:6]
        hs_11 = None
        hs_th = None
        if hs6:
            try:
                ckan = await fetch_hs_candidates([hs6[:4]], limit=3)
                for row in ckan:
                    code = str(row.get("hs_code", "")).replace(".", "")
                    if code.startswith(hs6[:4]):
                        hs_11 = code.ljust(11, "0")[:11]
                        hs_th = row.get("description", "")
                        break
            except Exception:
                pass
        raw_conf = float(c.get("confidence_score", 0.0))
        capped = min(round(raw_conf, 3), 0.980)
        enriched.append(CandidateResult(
            rank=rank,
            hs_code=c.get("hs_code"),
            hs_code_11=hs_11,
            hs_description=c.get("hs_description"),
            hs_description_th=hs_th,
            confidence_score=capped,
            source_reference=c.get("source_reference", ""),
            reasoning_steps=c.get("reasoning_steps", []),
            notes=c.get("notes") or _DISCLAIMER,
        ))
    return enriched


async def classify_item(
    description: str,
    origin_country: Optional[str] = None,
    additional_context: Optional[str] = None,
) -> ClassificationResult:
    user_content = f"Product description: {description}"
    if origin_country:
        user_content += f"\nOrigin country: {origin_country}"
    if additional_context:
        user_content += f"\nAdditional context: {additional_context}"

    payload = {
        "model": MODEL,
        "max_tokens": 2000,
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
    clean = raw_text.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(clean)

    if isinstance(parsed, dict):
        parsed = [parsed]

    filtered = sorted(
        [c for c in parsed if float(c.get("confidence_score", 0)) >= CONFIDENCE_THRESHOLD],
        key=lambda x: float(x.get("confidence_score", 0)),
        reverse=True
    )[:5]

    if not filtered and parsed:
        filtered = [max(parsed, key=lambda x: float(x.get("confidence_score", 0)))]

    candidates = await _enrich_with_ckan(filtered)
    best = candidates[0] if candidates else None

    return ClassificationResult(candidates=candidates, best=best, raw_response=raw_text)
