"""
classification_agent.py - Customs Intelligence Division
Multi-candidate HS classification with cache + CKAN 11-digit enrichment
"""
import json
import os
from dataclasses import dataclass
from typing import Optional
import httpx

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"
CONFIDENCE_THRESHOLD = 0.75
CACHE_THRESHOLD = 0.85

SYSTEM_PROMPT = """You are a Customs Classification Agent working for AI TO AI HOLDING.
Classify goods under the Harmonized System (HS Code).

STRICT RULES:
1. Respond in valid JSON array only - no prose, no markdown.
2. Cite real HS Chapter, Section, or Explanatory Note for every candidate.
3. Lower confidence_score when uncertain - never fabricate certainty.
4. confidence_score: float 0.00-1.00.
5. Return UP TO 5 candidates ranked by confidence_score descending.
6. Only include candidates with confidence_score >= 0.75.
7. If none reach 0.75, return single best candidate anyway.
8. hs_description_th: Thai language description of the HS heading — translate the official HS description to Thai. Keep it concise (≤80 chars).

Response format (JSON array ranked best first):
[
  {
    "hs_code": "8471.30",
    "hs_description": "Portable automatic data processing machines...",
    "hs_description_th": "เครื่องประมวลผลข้อมูลอัตโนมัติแบบพกพา...",
    "confidence_score": 0.92,
    "source_reference": "HS 2022, Chapter 84, Note 5(A); Explanatory Note 84.71",
    "reasoning_steps": ["Step 1: ...", "Step 2: ..."],
    "notes": null
  }
]"""

_DISCLAIMER = (
    "This is a preliminary estimate only. Not a legal determination. "
    "Please verify with customs authorities before actual import/export."
)


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


def _build_hs11_estimate(hs_code: str) -> Optional[str]:
    """
    สร้าง 11-digit estimate จาก HS 6-digit ของ Claude
    Format ไทย: HHHHSS.CC.NNN
    - 6 หลักแรกจาก HS international (Claude)
    - หลัก 7-8: AHTN subdivision (ค่าเริ่มต้น "00" ถ้าไม่มีข้อมูล)
    - หลัก 9-11: Thai statistical suffix (ค่าเริ่มต้น "000")
    หมายเหตุ: ต้องยืนยันกับ igtf.customs.go.th ก่อนใช้จริง
    """
    if not hs_code:
        return None
    digits = hs_code.replace(".", "").strip()
    if len(digits) < 4:
        return None
    # pad ให้ครบ 11 หลัก: 6 จาก HS + "00" AHTN + "000" Thai
    padded = digits.ljust(11, "0")[:11]
    return padded


async def _enrich_with_ckan(candidates: list) -> list:
    """Enrich candidates with Thai HS description from CKAN + 11-digit estimate"""
    from knowledge_service import fetch_hs_candidates
    enriched = []
    for rank, c in enumerate(candidates, 1):
        hs_raw = c.get("hs_code") or ""
        hs6 = hs_raw.replace(".", "")[:6]
        hs_th = None

        # ดึง description ภาษาไทยจาก CKAN (4-digit heading) — fallback: ใช้ที่ Claude generate
        claude_th = c.get("hs_description_th")
        if hs6:
            try:
                ckan = await fetch_hs_candidates([hs6[:4]], limit=5)
                for row in ckan:
                    code = str(row.get("hs_code", "")).replace(".", "")
                    if code.startswith(hs6[:4]):
                        ckan_th = row.get("description", "")
                        if ckan_th:
                            hs_th = ckan_th  # prefer CKAN if available
                            break
            except Exception:
                pass
        if not hs_th and claude_th:
            hs_th = claude_th  # fallback to Claude-generated Thai description

        # สร้าง 11-digit estimate (ยืนยันกับ igtf.customs.go.th ก่อนใช้จริง)
        hs_11 = _build_hs11_estimate(hs_raw)

        raw_conf = float(c.get("confidence_score", 0.0))
        capped = min(round(raw_conf, 3), 0.980)
        enriched.append(CandidateResult(
            rank=rank,
            hs_code=hs_raw,
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
    db=None,
    session_id: Optional[str] = None,
    session_type: str = "SANDBOX",
) -> ClassificationResult:

    # Cache lookup first
    if db:
        try:
            from cache_classification import cache_lookup
            cached = await cache_lookup(db, description)
            if cached:
                best = CandidateResult(
                    rank=1,
                    hs_code=cached["hs_code"],
                    hs_code_11=cached.get("hs_code_11"),
                    hs_description=cached.get("hs_description"),
                    hs_description_th=cached.get("hs_description_th"),
                    confidence_score=float(cached["confidence_score"]),
                    source_reference="Cache ({}, {} hits)".format(
                        cached["source"], cached["hit_count"]),
                    reasoning_steps=["Returned from cache - source: {}".format(cached["source"])],
                    notes=_DISCLAIMER,
                )
                return ClassificationResult(
                    candidates=[best], best=best,
                    raw_response="[CACHE HIT] {}".format(cached["source"])
                )
        except Exception:
            pass

    # ── DB-First lookup: ค้นหาจาก hs_code_master ก่อน call Claude ──────────
    db_hint = ""
    try:
        from knowledge_service import db_search_hs
        db_result = await db_search_hs(description)
        if db_result.get("found"):
            db_hint = db_result.get("inject_prompt", "")
            print(f"[DB-FIRST] mode={db_result['mode']} candidates={len(db_result['candidates'])}")
    except Exception as _dbe:
        print(f"[DB-FIRST] warning: {_dbe}")

    user_content = "Product description: {}".format(description)
    if origin_country:
        user_content += "\nOrigin country: {}".format(origin_country)
    if db_hint:
        user_content += "\n\n" + db_hint
    if additional_context:
        user_content += "\nAdditional context: {}".format(additional_context)

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

    # Auto-save to cache if confidence >= 0.85
    if db and best and best.confidence_score >= CACHE_THRESHOLD:
        try:
            from cache_classification import cache_save, log_candidates
            await cache_save(db, description, {
                "hs_code": best.hs_code,
                "hs_code_11": best.hs_code_11,
                "hs_description": best.hs_description,
                "hs_description_th": best.hs_description_th,
                "confidence_score": best.confidence_score,
            }, source="CLAUDE")
            if session_id:
                await log_candidates(db, session_id, session_type, description, [
                    {
                        "rank": c.rank, "hs_code": c.hs_code, "hs_code_11": c.hs_code_11,
                        "hs_description": c.hs_description, "confidence_score": c.confidence_score,
                        "source_reference": c.source_reference,
                    }
                    for c in candidates
                ])
        except Exception:
            pass

    return ClassificationResult(candidates=candidates, best=best, raw_response=raw_text)