"""
freight_rate_service.py — Phase 21: Freight Rate Reference Service
AI TO AI HOLDING — Customs Intelligence Division

ฐานข้อมูลอ้างอิงค่าขนส่ง ค่าประกัน ค่าใช้จ่ายท้องถิ่น (Thailand)
สำหรับประมาณการ Landed Cost

ข้อมูลจาก:
  - อัตราตลาดทั่วไป 2025-2026
  - Freight Forwarder Rate Schedule (เฉลี่ยจากหลายราย)
  - กรมศุลกากร — ระเบียบว่าด้วยราคาศุลกากร

Future (Phase 23):
  - Crowdsource จากบิลจริงของลูกค้า (anonymized)
  - API เชื่อม Freightos/Xeneta
  - Auto-update monthly

Usage:
    rate = get_freight_rate("sea", "CN", weight_kg=500, cbm=2.5)
    insurance = get_insurance_rate(goods_value=10000, freight=500)
    charges = get_local_charges("sea", "laem_chabang")
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone


# ══════════════════════════════════════════════════════════════════════════════
# FREIGHT RATES — Reference by Mode + Origin Region
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FreightRate:
    """Reference freight rate."""
    mode: str               # sea, air, land
    origin_region: str      # asean, east_asia, south_asia, europe, americas, oceania
    rate_per_kg: float      # USD/kg
    rate_per_cbm: float     # USD/CBM (sea only)
    min_charge: float       # Minimum charge USD
    transit_days_min: int
    transit_days_max: int
    notes: str = ""


# Sea freight rates to Thailand (Laem Chabang / Bangkok Port)
# Based on market averages — FCL 20ft ÷ typical load
_SEA_RATES: dict[str, FreightRate] = {
    "asean": FreightRate(
        mode="sea", origin_region="asean",
        rate_per_kg=0.05, rate_per_cbm=25.0, min_charge=150.0,
        transit_days_min=3, transit_days_max=7,
        notes="VN/MY/SG/ID/PH → Laem Chabang"
    ),
    "east_asia": FreightRate(
        mode="sea", origin_region="east_asia",
        rate_per_kg=0.08, rate_per_cbm=40.0, min_charge=200.0,
        transit_days_min=5, transit_days_max=14,
        notes="CN/JP/KR/TW/HK → Laem Chabang"
    ),
    "south_asia": FreightRate(
        mode="sea", origin_region="south_asia",
        rate_per_kg=0.07, rate_per_cbm=35.0, min_charge=180.0,
        transit_days_min=7, transit_days_max=18,
        notes="IN/BD/LK/PK → Laem Chabang"
    ),
    "europe": FreightRate(
        mode="sea", origin_region="europe",
        rate_per_kg=0.12, rate_per_cbm=55.0, min_charge=350.0,
        transit_days_min=25, transit_days_max=35,
        notes="EU ports → Laem Chabang"
    ),
    "americas": FreightRate(
        mode="sea", origin_region="americas",
        rate_per_kg=0.15, rate_per_cbm=65.0, min_charge=400.0,
        transit_days_min=28, transit_days_max=40,
        notes="US/CA/MX/BR/CL → Laem Chabang"
    ),
    "oceania": FreightRate(
        mode="sea", origin_region="oceania",
        rate_per_kg=0.10, rate_per_cbm=45.0, min_charge=250.0,
        transit_days_min=12, transit_days_max=20,
        notes="AU/NZ → Laem Chabang"
    ),
}

# Air freight rates to Thailand (Suvarnabhumi)
_AIR_RATES: dict[str, FreightRate] = {
    "asean": FreightRate(
        mode="air", origin_region="asean",
        rate_per_kg=2.00, rate_per_cbm=0, min_charge=100.0,
        transit_days_min=1, transit_days_max=3,
        notes="ASEAN → BKK Suvarnabhumi"
    ),
    "east_asia": FreightRate(
        mode="air", origin_region="east_asia",
        rate_per_kg=3.00, rate_per_cbm=0, min_charge=120.0,
        transit_days_min=1, transit_days_max=4,
        notes="CN/JP/KR → BKK"
    ),
    "south_asia": FreightRate(
        mode="air", origin_region="south_asia",
        rate_per_kg=2.80, rate_per_cbm=0, min_charge=120.0,
        transit_days_min=1, transit_days_max=4,
        notes="IN/BD → BKK"
    ),
    "europe": FreightRate(
        mode="air", origin_region="europe",
        rate_per_kg=4.50, rate_per_cbm=0, min_charge=200.0,
        transit_days_min=2, transit_days_max=5,
        notes="EU → BKK"
    ),
    "americas": FreightRate(
        mode="air", origin_region="americas",
        rate_per_kg=5.50, rate_per_cbm=0, min_charge=250.0,
        transit_days_min=2, transit_days_max=6,
        notes="US/CA → BKK"
    ),
    "oceania": FreightRate(
        mode="air", origin_region="oceania",
        rate_per_kg=3.50, rate_per_cbm=0, min_charge=150.0,
        transit_days_min=2, transit_days_max=4,
        notes="AU/NZ → BKK"
    ),
}

# Land freight rates (cross-border)
_LAND_RATES: dict[str, FreightRate] = {
    "asean": FreightRate(
        mode="land", origin_region="asean",
        rate_per_kg=0.08, rate_per_cbm=30.0, min_charge=80.0,
        transit_days_min=1, transit_days_max=5,
        notes="MY/LA/MM/KH → Thai border"
    ),
    "east_asia": FreightRate(
        mode="land", origin_region="east_asia",
        rate_per_kg=0.12, rate_per_cbm=45.0, min_charge=200.0,
        transit_days_min=5, transit_days_max=12,
        notes="CN (Kunming/Nanning) → Thai border via Laos/Myanmar"
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
# COUNTRY → REGION MAPPING
# ══════════════════════════════════════════════════════════════════════════════

_COUNTRY_REGION: dict[str, str] = {
    # ASEAN
    "VN": "asean", "MY": "asean", "SG": "asean", "ID": "asean",
    "PH": "asean", "MM": "asean", "KH": "asean", "LA": "asean",
    "BN": "asean",
    # East Asia
    "CN": "east_asia", "JP": "east_asia", "KR": "east_asia",
    "TW": "east_asia", "HK": "east_asia", "MO": "east_asia",
    # South Asia
    "IN": "south_asia", "BD": "south_asia", "LK": "south_asia",
    "PK": "south_asia", "NP": "south_asia",
    # Europe
    "DE": "europe", "FR": "europe", "IT": "europe", "ES": "europe",
    "GB": "europe", "NL": "europe", "BE": "europe", "CH": "europe",
    "AT": "europe", "SE": "europe", "DK": "europe", "FI": "europe",
    "PL": "europe", "CZ": "europe", "PT": "europe", "IE": "europe",
    "TR": "europe", "RU": "europe",
    # Americas
    "US": "americas", "CA": "americas", "MX": "americas",
    "BR": "americas", "CL": "americas", "AR": "americas",
    "CO": "americas", "PE": "americas",
    # Oceania
    "AU": "oceania", "NZ": "oceania",
}


def _get_region(country_code: str) -> str:
    """Map country code to freight region."""
    return _COUNTRY_REGION.get(country_code.upper(), "east_asia")  # default


# ══════════════════════════════════════════════════════════════════════════════
# LOCAL CHARGES — Thai Ports & Airports
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PortCharges:
    """Local charges at a specific Thai port/airport."""
    port_code: str
    port_name: str
    thc_20ft: float         # THC per 20ft container (USD)
    thc_40ft: float         # THC per 40ft container
    cfs_per_cbm: float      # CFS fee per CBM
    do_fee: float           # Delivery Order fee
    customs_clearance: float  # Broker fee (average)
    inland_to_bkk: float   # Transport to Bangkok/industrial zone
    wharfage: float         # Port wharfage per ton
    notes: str = ""


THAI_PORTS: dict[str, PortCharges] = {
    "laem_chabang": PortCharges(
        port_code="THLCH", port_name="Laem Chabang",
        thc_20ft=115.0, thc_40ft=175.0, cfs_per_cbm=8.0,
        do_fee=30.0, customs_clearance=80.0, inland_to_bkk=150.0,
        wharfage=1.50,
        notes="Main deep-sea port — 80% of Thai sea freight"
    ),
    "bangkok_port": PortCharges(
        port_code="THBKK", port_name="Bangkok Port (Klong Toei)",
        thc_20ft=100.0, thc_40ft=155.0, cfs_per_cbm=7.0,
        do_fee=25.0, customs_clearance=80.0, inland_to_bkk=50.0,
        wharfage=1.20,
        notes="City port — congested but close to Bangkok"
    ),
    "suvarnabhumi": PortCharges(
        port_code="THBKK_AIR", port_name="Suvarnabhumi Airport",
        thc_20ft=0, thc_40ft=0, cfs_per_cbm=0,
        do_fee=20.0, customs_clearance=80.0, inland_to_bkk=60.0,
        wharfage=0,
        notes="Main international airport — air cargo"
    ),
    "border_north": PortCharges(
        port_code="THCEI", port_name="Chiang Rai / Chiang Saen",
        thc_20ft=0, thc_40ft=0, cfs_per_cbm=0,
        do_fee=15.0, customs_clearance=50.0, inland_to_bkk=200.0,
        wharfage=0,
        notes="Northern border — Myanmar/Laos/China R3A"
    ),
    "border_east": PortCharges(
        port_code="THMKM", port_name="Mukdahan / Nong Khai",
        thc_20ft=0, thc_40ft=0, cfs_per_cbm=0,
        do_fee=15.0, customs_clearance=50.0, inland_to_bkk=180.0,
        wharfage=0,
        notes="Eastern border — Laos/Vietnam"
    ),
    "border_south": PortCharges(
        port_code="THSGN", port_name="Sadao / Padang Besar",
        thc_20ft=0, thc_40ft=0, cfs_per_cbm=0,
        do_fee=15.0, customs_clearance=50.0, inland_to_bkk=250.0,
        wharfage=0,
        notes="Southern border — Malaysia"
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
# INSURANCE RATES
# ══════════════════════════════════════════════════════════════════════════════

# Insurance rate by cargo category (% of insurable value)
INSURANCE_RATES: dict[str, float] = {
    "general": 0.003,       # 0.30% — general cargo
    "fragile": 0.005,       # 0.50% — glass, ceramics, electronics
    "perishable": 0.008,    # 0.80% — food, flowers, pharma
    "hazardous": 0.010,     # 1.00% — chemicals, flammables
    "high_value": 0.002,    # 0.20% — jewelry, gold (high value, low risk)
    "bulk": 0.002,          # 0.20% — raw materials, commodities
}


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_freight_rate(
    mode: str,
    origin_country: str,
    weight_kg: float = 0,
    cbm: float = 0,
) -> dict:
    """
    Get reference freight rate and estimated cost.

    Returns:
        {rate_per_kg, rate_per_cbm, estimated_cost, transit_days, notes}
    """
    region = _get_region(origin_country)
    mode = mode.lower()

    rate_db = {"sea": _SEA_RATES, "air": _AIR_RATES, "land": _LAND_RATES}
    rates = rate_db.get(mode, _SEA_RATES)
    rate = rates.get(region)

    if not rate:
        # Fallback to east_asia
        rate = rates.get("east_asia", list(rates.values())[0])

    # Calculate estimated cost
    cost_by_kg = weight_kg * rate.rate_per_kg if weight_kg > 0 else 0
    cost_by_cbm = cbm * rate.rate_per_cbm if cbm > 0 and rate.rate_per_cbm > 0 else 0

    if mode == "sea" and cbm > 0:
        estimated = max(cost_by_kg, cost_by_cbm, rate.min_charge)
    else:
        estimated = max(cost_by_kg, rate.min_charge)

    return {
        "mode": mode,
        "origin_country": origin_country.upper(),
        "origin_region": region,
        "rate_per_kg": rate.rate_per_kg,
        "rate_per_cbm": rate.rate_per_cbm,
        "min_charge": rate.min_charge,
        "estimated_cost_usd": round(estimated, 2),
        "weight_kg": weight_kg,
        "cbm": cbm,
        "transit_days": f"{rate.transit_days_min}-{rate.transit_days_max}",
        "notes": rate.notes,
        "disclaimer": "Reference rate — actual varies by carrier/season/volume"
    }


def get_insurance_rate(
    goods_value: float,
    freight_cost: float = 0,
    cargo_type: str = "general",
) -> dict:
    """
    Calculate insurance estimate.
    Thai Customs standard: insurable value = 110% × (goods + freight)
    """
    rate = INSURANCE_RATES.get(cargo_type, INSURANCE_RATES["general"])
    insurable_value = (goods_value + freight_cost) * 1.10
    premium = insurable_value * rate

    return {
        "cargo_type": cargo_type,
        "insurance_rate_pct": round(rate * 100, 3),
        "goods_value": round(goods_value, 2),
        "freight_cost": round(freight_cost, 2),
        "insurable_value_110pct": round(insurable_value, 2),
        "estimated_premium_usd": round(premium, 2),
        "notes": "110% cover per Thai Customs valuation rules"
    }


def get_local_charges(
    mode: str = "sea",
    port: str = "laem_chabang",
) -> dict:
    """Get local charges breakdown for a Thai port."""
    port_info = THAI_PORTS.get(port)
    if not port_info:
        port_info = THAI_PORTS["laem_chabang"]

    total = (port_info.thc_20ft + port_info.cfs_per_cbm * 10 +  # assume 10 CBM avg
             port_info.do_fee + port_info.customs_clearance +
             port_info.inland_to_bkk + port_info.wharfage * 5)  # assume 5 tons

    return {
        "port_code": port_info.port_code,
        "port_name": port_info.port_name,
        "charges": {
            "thc_20ft": port_info.thc_20ft,
            "thc_40ft": port_info.thc_40ft,
            "cfs_per_cbm": port_info.cfs_per_cbm,
            "do_fee": port_info.do_fee,
            "customs_clearance": port_info.customs_clearance,
            "inland_to_bangkok": port_info.inland_to_bkk,
            "wharfage_per_ton": port_info.wharfage,
        },
        "estimated_total_usd": round(total, 2),
        "notes": port_info.notes,
        "disclaimer": "Estimates based on market averages — actual varies by forwarder"
    }


def get_all_ports() -> list[dict]:
    """List all Thai ports with charges."""
    return [
        {
            "port_id": pid,
            "port_code": p.port_code,
            "port_name": p.port_name,
            "notes": p.notes,
        }
        for pid, p in THAI_PORTS.items()
    ]


def get_transit_time(mode: str, origin_country: str) -> dict:
    """Get estimated transit time."""
    region = _get_region(origin_country)
    mode = mode.lower()

    rate_db = {"sea": _SEA_RATES, "air": _AIR_RATES, "land": _LAND_RATES}
    rates = rate_db.get(mode, _SEA_RATES)
    rate = rates.get(region)

    if not rate:
        rate = rates.get("east_asia", list(rates.values())[0])

    return {
        "mode": mode,
        "origin_country": origin_country.upper(),
        "origin_region": region,
        "transit_days_min": rate.transit_days_min,
        "transit_days_max": rate.transit_days_max,
        "notes": rate.notes,
    }
