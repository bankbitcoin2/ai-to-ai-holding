"""
agents/mock_classification_agent.py
Mock Mode — ไม่เรียก Claude API
ใช้สำหรับทดสอบ flow ทั้งหมดโดยไม่เสีย token แม้แต่บาทเดียว
เปิด/ปิดผ่าน environment variable: MOCK_MODE=true
"""
import hashlib
from dataclasses import dataclass
from typing import Optional

# ── Mock HS Code Database ──────────────────────────────────────
# keyword → (hs_code, description, confidence, chapter)
MOCK_HS_TABLE = [
    (["laptop", "notebook", "computer", "pc", "macbook"],
     "8471.30", "Portable automatic data processing machines", 0.94),

    (["phone", "smartphone", "mobile", "iphone", "android"],
     "8517.12", "Telephones for cellular networks", 0.92),

    (["shirt", "t-shirt", "tshirt", "polo", "blouse", "top"],
     "6109.10", "T-shirts, singlets of cotton, knitted", 0.88),

    (["trouser", "pants", "jeans", "shorts", "jean"],
     "6203.42", "Men's trousers and breeches of cotton", 0.87),

    (["shoe", "shoes", "sneaker", "boot", "footwear", "sandal"],
     "6403.99", "Footwear with outer soles of rubber or plastics", 0.85),

    (["tablet", "ipad", "android tablet"],
     "8471.30", "Portable automatic data processing machines", 0.91),

    (["medicine", "drug", "pharmaceutical", "vitamin", "supplement", "capsule", "tablet pill"],
     "3004.90", "Medicaments for retail sale", 0.83),

    (["rice", "jasmine rice", "white rice", "brown rice"],
     "1006.30", "Semi-milled or wholly milled rice", 0.96),

    (["car", "vehicle", "automobile", "sedan", "suv"],
     "8703.23", "Motor cars with engine 1000-1500cc", 0.89),

    (["solar", "solar panel", "photovoltaic", "pv module"],
     "8541.40", "Photosensitive semiconductor devices", 0.90),

    (["cable", "wire", "usb cable", "hdmi", "charger cable"],
     "8544.42", "Electric conductors for voltage <= 1000V", 0.86),

    (["watch", "smartwatch", "wristwatch", "clock"],
     "9102.12", "Wrist-watches, electrically operated", 0.88),

    (["bag", "backpack", "handbag", "luggage", "suitcase"],
     "4202.92", "Containers with outer surface of textile", 0.84),

    (["coffee", "coffee bean", "roasted coffee", "ground coffee"],
     "0901.21", "Coffee, roasted, not decaffeinated", 0.95),

    (["plastic", "plastic bottle", "container", "packaging"],
     "3923.30", "Carboys, bottles, flasks of plastics", 0.82),
]


@dataclass
class ClassificationResult:
    hs_code: Optional[str]
    hs_description: Optional[str]
    confidence_score: float
    source_reference: str
    reasoning_steps: list
    notes: Optional[str]
    raw_response: str


def _match(description: str) -> tuple:
    """หา HS Code ที่ตรงกับ keyword มากที่สุด"""
    desc_lower = description.lower()
    best_score = 0
    best_match = None

    for keywords, hs_code, hs_desc, confidence in MOCK_HS_TABLE:
        score = sum(1 for kw in keywords if kw in desc_lower)
        if score > best_score:
            best_score = score
            best_match = (hs_code, hs_desc, confidence)

    return best_match


async def classify_item(
    description: str,
    origin_country: Optional[str] = None,
    additional_context: Optional[str] = None,
) -> ClassificationResult:
    """
    Mock version — ไม่เรียก API ใด ๆ
    คืนผลจาก keyword matching แทน
    """
    match = _match(description)

    if match:
        hs_code, hs_desc, confidence = match
        return ClassificationResult(
            hs_code=hs_code,
            hs_description=hs_desc,
            confidence_score=confidence,
            source_reference=f"[MOCK] HS 2022, Chapter {hs_code[:2]}",
            reasoning_steps=[
                f"[MOCK] Keyword match found in description: '{description[:50]}'",
                f"[MOCK] Matched to HS Chapter {hs_code[:2]}",
                f"[MOCK] Assigned heading {hs_code}",
            ],
            notes="[MOCK MODE — Not a real classification]",
            raw_response=f'{{"hs_code":"{hs_code}","confidence_score":{confidence}}}',
        )
    else:
        # ไม่เจอ keyword — คืน generic
        return ClassificationResult(
            hs_code="9999.99",
            hs_description="Unclassified goods (mock fallback)",
            confidence_score=0.40,
            source_reference="[MOCK] Unable to classify — insufficient keywords",
            reasoning_steps=[
                f"[MOCK] No keyword match found for: '{description[:50]}'",
                "[MOCK] Returning low-confidence fallback",
            ],
            notes="[MOCK] Add more descriptive keywords to improve matching.",
            raw_response='{"hs_code":"9999.99","confidence_score":0.40}',
        )
