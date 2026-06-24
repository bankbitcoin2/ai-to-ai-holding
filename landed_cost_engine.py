"""
landed_cost_engine.py — Phase 21: Landed Cost Calculator
AI TO AI HOLDING — Customs Intelligence Division

คำนวณต้นทุนรวมสินค้านำเข้าถึงหน้าโรงงาน (Total Landed Cost)
ครอบคลุม: Incoterms 2020, Freight, Insurance, Duty, VAT 7%, Local Charges

Input:
  - product_value (CIF/FOB/EXW value)
  - incoterm (EXW/FOB/FCA/CFR/CIF/CIP/DAP/DDP etc.)
  - hs_code → duty rate (from tax_engine)
  - origin_country → FTA rate (from fta_engine)
  - freight_cost (optional — auto-estimate if missing)
  - insurance_cost (optional — auto-estimate if missing)
  - transport_mode: sea/air/land
  - currency: source currency (convert via currency_service)

Output: LandedCostResult with full breakdown per item/per shipment

Usage:
    result = calculate_landed_cost(
        product_value=10000, currency="USD", incoterm="FOB",
        hs_code="030617", origin_country="VN", transport_mode="sea",
        item_count=500, weight_kg=200
    )
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone


# ══════════════════════════════════════════════════════════════════════════════
# INCOTERMS 2020 — Responsibility Matrix
# ══════════════════════════════════════════════════════════════════════════════

# Buyer responsibility flags per Incoterm
# True = buyer pays, False = seller pays (included in price)
@dataclass
class IncotermRule:
    """What the BUYER must pay on top of the quoted price."""
    code: str
    name: str
    group: str                  # E, F, C, D
    buyer_pays_export: bool     # Export clearance + export duty
    buyer_pays_freight: bool    # Main carriage (international)
    buyer_pays_insurance: bool  # Cargo insurance
    buyer_pays_import_duty: bool  # Import duty + VAT
    buyer_pays_delivery: bool   # Delivery from port to warehouse
    any_mode: bool              # True = any mode, False = sea/inland only
    description_th: str


INCOTERMS: dict[str, IncotermRule] = {
    # Group E — Departure
    "EXW": IncotermRule(
        code="EXW", name="Ex Works", group="E",
        buyer_pays_export=True, buyer_pays_freight=True,
        buyer_pays_insurance=True, buyer_pays_import_duty=True,
        buyer_pays_delivery=True, any_mode=True,
        description_th="ผู้ซื้อรับผิดชอบทุกอย่างตั้งแต่หน้าโรงงานผู้ขาย"
    ),
    # Group F — Main Carriage Unpaid
    "FCA": IncotermRule(
        code="FCA", name="Free Carrier", group="F",
        buyer_pays_export=False, buyer_pays_freight=True,
        buyer_pays_insurance=True, buyer_pays_import_duty=True,
        buyer_pays_delivery=True, any_mode=True,
        description_th="ผู้ขายส่งถึงผู้รับขนส่ง ผู้ซื้อจ่ายค่าขนส่งหลัก"
    ),
    "FAS": IncotermRule(
        code="FAS", name="Free Alongside Ship", group="F",
        buyer_pays_export=False, buyer_pays_freight=True,
        buyer_pays_insurance=True, buyer_pays_import_duty=True,
        buyer_pays_delivery=True, any_mode=False,
        description_th="ผู้ขายวางสินค้าข้างเรือ ผู้ซื้อจ่ายค่าขนส่งหลัก"
    ),
    "FOB": IncotermRule(
        code="FOB", name="Free On Board", group="F",
        buyer_pays_export=False, buyer_pays_freight=True,
        buyer_pays_insurance=True, buyer_pays_import_duty=True,
        buyer_pays_delivery=True, any_mode=False,
        description_th="ผู้ขายส่งขึ้นเรือ ผู้ซื้อจ่ายค่าขนส่ง+ประกัน"
    ),
    # Group C — Main Carriage Paid
    "CFR": IncotermRule(
        code="CFR", name="Cost and Freight", group="C",
        buyer_pays_export=False, buyer_pays_freight=False,
        buyer_pays_insurance=True, buyer_pays_import_duty=True,
        buyer_pays_delivery=True, any_mode=False,
        description_th="ผู้ขายจ่ายค่าขนส่งถึงท่าปลายทาง ผู้ซื้อจ่ายประกัน"
    ),
    "CIF": IncotermRule(
        code="CIF", name="Cost, Insurance & Freight", group="C",
        buyer_pays_export=False, buyer_pays_freight=False,
        buyer_pays_insurance=False, buyer_pays_import_duty=True,
        buyer_pays_delivery=True, any_mode=False,
        description_th="ผู้ขายจ่ายค่าขนส่ง+ประกันถึงท่าปลายทาง"
    ),
    "CPT": IncotermRule(
        code="CPT", name="Carriage Paid To", group="C",
        buyer_pays_export=False, buyer_pays_freight=False,
        buyer_pays_insurance=True, buyer_pays_import_duty=True,
        buyer_pays_delivery=True, any_mode=True,
        description_th="ผู้ขายจ่ายค่าขนส่งถึงจุดปลายทาง (ทุก mode)"
    ),
    "CIP": IncotermRule(
        code="CIP", name="Carriage and Insurance Paid To", group="C",
        buyer_pays_export=False, buyer_pays_freight=False,
        buyer_pays_insurance=False, buyer_pays_import_duty=True,
        buyer_pays_delivery=True, any_mode=True,
        description_th="ผู้ขายจ่ายค่าขนส่ง+ประกันถึงจุดปลายทาง (ทุก mode)"
    ),
    # Group D — Arrival
    "DAP": IncotermRule(
        code="DAP", name="Delivered At Place", group="D",
        buyer_pays_export=False, buyer_pays_freight=False,
        buyer_pays_insurance=False, buyer_pays_import_duty=True,
        buyer_pays_delivery=False, any_mode=True,
        description_th="ผู้ขายส่งถึงจุดปลายทาง ผู้ซื้อจ่ายภาษีนำเข้า"
    ),
    "DPU": IncotermRule(
        code="DPU", name="Delivered at Place Unloaded", group="D",
        buyer_pays_export=False, buyer_pays_freight=False,
        buyer_pays_insurance=False, buyer_pays_import_duty=True,
        buyer_pays_delivery=False, any_mode=True,
        description_th="ผู้ขายส่ง+ขนถ่ายที่ปลายทาง ผู้ซื้อจ่ายภาษีนำเข้า"
    ),
    "DDP": IncotermRule(
        code="DDP", name="Delivered Duty Paid", group="D",
        buyer_pays_export=False, buyer_pays_freight=False,
        buyer_pays_insurance=False, buyer_pays_import_duty=False,
        buyer_pays_delivery=False, any_mode=True,
        description_th="ผู้ขายรับผิดชอบทุกอย่างรวมภาษี — ผู้ซื้อรับของอย่างเดียว"
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
# DEFAULT RATES — Local Charges (Thailand)
# ══════════════════════════════════════════════════════════════════════════════

# Thai VAT rate
THAI_VAT_RATE = 0.07  # 7%

# Default insurance rate (% of CIF value) — if not provided
DEFAULT_INSURANCE_RATE = 0.003  # 0.3% of goods value (market standard)

# Export clearance estimate (USD)
DEFAULT_EXPORT_CLEARANCE_USD = 50.0

# Local charges at Thai port/airport (USD estimates)
# These are typical ranges — actual varies by forwarder
@dataclass
class LocalCharges:
    """Local charges at destination (Thailand)."""
    thc: float = 0.0          # Terminal Handling Charge
    cfs: float = 0.0          # Container Freight Station fee
    do_fee: float = 0.0       # Delivery Order fee
    customs_clearance: float = 0.0  # Customs broker fee
    inland_transport: float = 0.0   # Port/airport to warehouse
    other: float = 0.0        # Miscellaneous

    @property
    def total(self) -> float:
        return (self.thc + self.cfs + self.do_fee +
                self.customs_clearance + self.inland_transport + self.other)


# Default local charges by transport mode (USD)
DEFAULT_LOCAL_CHARGES = {
    "sea": LocalCharges(
        thc=120.0,              # THC per TEU ~$100-150
        cfs=50.0,               # CFS unstuffing ~$30-80
        do_fee=30.0,            # D/O fee ~$20-40
        customs_clearance=80.0, # Broker fee ~$50-120
        inland_transport=150.0, # Laem Chabang → Bangkok ~$100-200
        other=20.0              # Doc fee, port surcharge etc.
    ),
    "air": LocalCharges(
        thc=0.0,
        cfs=0.0,
        do_fee=20.0,            # AWB release fee
        customs_clearance=80.0, # Broker fee
        inland_transport=80.0,  # Suvarnabhumi → warehouse
        other=30.0              # Terminal fee, handling
    ),
    "land": LocalCharges(
        thc=0.0,
        cfs=0.0,
        do_fee=15.0,
        customs_clearance=60.0, # Broker fee (border)
        inland_transport=100.0, # Border → warehouse
        other=15.0
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
# RESULT DATACLASS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class LandedCostResult:
    """Full breakdown of landed cost."""
    # Input echo
    product_value_usd: float
    incoterm: str
    hs_code: str
    origin_country: str
    transport_mode: str
    item_count: int
    weight_kg: float

    # Cost components (all in USD)
    export_clearance: float = 0.0
    freight_cost: float = 0.0
    insurance_cost: float = 0.0
    cif_value: float = 0.0          # CIF value (base for duty)
    duty_rate_pct: float = 0.0      # Applied duty rate %
    fta_applied: Optional[str] = None  # FTA name if applied
    duty_amount: float = 0.0        # Import duty USD
    vat_base: float = 0.0           # CIF + duty (base for VAT)
    vat_amount: float = 0.0         # VAT 7% USD
    local_charges: float = 0.0      # Total local charges
    local_charges_detail: Optional[dict] = None

    # Totals
    total_landed_cost: float = 0.0
    cost_per_item: float = 0.0
    cost_per_kg: float = 0.0

    # Metadata
    duty_savings_vs_mfn: float = 0.0  # FTA savings
    effective_tax_rate: float = 0.0    # Total tax / product value
    currency_rate: Optional[float] = None  # If converted from other currency
    calculated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "input": {
                "product_value_usd": round(self.product_value_usd, 2),
                "incoterm": self.incoterm,
                "hs_code": self.hs_code,
                "origin_country": self.origin_country,
                "transport_mode": self.transport_mode,
                "item_count": self.item_count,
                "weight_kg": round(self.weight_kg, 2),
            },
            "cost_breakdown": {
                "export_clearance": round(self.export_clearance, 2),
                "freight": round(self.freight_cost, 2),
                "insurance": round(self.insurance_cost, 2),
                "cif_value": round(self.cif_value, 2),
                "duty_rate_pct": round(self.duty_rate_pct, 2),
                "fta_applied": self.fta_applied,
                "duty_amount": round(self.duty_amount, 2),
                "vat_base": round(self.vat_base, 2),
                "vat_amount": round(self.vat_amount, 2),
                "local_charges": round(self.local_charges, 2),
                "local_charges_detail": self.local_charges_detail,
            },
            "totals": {
                "total_landed_cost_usd": round(self.total_landed_cost, 2),
                "cost_per_item_usd": round(self.cost_per_item, 4),
                "cost_per_kg_usd": round(self.cost_per_kg, 4) if self.weight_kg > 0 else None,
            },
            "analysis": {
                "duty_savings_vs_mfn_usd": round(self.duty_savings_vs_mfn, 2),
                "effective_tax_rate_pct": round(self.effective_tax_rate, 2),
                "currency_rate": self.currency_rate,
            },
            "calculated_at": self.calculated_at,
        }


# ══════════════════════════════════════════════════════════════════════════════
# CORE CALCULATION
# ══════════════════════════════════════════════════════════════════════════════

def get_incoterm_info(code: str) -> Optional[IncotermRule]:
    """Get Incoterm rule by code."""
    return INCOTERMS.get(code.upper())


def get_all_incoterms() -> list[dict]:
    """List all supported Incoterms with buyer responsibility."""
    result = []
    for code, rule in INCOTERMS.items():
        result.append({
            "code": rule.code,
            "name": rule.name,
            "group": rule.group,
            "any_mode": rule.any_mode,
            "description_th": rule.description_th,
            "buyer_pays": {
                "export_clearance": rule.buyer_pays_export,
                "freight": rule.buyer_pays_freight,
                "insurance": rule.buyer_pays_insurance,
                "import_duty": rule.buyer_pays_import_duty,
                "delivery_to_warehouse": rule.buyer_pays_delivery,
            }
        })
    return result


def estimate_insurance(goods_value: float, freight: float) -> float:
    """Estimate cargo insurance cost.
    Standard: 110% of (goods + freight) × insurance rate
    กรมศุลกากรไทยใช้ CIF + 1% ในกรณีไม่มีเบี้ยประกัน
    """
    insurable_value = (goods_value + freight) * 1.10  # 110% cover
    return insurable_value * DEFAULT_INSURANCE_RATE


def calculate_cif_value(
    product_value: float,
    incoterm: str,
    freight: float,
    insurance: float,
    export_clearance: float = 0.0,
) -> tuple[float, float, float, float]:
    """
    Convert any Incoterm price to CIF value.
    Thai Customs assesses duty on CIF value.

    Returns: (cif_value, buyer_freight, buyer_insurance, buyer_export)
    """
    rule = INCOTERMS.get(incoterm.upper())
    if not rule:
        raise ValueError(f"Unknown Incoterm: {incoterm}")

    buyer_export = export_clearance if rule.buyer_pays_export else 0.0
    buyer_freight = freight if rule.buyer_pays_freight else 0.0
    buyer_insurance = insurance if rule.buyer_pays_insurance else 0.0

    # CIF = product price + any costs buyer must add to reach CIF
    # For EXW: CIF = price + export + freight + insurance
    # For FOB: CIF = price + freight + insurance
    # For CFR: CIF = price + insurance
    # For CIF: CIF = price (already includes freight+insurance)
    # For DAP/DDP: CIF = price - delivery (but price already > CIF)

    if incoterm.upper() in ("DAP", "DPU", "DDP"):
        # D-group: price includes freight+insurance+delivery
        # CIF is LESS than quoted price (subtract delivery portion)
        # Approximation: CIF ≈ product_value - local delivery
        # For duty calculation, Thai customs still requires CIF declaration
        cif = product_value  # Conservative: use full value
    else:
        cif = product_value + buyer_export + buyer_freight + buyer_insurance

    return cif, buyer_freight, buyer_insurance, buyer_export


def calculate_landed_cost(
    product_value: float,
    incoterm: str = "FOB",
    hs_code: str = "",
    origin_country: str = "",
    transport_mode: str = "sea",
    item_count: int = 1,
    weight_kg: float = 0.0,
    # Optional overrides
    freight_cost: Optional[float] = None,
    insurance_cost: Optional[float] = None,
    duty_rate: Optional[float] = None,
    fta_name: Optional[str] = None,
    mfn_rate: Optional[float] = None,
    local_charges_override: Optional[LocalCharges] = None,
    currency: str = "USD",
    currency_rate: Optional[float] = None,
) -> LandedCostResult:
    """
    Calculate total landed cost for importing goods to Thailand.

    Args:
        product_value: Goods value in source currency
        incoterm: Incoterms 2020 code
        hs_code: HS code (for duty lookup — caller provides rate)
        origin_country: ISO country code
        transport_mode: sea/air/land
        item_count: Number of items
        weight_kg: Total shipment weight
        freight_cost: Override freight (USD). None = use reference rate
        insurance_cost: Override insurance (USD). None = auto-estimate
        duty_rate: Applied duty rate % (caller resolves MFN vs FTA)
        fta_name: FTA agreement name if applicable
        mfn_rate: MFN rate for savings comparison
        local_charges_override: Override default local charges
        currency: Source currency of product_value
        currency_rate: Rate to USD (if currency != USD)
    """
    rule = INCOTERMS.get(incoterm.upper())
    if not rule:
        raise ValueError(f"Unknown Incoterm: {incoterm}")

    mode = transport_mode.lower()
    if mode not in ("sea", "air", "land"):
        mode = "sea"

    # ── Step 1: Convert to USD ──
    value_usd = product_value
    if currency.upper() != "USD" and currency_rate and currency_rate > 0:
        value_usd = product_value / currency_rate  # currency_rate = 1 USD in source currency

    # ── Step 2: Estimate freight if not provided ──
    # Import from freight_rate_service (or use simple estimate)
    if freight_cost is not None:
        freight = freight_cost
    else:
        freight = _estimate_freight(value_usd, weight_kg, mode)

    # ── Step 3: Estimate insurance if not provided ──
    if insurance_cost is not None:
        insurance = insurance_cost
    else:
        insurance = estimate_insurance(value_usd, freight)

    # ── Step 4: Calculate CIF value ──
    export_clr = DEFAULT_EXPORT_CLEARANCE_USD if rule.buyer_pays_export else 0.0
    cif, buyer_freight, buyer_insurance, buyer_export = calculate_cif_value(
        value_usd, incoterm, freight, insurance, export_clr
    )

    # ── Step 5: Import Duty ──
    applied_duty_rate = duty_rate if duty_rate is not None else 0.0
    if rule.buyer_pays_import_duty:
        duty_amount = cif * (applied_duty_rate / 100.0)
    else:
        duty_amount = 0.0  # DDP — seller pays

    # ── Step 6: VAT (7% on CIF + Duty) ──
    if rule.buyer_pays_import_duty:
        vat_base = cif + duty_amount
        vat_amount = vat_base * THAI_VAT_RATE
    else:
        vat_base = 0.0
        vat_amount = 0.0  # DDP

    # ── Step 7: Local Charges ──
    if local_charges_override:
        lc = local_charges_override
    else:
        lc = DEFAULT_LOCAL_CHARGES.get(mode, DEFAULT_LOCAL_CHARGES["sea"])

    local_total = lc.total if rule.buyer_pays_delivery else 0.0

    local_detail = {
        "thc": round(lc.thc, 2),
        "cfs": round(lc.cfs, 2),
        "do_fee": round(lc.do_fee, 2),
        "customs_clearance": round(lc.customs_clearance, 2),
        "inland_transport": round(lc.inland_transport, 2),
        "other": round(lc.other, 2),
    }

    # ── Step 8: Total Landed Cost ──
    total = (
        value_usd          # Product cost
        + buyer_export     # Export clearance (if buyer pays)
        + buyer_freight    # Freight (if buyer pays)
        + buyer_insurance  # Insurance (if buyer pays)
        + duty_amount      # Import duty
        + vat_amount       # VAT 7%
        + local_total      # Local charges
    )

    # ── Step 9: FTA Savings ──
    savings = 0.0
    if mfn_rate is not None and duty_rate is not None and mfn_rate > duty_rate:
        savings = cif * ((mfn_rate - duty_rate) / 100.0)

    # ── Step 10: Effective tax rate ──
    effective_rate = 0.0
    if value_usd > 0:
        total_tax = duty_amount + vat_amount
        effective_rate = (total_tax / value_usd) * 100.0

    return LandedCostResult(
        product_value_usd=value_usd,
        incoterm=incoterm.upper(),
        hs_code=hs_code,
        origin_country=origin_country.upper(),
        transport_mode=mode,
        item_count=item_count,
        weight_kg=weight_kg,
        export_clearance=buyer_export,
        freight_cost=buyer_freight,
        insurance_cost=buyer_insurance,
        cif_value=cif,
        duty_rate_pct=applied_duty_rate,
        fta_applied=fta_name,
        duty_amount=duty_amount,
        vat_base=vat_base,
        vat_amount=vat_amount,
        local_charges=local_total,
        local_charges_detail=local_detail,
        total_landed_cost=total,
        cost_per_item=total / item_count if item_count > 0 else total,
        cost_per_kg=total / weight_kg if weight_kg > 0 else 0.0,
        duty_savings_vs_mfn=savings,
        effective_tax_rate=effective_rate,
        currency_rate=currency_rate,
        calculated_at=datetime.now(timezone.utc).isoformat(),
    )


# ══════════════════════════════════════════════════════════════════════════════
# FREIGHT ESTIMATION (Simple — Phase 23 will add Freight Auditor)
# ══════════════════════════════════════════════════════════════════════════════

def _estimate_freight(value_usd: float, weight_kg: float, mode: str) -> float:
    """
    Simple freight estimate when actual cost not provided.
    Phase 23 (Freight Rate Auditor) จะมี rate database จริง

    Current logic:
    - Sea: ~$50/CBM or $0.10/kg (whichever higher), min $200
    - Air: ~$3.50/kg, min $150
    - Land: ~$0.15/kg, min $100
    """
    if mode == "sea":
        # Rough: $0.10/kg or 2% of value, min $200
        by_weight = weight_kg * 0.10 if weight_kg > 0 else 0
        by_value = value_usd * 0.02
        return max(by_weight, by_value, 200.0)

    elif mode == "air":
        # Air freight: ~$3.50/kg chargeable weight
        by_weight = weight_kg * 3.50 if weight_kg > 0 else 0
        return max(by_weight, 150.0)

    else:  # land
        by_weight = weight_kg * 0.15 if weight_kg > 0 else 0
        return max(by_weight, 100.0)


# ══════════════════════════════════════════════════════════════════════════════
# COMPARISON TOOL — Compare Incoterms
# ══════════════════════════════════════════════════════════════════════════════

def compare_incoterms(
    product_values: dict[str, float],
    hs_code: str = "",
    origin_country: str = "",
    transport_mode: str = "sea",
    item_count: int = 1,
    weight_kg: float = 0.0,
    duty_rate: float = 0.0,
    mfn_rate: Optional[float] = None,
    freight_cost: Optional[float] = None,
    insurance_cost: Optional[float] = None,
) -> list[dict]:
    """
    Compare landed cost across different Incoterm quotes.

    Args:
        product_values: {"FOB": 10000, "CIF": 11500, "EXW": 9500}

    Returns: sorted list by total_landed_cost (cheapest first)
    """
    results = []
    for incoterm, value in product_values.items():
        if incoterm.upper() not in INCOTERMS:
            continue
        try:
            result = calculate_landed_cost(
                product_value=value,
                incoterm=incoterm,
                hs_code=hs_code,
                origin_country=origin_country,
                transport_mode=transport_mode,
                item_count=item_count,
                weight_kg=weight_kg,
                duty_rate=duty_rate,
                mfn_rate=mfn_rate,
                freight_cost=freight_cost,
                insurance_cost=insurance_cost,
            )
            d = result.to_dict()
            d["quoted_incoterm"] = incoterm.upper()
            d["quoted_price_usd"] = round(value, 2)
            results.append(d)
        except Exception:
            continue

    results.sort(key=lambda x: x["totals"]["total_landed_cost_usd"])

    # Add ranking
    for i, r in enumerate(results):
        r["rank"] = i + 1
        if i == 0:
            r["recommendation"] = "CHEAPEST"
        else:
            diff = r["totals"]["total_landed_cost_usd"] - results[0]["totals"]["total_landed_cost_usd"]
            r["extra_cost_vs_cheapest"] = round(diff, 2)

    return results
