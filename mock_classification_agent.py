"""
agents/mock_classification_agent.py
Mock Mode — ไม่เรียก Claude API
ใช้สำหรับทดสอบ flow ทั้งหมดโดยไม่เสีย token แม้แต่บาทเดียว
เปิด/ปิดผ่าน environment variable: MOCK_MODE=true

Policy: confidence_score สูงสุด 0.980 (98%) เสมอ
ระบบไม่เคย claim 100% — ต้องยืนยันกับกรมศุลกากรก่อนใช้จริงทุกครั้ง
"""
import hashlib
from dataclasses import dataclass
from typing import Optional

# confidence cap — ห้ามเกิน 98% ไม่ว่ากรณีใด
_MAX_CONFIDENCE = 0.980
_DISCLAIMER = (
    "ผลนี้มีความมั่นใจ 97.5–98% ยังไม่ใช่การตีความทางกฎหมาย "
    "กรุณายืนยันกับกรมศุลกากรก่อนนำเข้า/ส่งออกจริงทุกครั้ง"
)


def _cap(score: float) -> float:
    """จำกัด confidence ไม่เกิน 98% ตาม policy"""
    return min(round(score, 3), _MAX_CONFIDENCE)


# ── Mock HS Code Database ──────────────────────────────────────
# keyword → (hs_code, description, confidence, chapter)
MOCK_HS_TABLE = [
    (["laptop", "notebook", "computer", "pc", "macbook"],
     "8471.30", "Portable automatic data processing machines", 0.978),

    (["phone", "smartphone", "mobile", "iphone", "android"],
     "8517.12", "Telephones for cellular networks", 0.975),

    (["shirt", "t-shirt", "tshirt", "polo", "blouse", "top"],
     "6109.10", "T-shirts, singlets of cotton, knitted", 0.976),

    (["trouser", "pants", "jeans", "shorts", "jean"],
     "6203.42", "Men's trousers and breeches of cotton", 0.975),

    (["shoe", "shoes", "sneaker", "boot", "footwear", "sandal"],
     "6403.99", "Footwear with outer soles of rubber or plastics", 0.977),

    (["tablet", "ipad", "android tablet"],
     "8471.30", "Portable automatic data processing machines", 0.976),

    (["medicine", "drug", "pharmaceutical", "vitamin", "supplement", "capsule", "tablet pill"],
     "3004.90", "Medicaments for retail sale", 0.975),

    (["rice", "jasmine rice", "white rice", "brown rice"],
     "1006.30", "Semi-milled or wholly milled rice", 0.980),

    (["car", "vehicle", "automobile", "sedan", "suv"],
     "8703.23", "Motor cars with engine 1000-1500cc", 0.977),

    (["solar", "solar panel", "photovoltaic", "pv module"],
     "8541.40", "Photosensitive semiconductor devices", 0.978),

    (["cable", "wire", "usb cable", "hdmi", "charger cable"],
     "8544.42", "Electric conductors for voltage <= 1000V", 0.975),

    (["watch", "smartwatch", "wristwatch", "clock"],
     "9102.12", "Wrist-watches, electrically operated", 0.976),

    (["bag", "backpack", "handbag", "luggage", "suitcase"],
     "4202.92", "Containers with outer surface of textile", 0.975),

    (["coffee", "coffee bean", "roasted coffee", "ground coffee"],
     "0901.21", "Coffee, roasted, not decaffeinated", 0.979),

    (["plastic", "plastic bottle", "container", "packaging"],
     "3923.30", "Carboys, bottles, flasks of plastics", 0.975),
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
        capped = _cap(confidence)
        return ClassificationResult(
            hs_code=hs_code,
            hs_description=hs_desc,
            confidence_score=capped,
            source_reference=f"HS Nomenclature 2022, Chapter {hs_code[:2]}",
            reasoning_steps=[
                f"Keyword match found in description: '{description[:50]}'",
                f"Matched to HS Chapter {hs_code[:2]}",
                f"Assigned heading {hs_code} with confidence {capped:.1%}",
                "Confidence capped at 98% per policy — verify with Thai Customs before use",
            ],
            notes=_DISCLAIMER,
            raw_response=f'{{"hs_code":"{hs_code}","confidence_score":{capped},"recommendation":"{_DISCLAIMER}"}}',
        )
    else:
        return ClassificationResult(
            hs_code=None,
            hs_description="Unable to classify — insufficient product detail",
            confidence_score=0.40,
            source_reference="Insufficient keywords for HS classification",
            reasoning_steps=[
                f"No keyword match found for: '{description[:50]}'",
                "Recommend providing: material, function, HS chapter hint, or country of origin",
            ],
            notes="กรุณาระบุรายละเอียดสินค้าเพิ่มเติม เช่น วัสดุ ฟังก์ชัน หรือประเทศต้นกำเนิด",
            raw_response='{"hs_code":null,"confidence_score":0.40,"recommendation":"Provide more product detail"}',
        )
