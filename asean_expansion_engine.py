"""
asean_expansion_engine.py — Phase 28: ASEAN Expansion
AI TO AI HOLDING — Customs Intelligence Division

ขยายจากไทย → เวียดนาม / มาเลเซีย / อินโดนีเซีย / ฟิลิปปินส์:
  - ข้อมูลภาษี MFN / FTA แต่ละประเทศ
  - โครงสร้างศุลกากร + หน่วยงาน
  - Duty comparison ข้ามประเทศ
  - Multi-country compliance check
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


# ── ASEAN Country Profiles ───────────────────────────────────────────────────

ASEAN_COUNTRIES = {
    # Sources: WTO Tariff Profiles 2024, trade.gov, macrotrends.net
    # Thai avg MFN: 7.4% trade-weighted (WTO 2024); Ag 28.3%, Non-Ag 7%
    # VN avg MFN: 9.6% (WTO 2024); recently reduced on select ag products
    # MY avg MFN: 6.1% (WTO); ID avg MFN: 8.1% (WTO)
    # Last verified: June 2026

    "TH": {
        "name_th": "ไทย",
        "name_en": "Thailand",
        "customs_authority": "กรมศุลกากร (Thai Customs Department)",
        "currency": "THB",
        "vat_rate": 7.0,
        "hs_digits": 11,  # HS code ใช้กี่หลัก
        "avg_mfn_rate": 7.4,  # WTO 2024 trade-weighted; simple avg ~11.5%
        "trade_agreements": ["ATIGA", "ACFTA", "JTEPA", "AKFTA", "TAFTA", "TNZFTA",
                             "AIFTA", "RCEP", "TCFTA", "TPFTA"],
        "nsw_url": "https://nsw.customs.go.th",
        "tariff_url": "https://igtf.customs.go.th",
        "status": "LIVE",
    },
    "VN": {
        "name_th": "เวียดนาม",
        "name_en": "Vietnam",
        "customs_authority": "General Department of Vietnam Customs (GDVC)",
        "currency": "VND",
        "vat_rate": 8.0,   # Reduced from 10% to 8% (extended)
        "hs_digits": 8,
        "avg_mfn_rate": 9.5,  # WTO 2024; reduced on select ag products Mar 2025
        "trade_agreements": ["ATIGA", "ACFTA", "AJCEP", "VKFTA", "EVFTA", "CPTPP",
                             "RCEP", "UKVFTA"],
        "nsw_url": "https://vnsw.gov.vn",
        "tariff_url": "https://customs.gov.vn",
        "status": "BETA",
    },
    "MY": {
        "name_th": "มาเลเซีย",
        "name_en": "Malaysia",
        "customs_authority": "Royal Malaysian Customs Department (JKDM)",
        "currency": "MYR",
        "vat_rate": 0.0,    # No VAT, SST 6-10%
        "sst_rate": 10.0,    # Sales and Service Tax
        "hs_digits": 10,
        "avg_mfn_rate": 6.1,
        "trade_agreements": ["ATIGA", "ACFTA", "MJEPA", "AKFTA", "MNZFTA", "MAIFTA",
                             "RCEP", "CPTPP"],
        "nsw_url": "https://www.mnsw.gov.my",
        "tariff_url": "https://www.dagangnet.com",
        "status": "BETA",
    },
    "ID": {
        "name_th": "อินโดนีเซีย",
        "name_en": "Indonesia",
        "customs_authority": "Directorate General of Customs and Excise (DJBC)",
        "currency": "IDR",
        "vat_rate": 11.0,
        "hs_digits": 10,
        "avg_mfn_rate": 8.1,
        "trade_agreements": ["ATIGA", "ACFTA", "IJEPA", "AKFTA", "IA-CEPA", "RCEP",
                             "IK-CEPA"],
        "nsw_url": "https://insw.go.id",
        "tariff_url": "https://insw.go.id/intr",
        "status": "BETA",
    },
    "PH": {
        "name_th": "ฟิลิปปินส์",
        "name_en": "Philippines",
        "customs_authority": "Bureau of Customs (BOC)",
        "currency": "PHP",
        "vat_rate": 12.0,
        "hs_digits": 10,
        "avg_mfn_rate": 6.3,
        "trade_agreements": ["ATIGA", "ACFTA", "PJEPA", "AKFTA", "RCEP"],
        "nsw_url": "https://nsw.gov.ph",
        "tariff_url": "https://finder.tariffcommission.gov.ph",
        "status": "PLANNED",
    },
    "SG": {
        "name_th": "สิงคโปร์",
        "name_en": "Singapore",
        "customs_authority": "Singapore Customs",
        "currency": "SGD",
        "vat_rate": 9.0,   # GST
        "hs_digits": 8,
        "avg_mfn_rate": 0.0,  # Free port
        "trade_agreements": ["ATIGA", "ACFTA", "JSEPA", "KSFTA", "USSFTA",
                             "RCEP", "CPTPP", "EUSFTA"],
        "nsw_url": "https://www.tradenet.gov.sg",
        "tariff_url": "https://www.customs.gov.sg",
        "status": "PLANNED",
    },
}


# ── Sample Duty Rates by Country (HS 4-digit level) ─────────────────────────
# In production, this would come from each country's tariff DB

SAMPLE_DUTIES = {
    # HS 8517 — Telephones
    "8517": {"TH": 0, "VN": 0, "MY": 0, "ID": 0, "PH": 0, "SG": 0},
    # HS 8471 — Computers
    "8471": {"TH": 0, "VN": 0, "MY": 0, "ID": 0, "PH": 0, "SG": 0},
    # HS 6203 — Men's clothing
    "6203": {"TH": 30, "VN": 20, "MY": 15, "ID": 25, "PH": 15, "SG": 0},
    # HS 6204 — Women's clothing
    "6204": {"TH": 30, "VN": 20, "MY": 15, "ID": 25, "PH": 15, "SG": 0},
    # HS 2204 — Wine
    "2204": {"TH": 54, "VN": 45, "MY": 0, "ID": 150, "PH": 15, "SG": 0},
    # HS 8703 — Passenger cars
    "8703": {"TH": 80, "VN": 70, "MY": 30, "ID": 50, "PH": 30, "SG": 0},
    # HS 7208 — Hot-rolled steel
    "7208": {"TH": 5, "VN": 8, "MY": 15, "ID": 10, "PH": 3, "SG": 0},
    # HS 3004 — Medicines
    "3004": {"TH": 8, "VN": 5, "MY": 0, "ID": 5, "PH": 3, "SG": 0},
    # HS 2106 — Food preparations
    "2106": {"TH": 30, "VN": 22, "MY": 5, "ID": 20, "PH": 10, "SG": 0},
    # HS 8528 — TVs
    "8528": {"TH": 20, "VN": 20, "MY": 30, "ID": 10, "PH": 10, "SG": 0},
    # HS 3304 — Cosmetics
    "3304": {"TH": 30, "VN": 10, "MY": 0, "ID": 15, "PH": 10, "SG": 0},
    # HS 0901 — Coffee
    "0901": {"TH": 40, "VN": 15, "MY": 0, "ID": 5, "PH": 7, "SG": 0},
}


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class DutyComparison:
    hs_code: str
    comparisons: list[dict]
    cheapest_country: str
    cheapest_rate: float
    most_expensive_country: str
    most_expensive_rate: float

    def to_dict(self) -> dict:
        return {
            "hs_code": self.hs_code,
            "comparisons": self.comparisons,
            "cheapest": {"country": self.cheapest_country, "rate_pct": self.cheapest_rate},
            "most_expensive": {"country": self.most_expensive_country, "rate_pct": self.most_expensive_rate},
        }


@dataclass
class ComplianceCheck:
    country_code: str
    country_name: str
    hs_code: str
    mfn_rate: float
    vat_rate: float
    total_import_tax_pct: float
    ftas_available: list[str]
    required_docs: list[str]
    status: str  # LIVE / BETA / PLANNED

    def to_dict(self) -> dict:
        return {
            "country_code": self.country_code,
            "country_name": self.country_name,
            "hs_code": self.hs_code,
            "mfn_rate_pct": self.mfn_rate,
            "vat_rate_pct": self.vat_rate,
            "estimated_total_import_tax_pct": round(self.total_import_tax_pct, 2),
            "ftas_available": self.ftas_available,
            "required_documents": self.required_docs,
            "coverage_status": self.status,
        }


# ── Core Functions ───────────────────────────────────────────────────────────

def compare_duties(hs_code: str, countries: Optional[list[str]] = None) -> DutyComparison:
    """
    เปรียบเทียบอัตราอากรข้ามประเทศ ASEAN
    """
    hs_4 = hs_code.replace(".", "").replace(" ", "")[:4]

    if countries:
        target = [c.upper() for c in countries if c.upper() in ASEAN_COUNTRIES]
    else:
        target = list(ASEAN_COUNTRIES.keys())

    comparisons = []
    for cc in target:
        profile = ASEAN_COUNTRIES[cc]
        rate = SAMPLE_DUTIES.get(hs_4, {}).get(cc, profile["avg_mfn_rate"])
        vat = profile.get("sst_rate", profile["vat_rate"])
        total = rate + vat

        comparisons.append({
            "country": cc,
            "country_name": profile["name_en"],
            "duty_rate_pct": rate,
            "vat_gst_pct": vat,
            "total_pct": round(total, 1),
            "currency": profile["currency"],
            "status": profile["status"],
        })

    comparisons.sort(key=lambda x: x["total_pct"])

    cheapest = comparisons[0] if comparisons else {"country": "N/A", "total_pct": 0}
    expensive = comparisons[-1] if comparisons else {"country": "N/A", "total_pct": 0}

    return DutyComparison(
        hs_code=hs_code,
        comparisons=comparisons,
        cheapest_country=cheapest["country"],
        cheapest_rate=cheapest["total_pct"],
        most_expensive_country=expensive["country"],
        most_expensive_rate=expensive["total_pct"],
    )


def check_compliance(
    hs_code: str,
    country_code: str,
) -> ComplianceCheck:
    """
    ตรวจ compliance สำหรับนำเข้าไปประเทศ ASEAN
    """
    cc = country_code.upper()
    profile = ASEAN_COUNTRIES.get(cc)
    if not profile:
        return ComplianceCheck(
            country_code=cc, country_name="Unknown",
            hs_code=hs_code, mfn_rate=0, vat_rate=0,
            total_import_tax_pct=0, ftas_available=[],
            required_docs=["Country not supported yet"],
            status="NOT_SUPPORTED",
        )

    hs_4 = hs_code.replace(".", "").replace(" ", "")[:4]
    mfn = SAMPLE_DUTIES.get(hs_4, {}).get(cc, profile["avg_mfn_rate"])
    vat = profile.get("sst_rate", profile["vat_rate"])

    # Standard import docs per country
    docs = _get_standard_docs(cc)

    return ComplianceCheck(
        country_code=cc,
        country_name=profile["name_en"],
        hs_code=hs_code,
        mfn_rate=mfn,
        vat_rate=vat,
        total_import_tax_pct=mfn + vat,
        ftas_available=profile["trade_agreements"],
        required_docs=docs,
        status=profile["status"],
    )


def multi_country_check(
    hs_code: str,
    countries: Optional[list[str]] = None,
) -> list[dict]:
    """ตรวจ compliance หลายประเทศพร้อมกัน"""
    if countries:
        targets = [c.upper() for c in countries if c.upper() in ASEAN_COUNTRIES]
    else:
        targets = list(ASEAN_COUNTRIES.keys())

    return [check_compliance(hs_code, cc).to_dict() for cc in targets]


def get_country_profile(country_code: str) -> Optional[dict]:
    """ข้อมูลประเทศ ASEAN"""
    cc = country_code.upper()
    profile = ASEAN_COUNTRIES.get(cc)
    if not profile:
        return None
    return {"country_code": cc, **profile}


def get_all_countries() -> list[dict]:
    """รายชื่อประเทศ ASEAN ที่รองรับ"""
    return [
        {"country_code": cc, **profile}
        for cc, profile in ASEAN_COUNTRIES.items()
    ]


def get_expansion_status() -> dict:
    """สถานะการขยาย"""
    by_status = {}
    for cc, profile in ASEAN_COUNTRIES.items():
        s = profile["status"]
        by_status.setdefault(s, []).append(cc)

    return {
        "total_countries": len(ASEAN_COUNTRIES),
        "live": by_status.get("LIVE", []),
        "beta": by_status.get("BETA", []),
        "planned": by_status.get("PLANNED", []),
        "hs_codes_with_duty_data": len(SAMPLE_DUTIES),
    }


# ── Internal ─────────────────────────────────────────────────────────────────

def _get_standard_docs(cc: str) -> list[str]:
    common = [
        "Commercial Invoice",
        "Bill of Lading / Air Waybill",
        "Packing List",
        "Certificate of Origin (for FTA preference)",
    ]

    extras = {
        "TH": ["ใบขนสินค้าขาเข้า", "ใบอนุญาต OGA (ถ้าจำเป็น)"],
        "VN": ["Tờ khai hải quan (Customs Declaration)", "Import License (if required)"],
        "MY": ["Customs Form K1", "Import Permit (AP) if applicable"],
        "ID": ["Pemberitahuan Impor Barang (PIB)", "NPIK (Importir Terdaftar)"],
        "PH": ["Import Entry Declaration", "Bureau of Customs clearance"],
        "SG": ["TradeNet Declaration", "Customs permit (IN)"],
    }

    return common + extras.get(cc, [])
