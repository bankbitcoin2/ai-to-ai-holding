"""
AI TO AI HOLDING — Customs Intelligence Division
Halal Engine — ตรวจสอบข้อกำหนด Halal 21 ประเทศ (P-05: Evidence-Based)

ใช้:
    halal_engine.check("0203", "MY")        # ตรวจ HS + ประเทศปลายทาง
    halal_engine.is_halal_zone("SA")        # ตรวจว่าประเทศต้องการ Halal
    halal_engine.list_halal_countries()     # รายชื่อ 21 ประเทศ
"""

# ============================================================
# 21 ประเทศที่ต้องการ Halal Certification
# ISO 3166-1 alpha-2 country codes
# ============================================================
HALAL_MANDATORY_COUNTRIES: dict[str, dict] = {
    # ── กลุ่ม GCC ──
    "SA": {"name": "Saudi Arabia",      "region": "GCC",        "authority": "SFDA / SASO"},
    "AE": {"name": "United Arab Emirates", "region": "GCC",     "authority": "ESMA / MoEI"},
    "QA": {"name": "Qatar",             "region": "GCC",        "authority": "QSTP-B / MoPH"},
    "KW": {"name": "Kuwait",            "region": "GCC",        "authority": "PAFN"},
    "BH": {"name": "Bahrain",           "region": "GCC",        "authority": "NHRA"},
    "OM": {"name": "Oman",              "region": "GCC",        "authority": "MOCI"},
    # ── ตะวันออกกลาง ──
    "EG": {"name": "Egypt",             "region": "Middle East", "authority": "HEIA"},
    "JO": {"name": "Jordan",            "region": "Middle East", "authority": "JISM"},
    "IQ": {"name": "Iraq",              "region": "Middle East", "authority": "COSQC"},
    # ── เอเชียตะวันออกเฉียงใต้ ──
    "MY": {"name": "Malaysia",          "region": "SEA",         "authority": "JAKIM"},
    "ID": {"name": "Indonesia",         "region": "SEA",         "authority": "BPJPH / MUI"},
    "BN": {"name": "Brunei",            "region": "SEA",         "authority": "MUIB"},
    "PH": {"name": "Philippines",       "region": "SEA",         "authority": "IDCP / OIAA"},
    # ── เอเชียใต้ ──
    "PK": {"name": "Pakistan",          "region": "South Asia",  "authority": "PNAC"},
    "BD": {"name": "Bangladesh",        "region": "South Asia",  "authority": "BSTI"},
    # ── แอฟริกาเหนือ ──
    "MA": {"name": "Morocco",           "region": "North Africa","authority": "IMANOR"},
    "DZ": {"name": "Algeria",           "region": "North Africa","authority": "IANOR"},
    "TN": {"name": "Tunisia",           "region": "North Africa","authority": "INNORPI"},
    "LY": {"name": "Libya",             "region": "North Africa","authority": "LNCSM"},
    # ── แอฟริกาตะวันตก ──
    "NG": {"name": "Nigeria",           "region": "West Africa", "authority": "NAFDAC / SON"},
    "SN": {"name": "Senegal",           "region": "West Africa", "authority": "ASNOR"},
}

# HS Code ระดับ Chapter (2 หลัก) ที่เกี่ยวข้องกับ Halal
# ครอบคลุมสัตว์มีชีวิต เนื้อสัตว์ ผลิตภัณฑ์สัตว์ ไขมัน อาหารปรุงแต่ง
_HALAL_SENSITIVE_CHAPTERS: set[str] = {
    "01",  # สัตว์มีชีวิต
    "02",  # เนื้อสัตว์
    "03",  # ปลา สัตว์น้ำ
    "04",  # ผลิตภัณฑ์นม ไข่ น้ำผึ้ง
    "05",  # ผลิตภัณฑ์จากสัตว์อื่น
    "10",  # ธัญพืช (บางรายการ)
    "15",  # ไขมัน น้ำมันสัตว์/พืช
    "16",  # ผลิตภัณฑ์จากเนื้อสัตว์/ปลา (กระป๋อง/แปรรูป)
    "17",  # น้ำตาล ขนมหวาน
    "18",  # โกโก้ ช็อกโกแลต
    "19",  # ผลิตภัณฑ์จากธัญพืช แป้ง ขนมปัง
    "20",  # ผักและผลไม้แปรรูป
    "21",  # อาหารปรุงแต่งเบ็ดเตล็ด (ซอส เครื่องปรุง)
    "22",  # เครื่องดื่ม (บางรายการมีแอลกอฮอล์)
    "23",  # กากจากอุตสาหกรรมอาหาร / อาหารสัตว์
    "29",  # สารเคมีอินทรีย์ (บางรายการ เช่น เจลาติน)
    "33",  # เครื่องหอม เครื่องสำอาง (บางรายการมีแอลกอฮอล์)
    "35",  # แป้ง กาว เอนไซม์
    "39",  # พลาสติก (บรรจุภัณฑ์อาหาร)
    "41",  # หนังดิบ
    "43",  # เครื่องหนังขน
}

# Chapter ที่ Halal-Sensitive ระดับสูงมาก (เนื้อสัตว์โดยตรง)
_HIGH_RISK_CHAPTERS: set[str] = {"01", "02", "16"}


# ============================================================
# Public API
# ============================================================

def is_halal_zone(country_code: str) -> bool:
    """ตรวจว่า country_code (ISO alpha-2) เป็นเขตที่ต้องการ Halal หรือไม่"""
    return country_code.upper() in HALAL_MANDATORY_COUNTRIES


def list_halal_countries() -> list[str]:
    """คืนรายชื่อ ISO alpha-2 code ของ 21 ประเทศ Halal ทั้งหมด"""
    return list(HALAL_MANDATORY_COUNTRIES.keys())


def check(hs_code: str, destination_country: str | None = None) -> dict:
    """
    ตรวจสอบข้อกำหนด Halal สำหรับ HS Code และประเทศปลายทาง

    Args:
        hs_code: รหัสพิกัด HS (2, 4, 6, 8 หลักก็ได้)
        destination_country: รหัสประเทศปลายทาง ISO alpha-2 (None = ไม่ระบุ)

    Returns:
        {
            "halal_required": bool,
            "risk_level": "HIGH" | "MEDIUM" | "LOW" | "NONE",
            "hs_chapter": str,
            "destination_is_halal_zone": bool,
            "destination_info": dict | None,
            "notes": str,
            "disclaimer": str,
        }
    """
    hs_clean = str(hs_code).replace(".", "").replace(" ", "").strip()
    chapter = hs_clean[:2] if len(hs_clean) >= 2 else hs_clean.zfill(2)

    dest = destination_country.upper() if destination_country else None
    dest_is_halal_zone = is_halal_zone(dest) if dest else False
    dest_info = HALAL_MANDATORY_COUNTRIES.get(dest) if dest else None

    # ── ประเมิน Halal Risk ──
    is_halal_sensitive = chapter in _HALAL_SENSITIVE_CHAPTERS
    is_high_risk = chapter in _HIGH_RISK_CHAPTERS

    if dest_is_halal_zone and is_high_risk:
        risk_level = "HIGH"
        halal_required = True
        notes = (
            f"Chapter {chapter} (เนื้อสัตว์/ผลิตภัณฑ์สัตว์) ส่งออกไป {dest} "
            f"({dest_info['name']}) ต้องมีใบรับรอง Halal จาก {dest_info['authority']}"
        )
    elif dest_is_halal_zone and is_halal_sensitive:
        risk_level = "MEDIUM"
        halal_required = True
        notes = (
            f"Chapter {chapter} อยู่ในกลุ่มสินค้าที่ต้องตรวจสอบ Halal "
            f"เมื่อส่งออกไป {dest} ({dest_info['name']}) "
            f"ควรขอใบรับรองจาก {dest_info['authority']} เพื่อความปลอดภัย"
        )
    elif dest_is_halal_zone and not is_halal_sensitive:
        risk_level = "LOW"
        halal_required = False
        notes = (
            f"Chapter {chapter} ไม่ใช่สินค้า Halal-Sensitive "
            f"แต่ปลายทาง {dest} เป็นประเทศ Halal Zone — "
            "ควรตรวจสอบข้อกำหนดเฉพาะสินค้ากับหน่วยงานก่อนส่งออก"
        )
    elif not dest_is_halal_zone and is_halal_sensitive:
        risk_level = "LOW"
        halal_required = False
        notes = (
            f"Chapter {chapter} เป็นสินค้า Halal-Sensitive "
            f"แต่ปลายทาง '{dest or 'ไม่ระบุ'}' ไม่ใช่ Halal Zone ตาม 21 ประเทศที่ติดตาม"
        )
    else:
        risk_level = "NONE"
        halal_required = False
        notes = f"Chapter {chapter} ไม่ใช่สินค้า Halal-Sensitive และปลายทางไม่ใช่ Halal Zone"

    return {
        "halal_required": halal_required,
        "risk_level": risk_level,
        "hs_chapter": chapter,
        "destination_is_halal_zone": dest_is_halal_zone,
        "destination_info": dest_info,
        "notes": notes,
        "disclaimer": (
            "Halal Engine v1.0 — ข้อมูลเพื่อประกอบการตัดสินใจเบื้องต้นเท่านั้น "
            "ต้องตรวจสอบข้อกำหนดล่าสุดจากหน่วยงาน Halal ของประเทศปลายทางก่อนส่งออกจริง"
        ),
    }
