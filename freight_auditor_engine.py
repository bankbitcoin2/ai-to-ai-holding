"""
freight_auditor_engine.py — Phase 23: Freight Rate Auditor
AI TO AI HOLDING — Customs Intelligence Division

ตรวจบิลค่าขนส่งว่าแพงเกินจริงหรือไม่:
  - แกะรายการค่าใช้จ่ายในบิลชิปปิ้ง (THC, CFS, D/O, BAF, clearance fee ฯลฯ)
  - เทียบแต่ละรายการกับอัตราตลาด (market rate)
  - Flag รายการที่แพงเกิน threshold
  - สรุป savings ที่ประหยัดได้ถ้าเจรจาใหม่

ขายเป็น Premium feature สำหรับ Procurement / CFO
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import math


# ── Configuration ────────────────────────────────────────────────────────────

OVERCHARGE_THRESHOLD = 0.20       # > 20% เหนือ market rate = flag
SEVERE_OVERCHARGE = 0.50          # > 50% = RED flag
MIN_CHARGE_USD = 5.0              # ไม่ flag รายการต่ำกว่า $5


# ── Charge Categories ────────────────────────────────────────────────────────
# รายการค่าใช้จ่ายมาตรฐานในบิลค่าขนส่ง

CHARGE_CATEGORIES = {
    # ── Sea Freight Charges ──
    "ocean_freight":    {"name": "Ocean Freight / ค่าระวางเรือ", "mode": "sea"},
    "thc_origin":       {"name": "THC Origin / ค่ายกตู้ต้นทาง", "mode": "sea"},
    "thc_destination":  {"name": "THC Destination / ค่ายกตู้ปลายทาง", "mode": "sea"},
    "cfs_charge":       {"name": "CFS Charge / ค่าจัดตู้ (LCL)", "mode": "sea"},
    "seal_fee":         {"name": "Seal Fee / ค่าซีลตู้", "mode": "sea"},
    "baf":              {"name": "BAF / Bunker Adjustment Factor", "mode": "sea"},
    "caf":              {"name": "CAF / Currency Adjustment Factor", "mode": "sea"},
    "pss":              {"name": "PSS / Peak Season Surcharge", "mode": "sea"},
    "ams_fee":          {"name": "AMS / Advance Manifest System", "mode": "sea"},

    # ── Destination Charges (Sea) ──
    "do_fee":           {"name": "D/O Fee / ค่าใบสั่งปล่อย", "mode": "sea"},
    "demurrage":        {"name": "Demurrage / ค่าคอนเทนเนอร์เกินกำหนด", "mode": "sea"},
    "detention":        {"name": "Detention / ค่าเก็บตู้เกินกำหนด", "mode": "sea"},
    "wharfage":         {"name": "Wharfage / ค่าท่าเรือ", "mode": "sea"},
    "lift_on_off":      {"name": "Lift On/Off / ค่ายกตู้ขึ้น-ลง", "mode": "sea"},

    # ── Air Freight Charges ──
    "air_freight":      {"name": "Air Freight / ค่าระวางเครื่องบิน", "mode": "air"},
    "fuel_surcharge":   {"name": "Fuel Surcharge / ค่าน้ำมันเพิ่มเติม", "mode": "air"},
    "security_fee":     {"name": "Security Fee / ค่าตรวจสอบความปลอดภัย", "mode": "air"},
    "awb_fee":          {"name": "AWB Fee / ค่าใบตราส่งสินค้าทางอากาศ", "mode": "air"},
    "terminal_handling": {"name": "Terminal Handling / ค่าจัดการที่สนามบิน", "mode": "air"},

    # ── Common Charges ──
    "customs_clearance": {"name": "Customs Clearance / ค่าดำเนินพิธีการศุลกากร", "mode": "all"},
    "customs_inspection": {"name": "Customs Inspection / ค่าตรวจสินค้า", "mode": "all"},
    "documentation":     {"name": "Documentation / ค่าเอกสาร", "mode": "all"},
    "insurance":         {"name": "Insurance / ค่าประกันสินค้า", "mode": "all"},
    "trucking":          {"name": "Trucking / ค่าขนส่งภายใน", "mode": "all"},
    "warehouse":         {"name": "Warehouse / ค่าฝากสินค้า", "mode": "all"},
    "handling_fee":      {"name": "Handling Fee / ค่าจัดการ", "mode": "all"},
    "agency_fee":        {"name": "Agency Fee / ค่าตัวแทน", "mode": "all"},
    "vat":               {"name": "VAT / ภาษีมูลค่าเพิ่ม", "mode": "all"},
    "other":             {"name": "Other / อื่นๆ", "mode": "all"},
}


# ── Market Reference Rates ───────────────────────────────────────────────────
# อัตราตลาดอ้างอิง (USD) — ใช้เป็นฐานเปรียบเทียบ
# Source: Freight forwarder rate schedules (averaged), 2025-2026

# Per container rates (20ft / 40ft)
MARKET_RATES_SEA: dict[str, dict] = {
    "thc_origin": {
        "asean": {"min": 50, "typical": 80, "max": 120},
        "east_asia": {"min": 80, "typical": 120, "max": 180},
        "south_asia": {"min": 60, "typical": 100, "max": 150},
        "europe": {"min": 100, "typical": 150, "max": 220},
        "americas": {"min": 120, "typical": 180, "max": 250},
        "default": {"min": 80, "typical": 130, "max": 200},
    },
    "thc_destination": {
        "default": {"min": 80, "typical": 120, "max": 180},
    },
    "cfs_charge": {
        "default": {"min": 30, "typical": 50, "max": 80},
    },
    "seal_fee": {
        "default": {"min": 10, "typical": 15, "max": 25},
    },
    "baf": {
        "default": {"min": 100, "typical": 200, "max": 400},
    },
    "caf": {
        "default": {"min": 0, "typical": 30, "max": 80},
    },
    "pss": {
        "default": {"min": 0, "typical": 150, "max": 400},
    },
    "ams_fee": {
        "default": {"min": 25, "typical": 35, "max": 50},
    },
    "do_fee": {
        "default": {"min": 30, "typical": 50, "max": 80},
    },
    "demurrage": {
        "default": {"min": 50, "typical": 100, "max": 200},  # per day
    },
    "detention": {
        "default": {"min": 40, "typical": 80, "max": 150},   # per day
    },
    "wharfage": {
        "default": {"min": 20, "typical": 40, "max": 70},
    },
    "lift_on_off": {
        "default": {"min": 30, "typical": 50, "max": 80},
    },
}

MARKET_RATES_AIR: dict[str, dict] = {
    "fuel_surcharge": {
        "default": {"min": 0.3, "typical": 0.5, "max": 1.0},  # per kg
    },
    "security_fee": {
        "default": {"min": 0.03, "typical": 0.06, "max": 0.10},  # per kg
    },
    "awb_fee": {
        "default": {"min": 20, "typical": 35, "max": 50},
    },
    "terminal_handling": {
        "default": {"min": 0.05, "typical": 0.10, "max": 0.20},  # per kg
    },
}

MARKET_RATES_COMMON: dict[str, dict] = {
    "customs_clearance": {
        "default": {"min": 50, "typical": 100, "max": 200},
    },
    "customs_inspection": {
        "default": {"min": 50, "typical": 80, "max": 150},
    },
    "documentation": {
        "default": {"min": 20, "typical": 40, "max": 80},
    },
    "handling_fee": {
        "default": {"min": 30, "typical": 50, "max": 100},
    },
    "agency_fee": {
        "default": {"min": 50, "typical": 100, "max": 200},
    },
}


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class ChargeLineItem:
    """รายการค่าใช้จ่ายหนึ่งบรรทัดในบิล"""
    charge_type: str           # key จาก CHARGE_CATEGORIES
    description: str           # ชื่อตามบิลจริง
    amount_usd: float          # จำนวนเงิน (USD)
    currency: str = "USD"      # สกุลเงินต้นฉบับ
    quantity: int = 1          # จำนวน (เช่น days for demurrage)
    unit: str = ""             # per container / per kg / per shipment
    notes: str = ""


@dataclass
class AuditResult:
    """ผลตรวจรายการค่าใช้จ่ายหนึ่งบรรทัด"""
    charge_type: str
    description: str
    charged_amount: float
    market_typical: float
    market_max: float
    deviation_pct: float       # % เหนือ typical (negative = ต่ำกว่า)
    status: str                # OK / WARNING / OVERCHARGE / SEVERE
    savings_potential: float   # ประหยัดได้ถ้าเจรจาเท่า typical
    recommendation: str

    def to_dict(self) -> dict:
        return {
            "charge_type": self.charge_type,
            "description": self.description,
            "charged_amount": round(self.charged_amount, 2),
            "market_rate": {
                "typical": round(self.market_typical, 2),
                "max": round(self.market_max, 2),
            },
            "deviation_pct": round(self.deviation_pct, 1),
            "status": self.status,
            "savings_potential_usd": round(self.savings_potential, 2),
            "recommendation": self.recommendation,
        }


@dataclass
class FreightAuditReport:
    """รายงานผลตรวจบิลค่าขนส่งทั้งฉบับ"""
    shipment_mode: str
    origin_region: str
    total_charged: float
    total_market_typical: float
    total_savings_potential: float
    overall_status: str         # PASS / WARNING / OVERCHARGED
    overcharge_count: int
    line_items: list[AuditResult] = field(default_factory=list)
    audit_timestamp: str = ""
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "shipment_mode": self.shipment_mode,
            "origin_region": self.origin_region,
            "total_charged_usd": round(self.total_charged, 2),
            "total_market_typical_usd": round(self.total_market_typical, 2),
            "total_savings_potential_usd": round(self.total_savings_potential, 2),
            "savings_pct": round(
                (self.total_savings_potential / self.total_charged * 100)
                if self.total_charged > 0 else 0, 1
            ),
            "overall_status": self.overall_status,
            "overcharge_count": self.overcharge_count,
            "line_items": [li.to_dict() for li in self.line_items],
            "audit_timestamp": self.audit_timestamp,
            "summary": self.summary,
        }


# ── Core Audit Function ─────────────────────────────────────────────────────

def audit_freight_bill(
    charges: list[ChargeLineItem],
    shipment_mode: str = "sea",
    origin_region: str = "default",
    weight_kg: float = 0,
) -> FreightAuditReport:
    """
    ตรวจบิลค่าขนส่ง — เทียบทุกรายการกับอัตราตลาด

    Args:
        charges: รายการค่าใช้จ่ายจากบิล
        shipment_mode: sea / air / land
        origin_region: asean / east_asia / south_asia / europe / americas / oceania
        weight_kg: น้ำหนักสินค้า (สำหรับ per-kg rates)

    Returns:
        FreightAuditReport พร้อมผลตรวจแต่ละรายการ
    """
    results: list[AuditResult] = []
    total_charged = 0.0
    total_typical = 0.0
    total_savings = 0.0
    overcharge_count = 0

    for charge in charges:
        amount = charge.amount_usd * charge.quantity
        total_charged += amount

        # หา market rate
        market = _get_market_rate(charge.charge_type, shipment_mode, origin_region)

        if not market:
            # ไม่มีข้อมูลอ้างอิง
            results.append(AuditResult(
                charge_type=charge.charge_type,
                description=charge.description,
                charged_amount=amount,
                market_typical=0,
                market_max=0,
                deviation_pct=0,
                status="NO_DATA",
                savings_potential=0,
                recommendation="ไม่มีอัตราอ้างอิง — ควรเปรียบเทียบกับใบเสนอราคาจากผู้ให้บริการอื่น",
            ))
            continue

        typical = market["typical"]
        max_rate = market["max"]

        # ปรับ per-kg rates ตามน้ำหนัก
        if charge.charge_type in ("fuel_surcharge", "security_fee", "terminal_handling") and weight_kg > 0:
            typical *= weight_kg
            max_rate *= weight_kg

        total_typical += typical

        # คำนวณ deviation
        if typical > 0:
            deviation = (amount - typical) / typical
        else:
            deviation = 0

        deviation_pct = deviation * 100

        # Determine status
        savings = max(0, amount - typical)
        status = "OK"
        recommendation = "ราคาอยู่ในเกณฑ์ปกติ"

        if amount < MIN_CHARGE_USD:
            status = "OK"
            recommendation = "จำนวนเงินน้อย ไม่จำเป็นต้องเจรจา"
            savings = 0

        elif deviation > SEVERE_OVERCHARGE:
            status = "SEVERE"
            overcharge_count += 1
            recommendation = (
                f"แพงเกินตลาด {deviation_pct:.0f}% — "
                f"ค่าปกติ ${typical:.0f}, ถูกเรียก ${amount:.0f} "
                f"→ ควรเจรจาลดราคาหรือเปลี่ยนผู้ให้บริการ"
            )

        elif deviation > OVERCHARGE_THRESHOLD:
            status = "OVERCHARGE"
            overcharge_count += 1
            recommendation = (
                f"สูงกว่าตลาด {deviation_pct:.0f}% — "
                f"ค่าปกติ ${typical:.0f} → ลองขอส่วนลดได้"
            )

        elif amount > max_rate and max_rate > 0:
            status = "WARNING"
            recommendation = (
                f"เกิน max rate ตลาด (${max_rate:.0f}) — อาจมีเหตุผลพิเศษ ควรตรวจสอบ"
            )

        elif deviation < -0.3:
            recommendation = f"ต่ำกว่าตลาดมาก ({abs(deviation_pct):.0f}%) — ราคาดี"
            savings = 0

        else:
            savings = 0

        total_savings += savings

        results.append(AuditResult(
            charge_type=charge.charge_type,
            description=charge.description,
            charged_amount=amount,
            market_typical=typical,
            market_max=max_rate,
            deviation_pct=deviation_pct,
            status=status,
            savings_potential=savings,
            recommendation=recommendation,
        ))

    # Overall status
    if overcharge_count == 0:
        overall = "PASS"
        summary = "บิลค่าขนส่งอยู่ในเกณฑ์ปกติ ไม่พบรายการแพงเกินจริง"
    elif any(r.status == "SEVERE" for r in results):
        overall = "OVERCHARGED"
        summary = (
            f"พบ {overcharge_count} รายการแพงเกินตลาด "
            f"ประหยัดได้ประมาณ ${total_savings:.0f} ถ้าเจรจาใหม่"
        )
    else:
        overall = "WARNING"
        summary = (
            f"พบ {overcharge_count} รายการสูงกว่าตลาดเล็กน้อย "
            f"ประหยัดได้ประมาณ ${total_savings:.0f}"
        )

    return FreightAuditReport(
        shipment_mode=shipment_mode,
        origin_region=origin_region,
        total_charged=total_charged,
        total_market_typical=total_typical,
        total_savings_potential=total_savings,
        overall_status=overall,
        overcharge_count=overcharge_count,
        line_items=results,
        audit_timestamp=datetime.now(timezone.utc).isoformat(),
        summary=summary,
    )


def get_charge_categories(mode: str = "") -> list[dict]:
    """รายชื่อ charge categories ทั้งหมด"""
    cats = []
    for key, info in CHARGE_CATEGORIES.items():
        if mode and info["mode"] not in (mode, "all"):
            continue
        cats.append({
            "code": key,
            "name": info["name"],
            "mode": info["mode"],
            "has_market_rate": _get_market_rate(key, mode or "sea", "default") is not None,
        })
    return cats


def get_market_rate_card(mode: str = "sea", region: str = "default") -> list[dict]:
    """แสดง market rate card — ราคาตลาดทั้งหมดสำหรับ mode + region"""
    rates = []

    if mode == "sea":
        source = MARKET_RATES_SEA
    elif mode == "air":
        source = MARKET_RATES_AIR
    else:
        source = {}

    # Mode-specific rates
    for charge_type, regions in source.items():
        rate = regions.get(region, regions.get("default"))
        if rate:
            cat = CHARGE_CATEGORIES.get(charge_type, {})
            rates.append({
                "charge_type": charge_type,
                "name": cat.get("name", charge_type),
                "min_usd": rate["min"],
                "typical_usd": rate["typical"],
                "max_usd": rate["max"],
                "region": region,
            })

    # Common rates
    for charge_type, regions in MARKET_RATES_COMMON.items():
        rate = regions.get(region, regions.get("default"))
        if rate:
            cat = CHARGE_CATEGORIES.get(charge_type, {})
            rates.append({
                "charge_type": charge_type,
                "name": cat.get("name", charge_type),
                "min_usd": rate["min"],
                "typical_usd": rate["typical"],
                "max_usd": rate["max"],
                "region": "all",
            })

    return rates


def compare_forwarder_quotes(
    quotes: list[dict],
    shipment_mode: str = "sea",
    origin_region: str = "default",
) -> dict:
    """
    เปรียบเทียบใบเสนอราคาจากหลาย forwarder

    quotes: list of {"name": "Forwarder A", "charges": [ChargeLineItem...]}
    Returns: ranking + savings analysis
    """
    results = []
    for quote in quotes:
        charges = [
            ChargeLineItem(
                charge_type=c.get("charge_type", "other"),
                description=c.get("description", ""),
                amount_usd=float(c.get("amount_usd", 0)),
                quantity=int(c.get("quantity", 1)),
            )
            for c in quote.get("charges", [])
        ]

        report = audit_freight_bill(charges, shipment_mode, origin_region)
        results.append({
            "name": quote.get("name", "Unknown"),
            "total_usd": report.total_charged,
            "overcharge_count": report.overcharge_count,
            "savings_potential": report.total_savings_potential,
            "status": report.overall_status,
        })

    # Sort by total cost
    results.sort(key=lambda x: x["total_usd"])

    if len(results) >= 2:
        cheapest = results[0]["total_usd"]
        most_expensive = results[-1]["total_usd"]
        diff = most_expensive - cheapest
        summary = (
            f"ถูกสุด: {results[0]['name']} (${cheapest:.0f}) | "
            f"แพงสุด: {results[-1]['name']} (${most_expensive:.0f}) | "
            f"ส่วนต่าง: ${diff:.0f} ({diff/most_expensive*100:.0f}%)"
        )
    else:
        summary = "ต้องมีอย่างน้อย 2 ใบเสนอราคาเพื่อเปรียบเทียบ"

    return {
        "ranking": results,
        "recommendation": results[0]["name"] if results else None,
        "summary": summary,
    }


# ── Helper Functions ─────────────────────────────────────────────────────────

def _get_market_rate(
    charge_type: str,
    mode: str,
    region: str,
) -> Optional[dict]:
    """ค้นหา market rate สำหรับ charge type"""
    # Try mode-specific rates first
    if mode == "sea" and charge_type in MARKET_RATES_SEA:
        rates = MARKET_RATES_SEA[charge_type]
        return rates.get(region, rates.get("default"))

    if mode == "air" and charge_type in MARKET_RATES_AIR:
        rates = MARKET_RATES_AIR[charge_type]
        return rates.get(region, rates.get("default"))

    # Try common rates
    if charge_type in MARKET_RATES_COMMON:
        rates = MARKET_RATES_COMMON[charge_type]
        return rates.get(region, rates.get("default"))

    return None


# ── Quick Test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Freight Rate Auditor — Test ===\n")

    # Simulate a sea freight bill from China
    bill = [
        ChargeLineItem("thc_origin", "THC Origin Charge", 250.0),
        ChargeLineItem("ocean_freight", "Ocean Freight 20ft FCL", 800.0),
        ChargeLineItem("baf", "Bunker Adjustment Factor", 350.0),
        ChargeLineItem("thc_destination", "THC Laem Chabang", 120.0),
        ChargeLineItem("do_fee", "D/O Fee", 150.0),           # overcharged!
        ChargeLineItem("customs_clearance", "Customs Clearance", 300.0),  # overcharged!
        ChargeLineItem("documentation", "Documentation Fee", 120.0),      # severely overcharged!
        ChargeLineItem("handling_fee", "Handling", 50.0),
    ]

    report = audit_freight_bill(bill, "sea", "east_asia")
    print(f"Total Charged: ${report.total_charged:.0f}")
    print(f"Market Typical: ${report.total_market_typical:.0f}")
    print(f"Savings Potential: ${report.total_savings_potential:.0f}")
    print(f"Status: {report.overall_status}")
    print(f"Summary: {report.summary}\n")

    for item in report.line_items:
        flag = " ⚠️" if item.status in ("OVERCHARGE", "SEVERE") else ""
        print(f"  [{item.status:10s}] {item.description}: ${item.charged_amount:.0f}"
              f" (typical ${item.market_typical:.0f}){flag}")
        if item.savings_potential > 0:
            print(f"              → ประหยัดได้ ${item.savings_potential:.0f}")

    # Market rate card
    print(f"\n--- Market Rate Card (Sea, East Asia) ---")
    card = get_market_rate_card("sea", "east_asia")
    for r in card[:5]:
        print(f"  {r['name']}: ${r['min_usd']}-${r['max_usd']} (typical ${r['typical_usd']})")
