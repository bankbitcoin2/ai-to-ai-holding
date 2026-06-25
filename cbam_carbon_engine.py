"""
cbam_carbon_engine.py — Phase 27: CBAM Carbon Tracker
AI TO AI HOLDING — Customs Intelligence Division

คำนวณ Carbon Footprint สำหรับสินค้านำเข้า/ส่งออก:
  - EU CBAM (Carbon Border Adjustment Mechanism) compliance
  - คำนวณ CO₂ emissions per product
  - ออก Carbon Report สำหรับส่งออกไปยุโรป/อเมริกา
  - ติดตาม EU ETS pricing

อ้างอิง: EU CBAM Regulation 2023/956, IPCC emission factors
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ── CBAM Covered Sectors ─────────────────────────────────────────────────────
# EU CBAM Phase 1 (2026+): cement, iron/steel, aluminium, fertilizers,
# electricity, hydrogen

CBAM_SECTORS = {
    "cement":       {"hs_chapters": ["2523"], "label_th": "ปูนซีเมนต์", "label_en": "Cement"},
    "iron_steel":   {"hs_chapters": ["72", "73"], "label_th": "เหล็กและเหล็กกล้า", "label_en": "Iron & Steel"},
    "aluminium":    {"hs_chapters": ["76"], "label_th": "อลูมิเนียม", "label_en": "Aluminium"},
    "fertilizers":  {"hs_chapters": ["31"], "label_th": "ปุ๋ย", "label_en": "Fertilizers"},
    "electricity":  {"hs_chapters": ["2716"], "label_th": "ไฟฟ้า", "label_en": "Electricity"},
    "hydrogen":     {"hs_chapters": ["2804"], "label_th": "ไฮโดรเจน", "label_en": "Hydrogen"},
}


# ── Default Emission Factors (kg CO₂e per tonne of product) ─────────────────
# Source: IPCC, EU default values for CBAM reporting

EMISSION_FACTORS = {
    # Cement
    "2523": {"factor": 640, "unit": "kg CO₂e/tonne", "source": "IPCC default — clinker production"},

    # Iron & Steel
    "72": {"factor": 1850, "unit": "kg CO₂e/tonne", "source": "IPCC default — blast furnace route"},
    "7201": {"factor": 2100, "unit": "kg CO₂e/tonne", "source": "Pig iron — high emission"},
    "7206": {"factor": 600, "unit": "kg CO₂e/tonne", "source": "EAF scrap-based steel"},
    "7207": {"factor": 1900, "unit": "kg CO₂e/tonne", "source": "Semi-finished steel"},
    "7208": {"factor": 1950, "unit": "kg CO₂e/tonne", "source": "Hot-rolled flat steel"},
    "7209": {"factor": 2050, "unit": "kg CO₂e/tonne", "source": "Cold-rolled flat steel"},
    "73": {"factor": 1800, "unit": "kg CO₂e/tonne", "source": "Steel articles — average"},

    # Aluminium
    "76": {"factor": 8400, "unit": "kg CO₂e/tonne", "source": "Primary aluminium — global average"},
    "7601": {"factor": 10000, "unit": "kg CO₂e/tonne", "source": "Unwrought aluminium (primary)"},
    "7602": {"factor": 500, "unit": "kg CO₂e/tonne", "source": "Aluminium scrap (secondary)"},

    # Fertilizers
    "31": {"factor": 2500, "unit": "kg CO₂e/tonne", "source": "Nitrogen fertilizer — ammonia process"},
    "3102": {"factor": 3200, "unit": "kg CO₂e/tonne", "source": "Urea — high emission"},
    "3105": {"factor": 2000, "unit": "kg CO₂e/tonne", "source": "NPK compound fertilizer"},

    # Hydrogen
    "2804": {"factor": 9000, "unit": "kg CO₂e/tonne", "source": "Grey hydrogen (natural gas SMR)"},

    # Electricity
    "2716": {"factor": 500, "unit": "kg CO₂e/MWh", "source": "Global average grid emission factor"},
}


# ── Country Grid Emission Factors (kg CO₂e per MWh) ─────────────────────────
# Used for indirect emissions from electricity in production

GRID_FACTORS = {
    "TH": 470, "CN": 570, "IN": 720, "VN": 510, "ID": 650,
    "MY": 580, "JP": 430, "KR": 420, "US": 390, "DE": 320,
    "FR": 60,  "SE": 13,  "AU": 660, "BR": 70,  "RU": 340,
    "TR": 440, "ZA": 900, "GB": 230, "PL": 680, "IT": 330,
}

# ── EU ETS Price Reference ──────────────────────────────────────────────────
EU_ETS_PRICE_EUR_PER_TONNE = 65.0   # Updated periodically; seed value ~€65


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class CarbonFootprint:
    """ผลคำนวณ Carbon Footprint ต่อสินค้า"""
    hs_code: str
    product_description: str
    weight_tonnes: float
    direct_emissions_kg: float       # Scope 1
    indirect_emissions_kg: float     # Scope 2 (electricity)
    total_emissions_kg: float        # Total CO₂e
    emission_factor_used: float
    emission_factor_source: str
    cbam_applicable: bool
    cbam_sector: Optional[str]
    cbam_cost_eur: float             # Estimated CBAM certificate cost

    def to_dict(self) -> dict:
        return {
            "hs_code": self.hs_code,
            "product_description": self.product_description,
            "weight_tonnes": round(self.weight_tonnes, 3),
            "direct_emissions_kg_co2e": round(self.direct_emissions_kg, 2),
            "indirect_emissions_kg_co2e": round(self.indirect_emissions_kg, 2),
            "total_emissions_kg_co2e": round(self.total_emissions_kg, 2),
            "total_emissions_tonnes_co2e": round(self.total_emissions_kg / 1000, 4),
            "emission_factor": self.emission_factor_used,
            "emission_factor_source": self.emission_factor_source,
            "cbam_applicable": self.cbam_applicable,
            "cbam_sector": self.cbam_sector,
            "estimated_cbam_cost_eur": round(self.cbam_cost_eur, 2),
        }


@dataclass
class CarbonReport:
    """รายงาน Carbon ภาพรวม"""
    items: list[CarbonFootprint]
    total_emissions_tonnes: float
    total_cbam_cost_eur: float
    cbam_items_count: int
    non_cbam_items_count: int
    generated_at: str
    reporting_period: str

    def to_dict(self) -> dict:
        return {
            "items": [i.to_dict() for i in self.items],
            "summary": {
                "total_items": len(self.items),
                "total_emissions_tonnes_co2e": round(self.total_emissions_tonnes, 4),
                "total_cbam_cost_eur": round(self.total_cbam_cost_eur, 2),
                "cbam_items_count": self.cbam_items_count,
                "non_cbam_items_count": self.non_cbam_items_count,
                "eu_ets_price_eur_per_tonne": EU_ETS_PRICE_EUR_PER_TONNE,
            },
            "generated_at": self.generated_at,
            "reporting_period": self.reporting_period,
        }


# ── Core Functions ───────────────────────────────────────────────────────────

def calculate_carbon_footprint(
    hs_code: str,
    weight_kg: float,
    origin_country: str = "CN",
    product_description: str = "",
    custom_emission_factor: Optional[float] = None,
) -> CarbonFootprint:
    """
    คำนวณ Carbon Footprint ต่อสินค้า
    """
    hs_clean = hs_code.replace(".", "").replace(" ", "").strip()
    weight_tonnes = weight_kg / 1000.0

    # หา emission factor — ยาวสุดก่อน
    factor_info = None
    for length in (6, 4, 2):
        prefix = hs_clean[:length]
        if prefix in EMISSION_FACTORS:
            factor_info = EMISSION_FACTORS[prefix]
            break

    if custom_emission_factor:
        ef = custom_emission_factor
        source = "Custom / Verified by producer"
    elif factor_info:
        ef = factor_info["factor"]
        source = factor_info["source"]
    else:
        ef = 500  # Conservative default
        source = "Generic default (no specific factor found)"

    # Direct emissions (Scope 1)
    direct = ef * weight_tonnes

    # Indirect emissions (Scope 2) — from grid electricity
    grid_factor = GRID_FACTORS.get(origin_country.upper(), 500)
    # Assume ~0.5 MWh electricity per tonne of product (generic estimate)
    indirect = grid_factor * 0.5 * weight_tonnes

    total = direct + indirect

    # Check CBAM applicability
    cbam_sector = _find_cbam_sector(hs_clean)
    cbam_applicable = cbam_sector is not None

    # Calculate CBAM cost
    cbam_cost = 0.0
    if cbam_applicable:
        cbam_cost = (total / 1000.0) * EU_ETS_PRICE_EUR_PER_TONNE

    return CarbonFootprint(
        hs_code=hs_code,
        product_description=product_description,
        weight_tonnes=weight_tonnes,
        direct_emissions_kg=direct,
        indirect_emissions_kg=indirect,
        total_emissions_kg=total,
        emission_factor_used=ef,
        emission_factor_source=source,
        cbam_applicable=cbam_applicable,
        cbam_sector=cbam_sector,
        cbam_cost_eur=cbam_cost,
    )


def generate_carbon_report(
    items: list[dict],
    reporting_period: str = "Q1 2026",
) -> CarbonReport:
    """
    สร้าง Carbon Report จากรายการสินค้า

    items: list of dict with keys: hs_code, weight_kg, origin_country, description
    """
    footprints = []
    for item in items:
        fp = calculate_carbon_footprint(
            hs_code=item.get("hs_code", ""),
            weight_kg=item.get("weight_kg", 0),
            origin_country=item.get("origin_country", "CN"),
            product_description=item.get("description", ""),
            custom_emission_factor=item.get("emission_factor"),
        )
        footprints.append(fp)

    total_emissions = sum(fp.total_emissions_kg for fp in footprints) / 1000.0
    total_cbam = sum(fp.cbam_cost_eur for fp in footprints)
    cbam_count = sum(1 for fp in footprints if fp.cbam_applicable)

    return CarbonReport(
        items=footprints,
        total_emissions_tonnes=total_emissions,
        total_cbam_cost_eur=total_cbam,
        cbam_items_count=cbam_count,
        non_cbam_items_count=len(footprints) - cbam_count,
        generated_at=datetime.now(timezone.utc).isoformat(),
        reporting_period=reporting_period,
    )


def check_cbam_applicability(hs_code: str) -> dict:
    """ตรวจว่า HS code อยู่ภายใต้ EU CBAM หรือไม่"""
    hs_clean = hs_code.replace(".", "").replace(" ", "").strip()
    sector = _find_cbam_sector(hs_clean)

    if sector:
        info = CBAM_SECTORS[sector]
        return {
            "hs_code": hs_code,
            "cbam_applicable": True,
            "sector": sector,
            "sector_th": info["label_th"],
            "sector_en": info["label_en"],
            "matched_chapters": info["hs_chapters"],
            "note": f"สินค้านี้อยู่ภายใต้ EU CBAM — ต้องรายงาน CO₂ emissions ตั้งแต่ 2026",
        }
    return {
        "hs_code": hs_code,
        "cbam_applicable": False,
        "sector": None,
        "note": "HS code นี้ยังไม่อยู่ภายใต้ EU CBAM Phase 1 (2026)",
    }


def get_emission_factor(hs_code: str) -> dict:
    """ดึง emission factor สำหรับ HS code"""
    hs_clean = hs_code.replace(".", "").replace(" ", "").strip()

    for length in (6, 4, 2):
        prefix = hs_clean[:length]
        if prefix in EMISSION_FACTORS:
            return {
                "hs_code": hs_code,
                "matched_prefix": prefix,
                "found": True,
                **EMISSION_FACTORS[prefix],
            }

    return {
        "hs_code": hs_code,
        "matched_prefix": None,
        "found": False,
        "factor": 500,
        "unit": "kg CO₂e/tonne",
        "source": "Generic default — consider providing actual production data",
    }


def get_cbam_sectors() -> list[dict]:
    """รายการ sectors ภายใต้ EU CBAM"""
    return [
        {
            "sector": key,
            "label_th": info["label_th"],
            "label_en": info["label_en"],
            "hs_chapters": info["hs_chapters"],
        }
        for key, info in CBAM_SECTORS.items()
    ]


def get_grid_factors() -> dict:
    """Grid emission factors ของแต่ละประเทศ"""
    return {
        "unit": "kg CO₂e per MWh",
        "factors": GRID_FACTORS,
    }


# ── Internal ─────────────────────────────────────────────────────────────────

def _find_cbam_sector(hs_digits: str) -> Optional[str]:
    """หา CBAM sector จาก HS digits"""
    for sector, info in CBAM_SECTORS.items():
        for ch in info["hs_chapters"]:
            if hs_digits.startswith(ch):
                return sector
    return None
