"""
agents/mock_classification_agent.py
Mock Mode — no Claude API calls
Uses keyword matching. Max confidence capped at 98%.
"""
import hashlib
from dataclasses import dataclass
from typing import Optional

_MAX_CONFIDENCE = 0.980
_DISCLAIMER = (
    "Result confidence 97.5-98%. Not legal advice. "
    "Verify with Thai Customs before import/export."
)

def _cap(score: float) -> float:
    return min(round(score, 3), _MAX_CONFIDENCE)

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
    (["medicine", "drug", "pharmaceutical", "vitamin", "supplement", "capsule"],
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
    # Thai keywords
    (["\u0e17\u0e2d\u0e07\u0e04\u0e33", "\u0e17\u0e2d\u0e07", "gold", "gold bar", "bullion", "\u0e2a\u0e23\u0e49\u0e2d\u0e22\u0e17\u0e2d\u0e07", "\u0e41\u0e2b\u0e27\u0e19\u0e17\u0e2d\u0e07"],
     "7108.12", "Gold non-monetary, unwrought forms", 0.978),
    (["\u0e21\u0e37\u0e2d\u0e16\u0e37\u0e2d", "\u0e42\u0e17\u0e23\u0e28\u0e31\u0e1e\u0e17\u0e4c", "\u0e2a\u0e21\u0e32\u0e23\u0e4c\u0e17\u0e42\u0e1f\u0e19"],
     "8517.12", "Telephones for cellular networks", 0.977),
    (["\u0e41\u0e25\u0e47\u0e1b\u0e17\u0e47\u0e2d\u0e1b", "\u0e42\u0e19\u0e49\u0e15\u0e1a\u0e38\u0e4a\u0e04", "\u0e04\u0e2d\u0e21\u0e1e\u0e34\u0e27\u0e40\u0e15\u0e2d\u0e23\u0e4c", "\u0e42\u0e19\u0e49\u0e15\u0e1a\u0e38\u0e4a\u0e01"],
     "8471.30", "Portable automatic data processing machines", 0.978),
    (["\u0e23\u0e16\u0e22\u0e19\u0e15\u0e4c", "\u0e23\u0e16", "\u0e01\u0e23\u0e30\u0e1a\u0e30", "\u0e23\u0e16\u0e01\u0e23\u0e30\u0e1a\u0e30", "\u0e23\u0e16\u0e40\u0e01\u0e4b\u0e07"],
     "8703.23", "Motor cars with engine 1500-3000cc", 0.976),
    (["\u0e40\u0e2a\u0e37\u0e49\u0e2d", "\u0e40\u0e2a\u0e37\u0e49\u0e2d\u0e22\u0e37\u0e14", "\u0e40\u0e2a\u0e37\u0e49\u0e2d\u0e1c\u0e49\u0e32", "\u0e40\u0e2a\u0e37\u0e49\u0e2d\u0e42\u0e1b\u0e42\u0e25"],
     "6109.10", "T-shirts of cotton, knitted", 0.975),
    (["\u0e23\u0e2d\u0e07\u0e40\u0e17\u0e49\u0e32", "\u0e23\u0e2d\u0e07\u0e40\u0e17\u0e49\u0e32\u0e1c\u0e49\u0e32\u0e43\u0e1a", "\u0e23\u0e2d\u0e07\u0e40\u0e17\u0e49\u0e32\u0e2b\u0e19\u0e31\u0e07", "\u0e23\u0e2d\u0e07\u0e40\u0e17\u0e49\u0e32\u0e41\u0e15\u0e30"],
     "6403.99", "Footwear with outer soles of rubber or plastics", 0.976),
    (["\u0e01\u0e23\u0e30\u0e40\u0e1b\u0e4b\u0e32", "\u0e01\u0e23\u0e30\u0e40\u0e1b\u0e4b\u0e32\u0e16\u0e37\u0e2d", "\u0e01\u0e23\u0e30\u0e40\u0e1b\u0e4b\u0e32\u0e40\u0e14\u0e34\u0e19\u0e17\u0e32\u0e07", "\u0e01\u0e23\u0e30\u0e40\u0e1b\u0e4b\u0e32\u0e2a\u0e30\u0e1e\u0e32\u0e22"],
     "4202.92", "Containers with outer surface of textile", 0.975),
    (["\u0e19\u0e32\u0e2c\u0e34\u0e01\u0e32", "\u0e19\u0e32\u0e2c\u0e34\u0e01\u0e32\u0e02\u0e49\u0e2d\u0e21\u0e37\u0e2d", "\u0e19\u0e32\u0e2c\u0e34\u0e01\u0e32\u0e2a\u0e21\u0e32\u0e23\u0e4c\u0e17"],
     "9102.12", "Wrist-watches, electrically operated", 0.976),
    (["\u0e02\u0e49\u0e32\u0e27", "\u0e02\u0e49\u0e32\u0e27\u0e2b\u0e2d\u0e21\u0e21\u0e30\u0e25\u0e34", "\u0e02\u0e49\u0e32\u0e27\u0e2a\u0e32\u0e23", "\u0e02\u0e49\u0e32\u0e27\u0e01\u0e25\u0e49\u0e2d\u0e07"],
     "1006.30", "Semi-milled or wholly milled rice", 0.979),
    (["\u0e22\u0e32", "\u0e22\u0e32\u0e23\u0e31\u0e01\u0e29\u0e32\u0e42\u0e23\u0e04", "\u0e27\u0e34\u0e15\u0e32\u0e21\u0e34\u0e19", "\u0e22\u0e32\u0e40\u0e21\u0e47\u0e14", "\u0e22\u0e32\u0e41\u0e04\u0e1e\u0e0b\u0e39\u0e25"],
     "3004.90", "Medicaments for retail sale", 0.975),
    (["\u0e42\u0e0b\u0e25\u0e32\u0e23\u0e4c", "\u0e41\u0e1c\u0e07\u0e42\u0e0b\u0e25\u0e32\u0e23\u0e4c", "\u0e42\u0e0b\u0e25\u0e32\u0e23\u0e4c\u0e40\u0e0b\u0e25\u0e25\u0e4c"],
     "8541.40", "Photosensitive semiconductor devices", 0.977),
    (["\u0e17\u0e35\u0e27\u0e35", "\u0e42\u0e17\u0e23\u0e17\u0e31\u0e28\u0e19\u0e4c", "\u0e08\u0e2d\u0e17\u0e35\u0e27\u0e35"],
     "8528.72", "Colour TV receivers", 0.975),
    (["\u0e19\u0e49\u0e33\u0e21\u0e31\u0e19", "\u0e19\u0e49\u0e33\u0e21\u0e31\u0e19\u0e14\u0e34\u0e1a", "\u0e19\u0e49\u0e33\u0e21\u0e31\u0e19\u0e40\u0e0a\u0e37\u0e49\u0e2d\u0e40\u0e1e\u0e25\u0e34\u0e07"],
     "2709.00", "Petroleum oils, crude", 0.976),
    (["\u0e19\u0e21", "\u0e19\u0e21\u0e1c\u0e07", "\u0e19\u0e21\u0e27\u0e31\u0e27", "\u0e19\u0e21\u0e01\u0e25\u0e48\u0e2d\u0e07"],
     "0402.21", "Milk powder >1.5% fat", 0.975),
    (["\u0e2a\u0e32\u0e22\u0e44\u0e1f", "\u0e2a\u0e32\u0e22\u0e0a\u0e32\u0e23\u0e4c\u0e08", "\u0e2a\u0e32\u0e22 usb", "\u0e2a\u0e32\u0e22\u0e40\u0e04\u0e40\u0e1a\u0e34\u0e25"],
     "8544.42", "Electric conductors <=1000V with connectors", 0.975),
    (["\u0e01\u0e32\u0e41\u0e1f", "coffee"],
     "0901.21", "Coffee, roasted, not decaffeinated", 0.979),
    (["\u0e1e\u0e25\u0e32\u0e2a\u0e15\u0e34\u0e01"],
     "3923.30", "Carboys, bottles, flasks of plastics", 0.975),
    (["\u0e19\u0e21\u0e1c\u0e07\u0e40\u0e14\u0e47\u0e01", "infant formula", "baby formula", "baby milk"],
     "1901.10", "Infant preparations based on milk", 0.978),
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
    1. DB cache lookup (free)
    2. keyword match
    3. store to cache
    """
    _cache_set = None
    try:
        from cache_service import cache_get, cache_set as _cs
        _cache_set = _cs
        cached = await cache_get(description, origin_country)
        if cached:
            return ClassificationResult(
                hs_code=cached["hs_code"],
                hs_description=cached["hs_description"],
                confidence_score=cached["confidence_score"],
                source_reference=cached.get("source_reference", "DB Cache"),
                reasoning_steps=["CACHE HIT — result from database, no API cost"],
                notes=cached.get("notes"),
                raw_response=(
                    '{"hs_code":"' + str(cached["hs_code"]) +
                    '","source":"cache","hits":' + str(cached.get("hit_count", 1)) + '}'
                ),
            )
    except Exception:
        _cache_set = None

    match = _match(description)

    if match:
        hs_code, hs_desc, confidence = match
        capped = _cap(confidence)
        short_desc = description[:50]
        result = ClassificationResult(
            hs_code=hs_code,
            hs_description=hs_desc,
            confidence_score=capped,
            source_reference="HS Nomenclature 2022, Chapter " + hs_code[:2],
            reasoning_steps=[
                "Keyword match found in description: " + short_desc,
                "Matched to HS Chapter " + hs_code[:2],
                "Assigned heading " + hs_code + " confidence " + str(round(capped * 100, 1)) + "%",
                "Confidence capped at 98% per policy — verify with Thai Customs before use",
            ],
            notes=_DISCLAIMER,
            raw_response=(
                '{"hs_code":"' + hs_code +
                '","confidence_score":' + str(capped) + '}'
            ),
        )
    else:
        result = ClassificationResult(
            hs_code=None,
            hs_description="Unable to classify — insufficient product detail",
            confidence_score=0.40,
            source_reference="Insufficient keywords for HS classification",
            reasoning_steps=[
                "No keyword match found for: " + description[:50],
                "Provide: material, function, HS chapter hint, or country of origin",
            ],
            notes="Please provide more product detail: material, function, or origin country",
            raw_response='{"hs_code":null,"confidence_score":0.40}',
        )

    if result.hs_code and _cache_set:
        try:
            await _cache_set(
                description=description,
                origin_country=origin_country,
                hs_code=result.hs_code,
                hs_description=result.hs_description,
                confidence_score=result.confidence_score,
                source_reference=result.source_reference,
                notes=result.notes,
                model_used="mock",
            )
        except Exception:
            pass

    return result
