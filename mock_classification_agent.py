"""
mock_classification_agent.py
Mock Mode — no Claude API calls
Pipeline:
  1. DB cache lookup (free, instant)
  2. CKAN กรมศุลกากร (free, real HS data)
  3. Keyword fallback table
  4. Store result to cache
Max confidence capped at 98%.
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
    (["tablet", "ipad"],
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
    (["gold", "gold bar", "bullion"],
     "7108.12", "Gold non-monetary, unwrought forms", 0.978),
    (["tv", "television", "monitor", "display"],
     "8528.72", "Colour TV receivers", 0.975),
    (["oil", "petroleum", "crude oil", "diesel", "fuel"],
     "2709.00", "Petroleum oils, crude", 0.976),
    (["milk", "milk powder", "dairy", "infant formula", "baby formula", "baby milk"],
     "0402.21", "Milk powder >1.5% fat", 0.975),
    (["rubber", "natural rubber", "latex"],
     "4001.10", "Natural rubber latex", 0.977),
    (["sugar", "cane sugar", "white sugar"],
     "1701.99", "Other cane or beet sugar", 0.976),
    (["steel", "iron", "steel bar", "steel pipe"],
     "7214.20", "Bars and rods of iron or steel", 0.975),
    (["aluminum", "aluminium", "aluminum sheet"],
     "7606.12", "Aluminum alloy sheets", 0.975),
    (["chemical", "solvent", "acid", "chemical compound"],
     "2901.10", "Acyclic hydrocarbons", 0.970),
    (["textile", "fabric", "cloth", "woven fabric"],
     "5208.11", "Woven fabrics of cotton", 0.975),
    (["wood", "timber", "plywood", "lumber"],
     "4412.33", "Plywood with tropical wood", 0.975),
    (["ceramic", "tile", "porcelain"],
     "6907.21", "Ceramic flags and paving", 0.975),
    (["glass", "glass sheet", "tempered glass"],
     "7005.10", "Float glass and surface ground glass", 0.975),
    (["pump", "water pump", "hydraulic pump"],
     "8413.70", "Centrifugal pumps", 0.975),
    (["motor", "electric motor", "generator"],
     "8501.52", "AC motors multi-phase >750W", 0.975),
    (["battery", "lithium battery", "li-ion"],
     "8507.60", "Lithium-ion accumulators", 0.977),
    (["camera", "digital camera", "cctv", "webcam"],
     "8525.80", "Television cameras, digital cameras", 0.976),
    (["printer", "laser printer", "inkjet"],
     "8443.32", "Other printers for computers", 0.975),
    (["refrigerator", "fridge", "freezer"],
     "8418.10", "Combined refrigerator-freezers", 0.976),
    (["air conditioner", "air-con", "aircon", "hvac"],
     "8415.10", "Air conditioning machines", 0.977),
    (["washing machine", "washer", "dryer"],
     "8450.11", "Fully automatic washing machines", 0.976),
    (["bicycle", "bike", "e-bike", "electric bicycle"],
     "8712.00", "Bicycles and other cycles", 0.976),
    (["motorcycle", "motorbike", "scooter"],
     "8711.20", "Motorcycles with engine 50-250cc", 0.976),
    (["fertilizer", "urea", "npk"],
     "3102.10", "Urea fertilisers", 0.975),
    (["seed", "vegetable seed", "crop seed"],
     "1209.91", "Vegetable seeds for sowing", 0.975),
    (["fish", "frozen fish", "seafood", "shrimp", "prawn"],
     "0306.17", "Other frozen shrimps and prawns", 0.976),
    (["chicken", "poultry", "frozen chicken"],
     "0207.14", "Frozen cuts of fowls of Gallus domesticus", 0.975),
    (["fruit", "fresh fruit", "mango", "durian", "longan"],
     "0810.90", "Other fresh fruit", 0.975),
    (["vegetable", "fresh vegetable", "onion", "garlic"],
     "0703.10", "Onions and shallots, fresh", 0.975),
    (["paint", "coating", "varnish", "lacquer"],
     "3208.90", "Paints based on synthetic polymers", 0.975),
    (["paper", "printing paper", "copy paper", "cardboard"],
     "4802.56", "Paper for writing or printing", 0.975),
    (["book", "textbook", "magazine", "printed matter"],
     "4901.99", "Other printed books", 0.975),
    (["toy", "toys", "doll", "game", "puzzle"],
     "9503.00", "Tricycles, dolls, toys", 0.975),
    (["furniture", "chair", "table", "desk", "sofa"],
     "9401.61", "Upholstered seats of wood", 0.975),
    (["mattress", "bed", "pillow", "bedding"],
     "9404.21", "Mattresses of cellular rubber or plastics", 0.975),
    (["excavator", "bulldozer", "crane", "forklift", "loader", "backhoe", "grader", "dozer"],
     "8429.52", "Self-propelled excavators with 360 degree revolving superstructure", 0.977),
    (["generator set", "genset", "diesel generator", "power generator"],
     "8502.11", "Generating sets with compression-ignition engines <=75 kVA", 0.976),
    (["transformer", "electric transformer", "power transformer"],
     "8504.21", "Liquid dielectric transformers <=650 kVA", 0.975),
    (["compressor", "air compressor", "gas compressor"],
     "8414.80", "Air or gas compressors", 0.976),
    (["conveyor", "conveyor belt", "belt conveyor"],
     "8428.33", "Belt conveyors", 0.975),
    (["boiler", "steam boiler", "industrial boiler"],
     "8402.11", "Watertube boilers producing >45t/hr steam", 0.975),
    (["valve", "industrial valve", "ball valve", "gate valve"],
     "8481.80", "Taps, cocks, valves for pipes", 0.975),
    (["sensor", "industrial sensor", "pressure sensor", "temperature sensor"],
     "9026.20", "Instruments for measuring pressure", 0.975),
    (["robot", "industrial robot", "robotic arm", "automation robot"],
     "8479.50", "Industrial robots", 0.977),
    (["drone", "uav", "unmanned aerial vehicle", "quadcopter"],
     "8806.24", "Other unmanned aircraft >250g-7kg", 0.976),
    (["semiconductor", "chip", "ic", "integrated circuit", "microchip"],
     "8542.31", "Processors and controllers", 0.977),
    (["printing machine", "lithographic", "offset printing", "flexographic", "gravure printing"],
     "8443.11", "Lithographic printing machinery", 0.977),
    (["printing press", "inkjet printer industrial", "screen printing"],
     "8443.19", "Other printing machinery", 0.976),
    (["textile machine", "weaving machine", "loom", "knitting machine", "spinning machine"],
     "8446.30", "Weaving machines power looms", 0.976),
    (["milling machine", "cnc milling", "cnc machine", "machining center"],
     "8457.10", "Machining centres for working metal", 0.977),
    (["lathe", "cnc lathe", "turning machine"],
     "8458.11", "Horizontal lathes for removing metal CNC", 0.976),
    (["injection molding", "injection moulding", "plastic injection"],
     "8477.10", "Injection-moulding machines", 0.977),
    (["packaging machine", "filling machine", "sealing machine", "wrapping machine"],
     "8422.30", "Machinery for filling or closing containers", 0.976),
    (["food processing", "food machine", "meat processing", "slaughter"],
     "8438.10", "Machinery for the preparation of meat", 0.976),
    (["cooling tower", "heat exchanger", "chiller"],
     "8419.89", "Machinery for treating materials by temperature change", 0.975),
    (["led", "led light", "led lamp", "led strip"],
     "8539.52", "LED lamps", 0.976),
    (["optical fiber", "fibre optic", "fiber cable"],
     "8544.70", "Optical fibre cables", 0.976),
    (["medical device", "medical equipment", "x-ray", "ultrasound machine"],
     "9018.90", "Other instruments for medical use", 0.976),
    (["surgical", "surgical instrument", "scalpel", "forceps"],
     "9018.32", "Tubular metal needles and needles for sutures", 0.975),
    (["wheelchair", "mobility scooter", "walker"],
     "8713.10", "Wheelchairs, non-mechanically propelled", 0.976),
    (["aircraft", "airplane", "aeroplane", "helicopter"],
     "8802.40", "Aeroplanes >15000kg unladen", 0.977),
    (["ship", "vessel", "cargo ship", "tanker"],
     "8901.20", "Tankers", 0.975),
    (["satellite", "satellite dish", "antenna"],
     "8529.10", "Aerials and aerial reflectors", 0.975),
    (["rope", "cord", "twine", "net"],
     "5607.49", "Twine of polyethylene or polypropylene", 0.975),
    (["pipe", "tube", "pvc pipe", "steel tube"],
     "3917.32", "Flexible tubes pipes of plastics", 0.975),
    (["screw", "bolt", "nut", "fastener", "nail"],
     "7318.15", "Screws and bolts of iron or steel", 0.975),
    (["tool", "hand tool", "wrench", "hammer", "drill"],
     "8205.59", "Other hand tools", 0.975),
    (["cosmetic", "skincare", "lotion", "cream", "serum"],
     "3304.99", "Other beauty or make-up preparations", 0.975),
    (["soap", "detergent", "shampoo", "cleaner"],
     "3401.11", "Soap for toilet use", 0.975),
    (["perfume", "cologne", "fragrance"],
     "3303.00", "Perfumes and toilet waters", 0.976),
    # Thai keywords
    (["ทองคำ", "ทอง", "สร้อยทอง"],
     "7108.12", "Gold non-monetary, unwrought forms", 0.978),
    (["มือถือ", "โทรศัพท์", "สมาร์ทโฟน"],
     "8517.12", "Telephones for cellular networks", 0.977),
    (["แล็ปท็อป", "โน้ตบุ๊ค", "คอมพิวเตอร์"],
     "8471.30", "Portable automatic data processing machines", 0.978),
    (["รถยนต์", "รถ", "กระบะ"],
     "8703.23", "Motor cars with engine 1500-3000cc", 0.976),
    (["เสื้อ", "เสื้อยืด", "เสื้อผ้า"],
     "6109.10", "T-shirts of cotton, knitted", 0.975),
    (["รองเท้า", "รองเท้าผ้าใบ"],
     "6403.99", "Footwear with outer soles of rubber or plastics", 0.976),
    (["กระเป๋า", "กระเป๋าถือ"],
     "4202.92", "Containers with outer surface of textile", 0.975),
    (["นาฬิกา", "นาฬิกาข้อมือ"],
     "9102.12", "Wrist-watches, electrically operated", 0.976),
    (["ข้าว", "ข้าวหอมมะลิ", "ข้าวสาร"],
     "1006.30", "Semi-milled or wholly milled rice", 0.979),
    (["ยา", "ยารักษาโรค", "วิตามิน"],
     "3004.90", "Medicaments for retail sale", 0.975),
    (["โซลาร์", "แผงโซลาร์"],
     "8541.40", "Photosensitive semiconductor devices", 0.977),
    (["ทีวี", "โทรทัศน์"],
     "8528.72", "Colour TV receivers", 0.975),
    (["น้ำมัน", "น้ำมันดิบ"],
     "2709.00", "Petroleum oils, crude", 0.976),
    (["นม", "นมผง", "นมวัว"],
     "0402.21", "Milk powder >1.5% fat", 0.975),
    (["สายไฟ", "สายชาร์จ", "สาย usb"],
     "8544.42", "Electric conductors <=1000V with connectors", 0.975),
    (["กาแฟ"],
     "0901.21", "Coffee, roasted, not decaffeinated", 0.979),
    (["พลาสติก"],
     "3923.30", "Carboys, bottles, flasks of plastics", 0.975),
    (["สมุนไพร", "หมู", "เนื้อหมู"],
     "0203.29", "Other frozen swine meat", 0.975),
    (["ไก่", "เนื้อไก่", "หมูกระทง"],
     "0207.14", "Frozen cuts of fowls of Gallus domesticus", 0.975),
    (["ปลา", "อาหารทะเล", "กุ้ง"],
     "0306.17", "Other frozen shrimps and prawns", 0.976),
    (["ผัก", "ผักสด", "หอม"],
     "0703.10", "Onions and shallots, fresh", 0.975),
    (["ผลไม้", "มะม่วง", "ทุเรียน"],
     "0810.90", "Other fresh fruit", 0.975),
    (["เฟอร์นิเจอร์", "เก้าอี้", "โต๊ะ", "โซฟา"],
     "9401.61", "Upholstered seats of wood", 0.975),
    (["เครื่องสำอาง", "ครีม", "โลชั่น", "เซร่ัม"],
     "3304.99", "Other beauty or make-up preparations", 0.975),
    (["สบู่", "แชมพู", "ผงซักฟอก"],
     "3401.11", "Soap for toilet use", 0.975),
    (["สีฟัน", "ยาสีฟัน"],
     "3304.10", "Lip make-up preparations", 0.975),
    (["แบตเตอรี่", "สายชาร์จโรง"],
     "8507.60", "Lithium-ion accumulators", 0.977),
    (["ไม้", "ไม้แปรรูป", "ไม้อัด"],
     "4412.33", "Plywood with tropical wood", 0.975),
    (["เหล็ก", "เหล็กเส้น", "เหล็กสแตนเลส"],
     "7214.20", "Bars and rods of iron or steel", 0.975),
    (["ปุ๋ย", "ปุ๋ยเคมี", "ยูเรีย"],
     "3102.10", "Urea fertilisers", 0.975),
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


def _keyword_match(description: str) -> tuple:
    import re
    desc_lower = description.lower()
    best_score = 0
    best_match = None
    for keywords, hs_code, hs_desc, confidence in MOCK_HS_TABLE:
        score = 0
        for kw in keywords:
            if len(kw) <= 3:
                # คำสั้น ≤3 ตัว — ต้องเป็น whole word เท่านั้น
                if re.search(r'\b' + re.escape(kw) + r'\b', desc_lower):
                    score += 1
            else:
                if kw in desc_lower:
                    score += 1
        if score > best_score:
            best_score = score
            best_match = (hs_code, hs_desc, confidence)
    return best_match


async def _ckan_lookup(description: str) -> Optional[tuple]:
    """ดึง HS Code จาก CKAN กรมศุลกากรไทย (ฟรี ไม่ต้อง API key)
    ส่ง phrase เต็มก่อน ถ้าไม่ได้ผล fallback แยกคำ
    """
    try:
        from knowledge_service import fetch_hs_candidates

        # ── ลอง phrase เต็มก่อน (แม่นกว่า) ──────────────────
        candidates = await fetch_hs_candidates([description], limit=5)

        # ── ถ้าไม่ได้ผล → ลอง bigram (2 คำติดกัน) ───────────
        if not candidates:
            words = [w.strip(".,()[]") for w in description.split() if len(w) > 2]
            bigrams = [" ".join(words[i:i+2]) for i in range(len(words)-1)]
            if bigrams:
                candidates = await fetch_hs_candidates(bigrams[:3], limit=5)

        # ── ถ้ายังไม่ได้ → ลอง unigram (คำเดี่ยว ยาวสุด) ───
        if not candidates:
            words = sorted(
                [w.strip(".,()[]") for w in description.split() if len(w) > 3],
                key=len, reverse=True
            )
            if words:
                candidates = await fetch_hs_candidates(words[:3], limit=5)

        if candidates:
            best = candidates[0]
            hs = best.get("hs_code", "")
            desc = best.get("description", "")
            if hs:
                return (hs, desc, 0.920)
    except Exception:
        pass
    return None


async def classify_item(
    description: str,
    origin_country: Optional[str] = None,
    additional_context: Optional[str] = None,
) -> ClassificationResult:
    """
    Pipeline:
    1. DB cache (instant, free)
    2. CKAN กรมศุลกากร (real data, free)
    3. Keyword table fallback
    4. Save to cache
    """
    _cache_set = None

    # ── 1. Cache lookup ───────────────────────────────────────
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

    # ── 2. Keyword table (ความแน่นอนสูง) ─────────────────────
    kw_result = _keyword_match(description)

    # ── 3. CKAN (สำหรับสินค้าที่ไม่อยู่ใน keyword table) ────
    ckan_result = None
    if not kw_result:
        ckan_result = await _ckan_lookup(description)

    # เลือกผลที่ดีที่สุด — keyword ก่อน CKAN
    if kw_result:
        hs_code, hs_desc, confidence = kw_result
        confidence = _cap(confidence)
        source = "HS Nomenclature 2022, Chapter " + hs_code[:2]
        steps = [
            "Keyword match found: " + description[:50],
            "HS Chapter " + hs_code[:2] + " heading " + hs_code,
            "Confidence " + str(round(confidence * 100, 1)) + "% — capped at 98% per policy",
            "Verify with Thai Customs before formal import/export",
        ]
    elif ckan_result:
        hs_code, hs_desc, confidence = ckan_result
        confidence = _cap(confidence)
        source = "Thai Customs CKAN Database (catalog.customs.go.th)"
        steps = [
            "No keyword match — queried Thai Customs CKAN API",
            "Retrieved HS Code from official database: " + hs_code,
            "Confidence: " + str(round(confidence * 100, 1)) + "%",
            "Verify with Thai Customs before formal import/export",
        ]
    else:
        # ── ไม่พบทั้งคู่ ──────────────────────────────────────
        result = ClassificationResult(
            hs_code=None,
            hs_description="Unable to classify — insufficient product detail",
            confidence_score=0.40,
            source_reference="No match in CKAN or keyword table",
            reasoning_steps=[
                "CKAN returned no results for: " + description[:50],
                "No keyword match found",
                "Provide: material, function, HS chapter hint, or origin country",
            ],
            notes="Please provide more detail: material, function, or origin country",
            raw_response='{"hs_code":null,"confidence_score":0.40,"source":"no_match"}',
        )
        return result

    result = ClassificationResult(
        hs_code=hs_code,
        hs_description=hs_desc,
        confidence_score=confidence,
        source_reference=source,
        reasoning_steps=steps,
        notes=_DISCLAIMER,
        raw_response=(
            '{"hs_code":"' + hs_code +
            '","confidence_score":' + str(confidence) +
            ',"source":"' + ("ckan" if ckan_result else "keyword") + '"}'
        ),
    )

    # ── 4. Save to cache ──────────────────────────────────────
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
                model_used="mock+ckan" if ckan_result else "mock",
            )
        except Exception:
            pass

    return result
