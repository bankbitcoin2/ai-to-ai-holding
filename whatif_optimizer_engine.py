"""
whatif_optimizer_engine.py — Phase 24: What-If Scenario Optimizer + Duty Engineering
AI TO AI HOLDING — Customs Intelligence Division

จำลองสถานการณ์นำเข้าเพื่อหาเงื่อนไขที่ดีที่สุด:
  1. Route Optimizer   — เปรียบเทียบเส้นทาง/mode (sea vs air vs land)
  2. FTA Optimizer     — หา FTA form ที่ประหยัดที่สุด
  3. Duty Engineering  — แนะนำ HS code ที่ถูกต้องและอากรต่ำสุด
  4. Volume Simulator  — จำลองว่าถ้าเพิ่ม volume จะคุ้มขึ้นแค่ไหน

Output: 3 options เปรียบเทียบ (เร็วสุด / คุ้มสุด / ประหยัดสุด)
ขายเป็น: Strategic Sourcing Tool สำหรับองค์กรใหญ่
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone

from landed_cost_engine import (
    calculate_landed_cost,
    INCOTERMS,
    THAI_VAT_RATE,
)
from freight_rate_service import (
    get_freight_rate,
    get_insurance_rate,
    _COUNTRY_REGION,
)


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class ScenarioOption:
    """ผลลัพธ์ของแต่ละสถานการณ์"""
    label: str                    # "เร็วสุด" / "คุ้มสุด" / "ประหยัดสุด"
    tag: str                      # FASTEST / BALANCED / CHEAPEST
    transport_mode: str
    origin_country: str
    incoterm: str
    fta_form: str
    duty_rate_pct: float
    freight_cost: float
    insurance_cost: float
    duty_amount: float
    vat_amount: float
    local_charges: float
    total_landed_cost: float
    transit_days: str             # "5-14 days"
    cost_per_unit: float
    savings_vs_worst: float       # เทียบกับ option แพงสุด
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "tag": self.tag,
            "transport_mode": self.transport_mode,
            "origin_country": self.origin_country,
            "incoterm": self.incoterm,
            "fta_form": self.fta_form,
            "duty_rate_pct": round(self.duty_rate_pct, 2),
            "cost_breakdown": {
                "freight": round(self.freight_cost, 2),
                "insurance": round(self.insurance_cost, 2),
                "duty": round(self.duty_amount, 2),
                "vat": round(self.vat_amount, 2),
                "local_charges": round(self.local_charges, 2),
            },
            "total_landed_cost_usd": round(self.total_landed_cost, 2),
            "transit_days": self.transit_days,
            "cost_per_unit_usd": round(self.cost_per_unit, 4),
            "savings_vs_worst_usd": round(self.savings_vs_worst, 2),
            "pros": self.pros,
            "cons": self.cons,
        }


@dataclass
class WhatIfResult:
    """ผลการจำลองสถานการณ์ทั้งหมด"""
    product_value: float
    hs_code: str
    item_count: int
    options: list[ScenarioOption]
    recommendation: str
    analysis: str

    def to_dict(self) -> dict:
        return {
            "product_value_usd": round(self.product_value, 2),
            "hs_code": self.hs_code,
            "item_count": self.item_count,
            "options": [o.to_dict() for o in self.options],
            "recommendation": self.recommendation,
            "analysis": self.analysis,
        }


# ── FTA Database (Thai FTAs) ─────────────────────────────────────────────────
# FTA agreements Thailand is party to, with typical preferential rates

FTA_AGREEMENTS: dict[str, dict] = {
    "ATIGA": {
        "name": "ASEAN Trade in Goods Agreement",
        "countries": ["VN", "MY", "SG", "ID", "PH", "MM", "LA", "KH", "BN"],
        "typical_rate_reduction": 1.0,  # ลดเหลือ 0% ส่วนใหญ่
        "form": "Form D",
    },
    "ACFTA": {
        "name": "ASEAN-China FTA",
        "countries": ["CN"],
        "typical_rate_reduction": 0.85,
        "form": "Form E",
    },
    "JTEPA": {
        "name": "Japan-Thailand EPA",
        "countries": ["JP"],
        "typical_rate_reduction": 0.80,
        "form": "Form JTEPA",
    },
    "AKFTA": {
        "name": "ASEAN-Korea FTA",
        "countries": ["KR"],
        "typical_rate_reduction": 0.75,
        "form": "Form AK",
    },
    "TAFTA": {
        "name": "Thailand-Australia FTA",
        "countries": ["AU"],
        "typical_rate_reduction": 0.90,
        "form": "Form TAF",
    },
    "TNZFTA": {
        "name": "Thailand-New Zealand FTA",
        "countries": ["NZ"],
        "typical_rate_reduction": 0.85,
        "form": "Form TNZF",
    },
    "AIFTA": {
        "name": "ASEAN-India FTA",
        "countries": ["IN"],
        "typical_rate_reduction": 0.70,
        "form": "Form AI",
    },
    "RCEP": {
        "name": "Regional Comprehensive Economic Partnership",
        "countries": ["CN", "JP", "KR", "AU", "NZ", "VN", "MY", "SG", "ID", "PH",
                      "MM", "LA", "KH", "BN"],
        "typical_rate_reduction": 0.60,
        "form": "Form RCEP",
    },
    "TCFTA": {
        "name": "Thailand-Chile FTA",
        "countries": ["CL"],
        "typical_rate_reduction": 0.70,
        "form": "Form TC",
    },
    "TPFTA": {
        "name": "Thailand-Peru FTA",
        "countries": ["PE"],
        "typical_rate_reduction": 0.65,
        "form": "Form TP",
    },
}


# ── Core Functions ───────────────────────────────────────────────────────────

def simulate_scenarios(
    product_value: float,
    hs_code: str,
    origin_country: str,
    mfn_duty_rate: float,
    item_count: int = 1,
    weight_kg: float = 0.0,
    incoterm: str = "FOB",
) -> WhatIfResult:
    """
    จำลอง 3 สถานการณ์: เร็วสุด / คุ้มสุด / ประหยัดสุด

    เปรียบเทียบ transport mode + FTA อัตโนมัติ
    """
    options = []

    # หา FTA ที่ดีที่สุดสำหรับ country นี้
    best_fta = find_best_fta(origin_country, mfn_duty_rate)
    fta_rate = best_fta["rate"] if best_fta else mfn_duty_rate
    fta_form = best_fta["form"] if best_fta else "MFN"

    modes = ["air", "sea", "land"]
    mode_results = []

    for mode in modes:
        try:
            result = calculate_landed_cost(
                product_value=product_value,
                incoterm=incoterm,
                hs_code=hs_code,
                origin_country=origin_country,
                transport_mode=mode,
                item_count=item_count,
                weight_kg=weight_kg,
                duty_rate=fta_rate,
                mfn_rate=mfn_duty_rate,
            )
            rd = result.to_dict()

            # Get transit time
            fr = get_freight_rate(mode, origin_country, weight_kg or 100)
            transit = f"{fr.get('transit_days_min', '?')}-{fr.get('transit_days_max', '?')} วัน" if fr else "N/A"

            mode_results.append({
                "mode": mode,
                "result": rd,
                "transit": transit,
                "transit_min": fr.get("transit_days_min", 999) if fr else 999,
                "total": rd["totals"]["total_landed_cost_usd"],
                "freight": rd["totals"].get("freight_usd", 0),
                "insurance": rd["totals"].get("insurance_usd", 0),
                "duty": rd["totals"].get("duty_usd", 0),
                "vat": rd["totals"].get("vat_usd", 0),
                "local": rd["totals"].get("local_charges_usd", 0),
            })
        except Exception:
            continue

    if not mode_results:
        return WhatIfResult(
            product_value=product_value,
            hs_code=hs_code,
            item_count=item_count,
            options=[],
            recommendation="ไม่สามารถจำลองสถานการณ์ได้ — ตรวจสอบข้อมูลอีกครั้ง",
            analysis="",
        )

    # Sort for each strategy
    by_speed = sorted(mode_results, key=lambda x: x["transit_min"])
    by_cost = sorted(mode_results, key=lambda x: x["total"])
    worst_cost = max(r["total"] for r in mode_results)

    # Option 1: FASTEST
    fastest = by_speed[0]
    options.append(_build_option(
        fastest, "เร็วสุด", "FASTEST", fta_form, fta_rate,
        item_count, worst_cost,
        pros=["ได้สินค้าเร็วที่สุด", "เหมาะกับสินค้าเร่งด่วน/เน่าเสียง่าย"],
        cons=["ค่าขนส่งสูง" if fastest["mode"] == "air" else ""],
    ))

    # Option 2: CHEAPEST
    cheapest = by_cost[0]
    if cheapest["mode"] != fastest["mode"]:
        options.append(_build_option(
            cheapest, "ประหยัดสุด", "CHEAPEST", fta_form, fta_rate,
            item_count, worst_cost,
            pros=["ต้นทุนรวมต่ำสุด", "เหมาะกับสินค้าไม่เร่ง"],
            cons=["ใช้เวลาขนส่งนาน" if cheapest["mode"] == "sea" else ""],
        ))

    # Option 3: BALANCED (middle ground or sea if not already used)
    balanced_mode = None
    for mr in mode_results:
        if mr["mode"] not in (fastest["mode"], cheapest["mode"]):
            balanced_mode = mr
            break
    if not balanced_mode and len(mode_results) >= 2:
        balanced_mode = by_cost[min(1, len(by_cost) - 1)]

    if balanced_mode and balanced_mode["mode"] != cheapest.get("mode"):
        options.append(_build_option(
            balanced_mode, "คุ้มสุด (สมดุล)", "BALANCED", fta_form, fta_rate,
            item_count, worst_cost,
            pros=["สมดุลระหว่างราคาและเวลา"],
            cons=[],
        ))

    # Sort options by total cost
    options.sort(key=lambda x: x.total_landed_cost)
    for i, opt in enumerate(options):
        opt.savings_vs_worst = worst_cost - opt.total_landed_cost

    # Recommendation
    if len(options) >= 2:
        diff = options[-1].total_landed_cost - options[0].total_landed_cost
        diff_pct = diff / options[-1].total_landed_cost * 100
        rec = (
            f"แนะนำ: {options[0].label} ({options[0].transport_mode}) "
            f"ประหยัดกว่า {options[-1].label} ${diff:.0f} ({diff_pct:.0f}%)"
        )
        analysis = _build_analysis(options, product_value, fta_form, mfn_duty_rate, fta_rate)
    else:
        rec = f"มีเส้นทางเดียวที่เหมาะสม: {options[0].transport_mode}"
        analysis = ""

    return WhatIfResult(
        product_value=product_value,
        hs_code=hs_code,
        item_count=item_count,
        options=options,
        recommendation=rec,
        analysis=analysis,
    )


def find_best_fta(
    origin_country: str,
    mfn_rate: float,
) -> Optional[dict]:
    """
    หา FTA ที่ให้อัตราอากรต่ำสุดสำหรับประเทศต้นทาง

    Returns: {"name": ..., "form": ..., "rate": ..., "saving_pct": ...}
    """
    country = origin_country.upper()
    candidates = []

    for fta_code, fta in FTA_AGREEMENTS.items():
        if country in fta["countries"]:
            pref_rate = mfn_rate * (1 - fta["typical_rate_reduction"])
            pref_rate = max(0, pref_rate)
            saving = mfn_rate - pref_rate
            candidates.append({
                "fta_code": fta_code,
                "name": fta["name"],
                "form": fta["form"],
                "rate": pref_rate,
                "saving_pct": saving,
                "reduction_pct": fta["typical_rate_reduction"] * 100,
            })

    if not candidates:
        return None

    # Sort by lowest rate
    candidates.sort(key=lambda x: x["rate"])
    return candidates[0]


def find_all_ftas(origin_country: str, mfn_rate: float) -> list[dict]:
    """หา FTA ทั้งหมดที่ใช้ได้กับประเทศต้นทาง"""
    country = origin_country.upper()
    results = []

    for fta_code, fta in FTA_AGREEMENTS.items():
        if country in fta["countries"]:
            pref_rate = mfn_rate * (1 - fta["typical_rate_reduction"])
            pref_rate = max(0, pref_rate)
            results.append({
                "fta_code": fta_code,
                "name": fta["name"],
                "form": fta["form"],
                "preferential_rate": round(pref_rate, 2),
                "mfn_rate": mfn_rate,
                "saving_pct": round(mfn_rate - pref_rate, 2),
                "reduction_pct": round(fta["typical_rate_reduction"] * 100, 1),
            })

    results.sort(key=lambda x: x["preferential_rate"])

    # Add MFN as reference
    results.append({
        "fta_code": "MFN",
        "name": "Most Favoured Nation (ไม่ใช้ FTA)",
        "form": "N/A",
        "preferential_rate": mfn_rate,
        "mfn_rate": mfn_rate,
        "saving_pct": 0,
        "reduction_pct": 0,
    })

    return results


def simulate_volume_impact(
    product_value_per_unit: float,
    hs_code: str,
    origin_country: str,
    mfn_duty_rate: float,
    transport_mode: str = "sea",
    incoterm: str = "FOB",
    volumes: list[int] = None,
) -> list[dict]:
    """
    จำลองผลกระทบของ volume ต่อ cost per unit

    volumes: [100, 500, 1000, 5000, 10000]
    แสดงว่า scale up จะลด cost per unit ลงเท่าไหร่
    """
    if volumes is None:
        volumes = [50, 100, 500, 1000, 5000]

    best_fta = find_best_fta(origin_country, mfn_duty_rate)
    fta_rate = best_fta["rate"] if best_fta else mfn_duty_rate

    results = []
    for vol in volumes:
        total_value = product_value_per_unit * vol
        weight = vol * 0.5  # estimate 0.5 kg per unit

        try:
            lc = calculate_landed_cost(
                product_value=total_value,
                incoterm=incoterm,
                hs_code=hs_code,
                origin_country=origin_country,
                transport_mode=transport_mode,
                item_count=vol,
                weight_kg=weight,
                duty_rate=fta_rate,
            )
            rd = lc.to_dict()
            total = rd["totals"]["total_landed_cost_usd"]
            cpu = total / vol if vol > 0 else 0

            results.append({
                "volume": vol,
                "total_product_value": round(total_value, 2),
                "total_landed_cost": round(total, 2),
                "cost_per_unit": round(cpu, 4),
                "markup_pct": round((total - total_value) / total_value * 100, 1) if total_value > 0 else 0,
            })
        except Exception:
            continue

    # Add savings analysis
    if len(results) >= 2:
        base_cpu = results[0]["cost_per_unit"]
        for r in results:
            r["savings_vs_minimum_order"] = round(base_cpu - r["cost_per_unit"], 4)
            r["savings_pct"] = round(
                (base_cpu - r["cost_per_unit"]) / base_cpu * 100, 1
            ) if base_cpu > 0 else 0

    return results


def duty_engineering_analysis(
    hs_code: str,
    origin_country: str,
    product_value: float,
    mfn_rate: float,
) -> dict:
    """
    วิเคราะห์ Duty Engineering — หาวิธีลดอากรนำเข้า

    แนะนำ:
    1. FTA ที่เหมาะสม
    2. HS code classification tips
    3. Incoterm optimization
    4. Bonded warehouse / FTZ options
    """
    best_fta = find_best_fta(origin_country, mfn_rate)
    all_ftas = find_all_ftas(origin_country, mfn_rate)

    mfn_duty = product_value * mfn_rate / 100
    fta_duty = product_value * (best_fta["rate"] / 100) if best_fta else mfn_duty
    duty_saving = mfn_duty - fta_duty

    strategies = []

    # Strategy 1: FTA Utilization
    if best_fta and duty_saving > 0:
        strategies.append({
            "strategy": "ใช้สิทธิ FTA",
            "description": (
                f"ใช้ {best_fta['name']} ({best_fta['form']}) "
                f"ลดอากรจาก {mfn_rate}% เหลือ {best_fta['rate']:.1f}%"
            ),
            "potential_saving_usd": round(duty_saving, 2),
            "difficulty": "LOW",
            "requirements": [
                f"ต้องมี {best_fta['form']} จากผู้ส่งออก",
                "สินค้าต้องผ่านเกณฑ์ Rules of Origin",
                "ยื่นก่อนหรือขณะผ่านพิธีการศุลกากร",
            ],
        })

    # Strategy 2: CIF Optimization
    if mfn_rate > 0:
        # ลด CIF value = ลดฐานคำนวณอากร
        strategies.append({
            "strategy": "ปรับ CIF Value (Incoterm)",
            "description": (
                "เจรจาใช้ FOB แทน CIF — ค่า freight/insurance ที่ต่ำลง "
                "จะลดฐานคำนวณอากร (ถ้าแจ้งค่าขนส่ง/ประกันต่ำกว่า CIF เดิม)"
            ),
            "potential_saving_usd": round(product_value * 0.05 * mfn_rate / 100, 2),
            "difficulty": "MEDIUM",
            "requirements": [
                "ต้องมีเอกสารค่าขนส่งและประกันแยก",
                "ศุลกากรอาจตรวจสอบ freight rate ว่าสมเหตุสมผล",
            ],
        })

    # Strategy 3: Tariff Classification Review
    strategies.append({
        "strategy": "ทบทวน HS Code",
        "description": (
            f"HS {hs_code} อาจจำแนกได้หลายพิกัด — "
            "ทบทวนว่าพิกัดที่ใช้ตรงกับลักษณะสินค้าจริงและให้อัตราที่ดีที่สุดหรือไม่"
        ),
        "potential_saving_usd": None,
        "difficulty": "HIGH",
        "requirements": [
            "ปรึกษา customs broker หรือใช้ Advance Ruling จากกรมศุลกากร",
            "ต้องจำแนกตามหลักเกณฑ์ GIR (General Interpretive Rules)",
            "ห้าม misclassify โดยเจตนา — มีโทษทางกฎหมาย",
        ],
    })

    # Strategy 4: Bonded Warehouse / FTZ
    if product_value > 50000:
        strategies.append({
            "strategy": "คลังสินค้าทัณฑ์บน / เขตปลอดอากร",
            "description": (
                "นำเข้าเข้าคลังทัณฑ์บน — เสียอากรเมื่อนำออกมาขายในประเทศเท่านั้น "
                "ถ้า re-export ไม่ต้องเสียอากร"
            ),
            "potential_saving_usd": round(mfn_duty * 0.3, 2),
            "difficulty": "HIGH",
            "requirements": [
                "ต้องขออนุญาตจัดตั้งคลังทัณฑ์บนหรือใช้เขตปลอดอากร",
                "เหมาะกับธุรกิจ re-export หรือผลิตเพื่อส่งออก",
                "มีค่าใช้จ่ายในการจัดการคลัง",
            ],
        })

    # Strategy 5: Volume Consolidation
    strategies.append({
        "strategy": "รวม shipment เพื่อลดต้นทุนขนส่ง",
        "description": (
            "รวมคำสั่งซื้อหลายรายการเป็น shipment เดียว (FCL แทน LCL) "
            "ลดค่า freight ต่อหน่วย 30-50%"
        ),
        "potential_saving_usd": round(product_value * 0.02, 2),
        "difficulty": "LOW",
        "requirements": [
            "ต้องมี volume เพียงพอเต็มตู้ (20ft ~25-28 CBM)",
            "วางแผนสั่งซื้อล่วงหน้า",
        ],
    })

    return {
        "hs_code": hs_code,
        "origin_country": origin_country,
        "product_value_usd": round(product_value, 2),
        "current_duty": {
            "mfn_rate_pct": mfn_rate,
            "mfn_duty_usd": round(mfn_duty, 2),
            "best_fta_rate_pct": round(best_fta["rate"], 2) if best_fta else mfn_rate,
            "best_fta_duty_usd": round(fta_duty, 2),
            "fta_saving_usd": round(duty_saving, 2),
        },
        "available_ftas": all_ftas,
        "strategies": strategies,
        "total_potential_saving_usd": round(
            sum(s["potential_saving_usd"] for s in strategies
                if s["potential_saving_usd"] is not None), 2
        ),
    }


# ── Helper Functions ─────────────────────────────────────────────────────────

def _build_option(
    mr: dict,
    label: str,
    tag: str,
    fta_form: str,
    fta_rate: float,
    item_count: int,
    worst_cost: float,
    pros: list[str] = None,
    cons: list[str] = None,
) -> ScenarioOption:
    total = mr["total"]
    return ScenarioOption(
        label=label,
        tag=tag,
        transport_mode=mr["mode"],
        origin_country=mr.get("origin", ""),
        incoterm=mr["result"].get("incoterm", "FOB"),
        fta_form=fta_form,
        duty_rate_pct=fta_rate,
        freight_cost=mr["freight"],
        insurance_cost=mr["insurance"],
        duty_amount=mr["duty"],
        vat_amount=mr["vat"],
        local_charges=mr["local"],
        total_landed_cost=total,
        transit_days=mr["transit"],
        cost_per_unit=total / item_count if item_count > 0 else total,
        savings_vs_worst=worst_cost - total,
        pros=[p for p in (pros or []) if p],
        cons=[c for c in (cons or []) if c],
    )


def _build_analysis(
    options: list[ScenarioOption],
    product_value: float,
    fta_form: str,
    mfn_rate: float,
    fta_rate: float,
) -> str:
    parts = []

    if len(options) >= 2:
        cheapest = options[0]
        most_expensive = options[-1]
        diff = most_expensive.total_landed_cost - cheapest.total_landed_cost
        parts.append(
            f"ส่วนต่างระหว่าง {cheapest.transport_mode} กับ {most_expensive.transport_mode}: "
            f"${diff:.0f} ({diff/product_value*100:.1f}% ของมูลค่าสินค้า)"
        )

    if fta_form != "MFN" and fta_rate < mfn_rate:
        saving = product_value * (mfn_rate - fta_rate) / 100
        parts.append(
            f"ใช้ {fta_form} ลดอากรจาก {mfn_rate}% เหลือ {fta_rate:.1f}% "
            f"ประหยัด ${saving:.0f}"
        )

    return " | ".join(parts)


# ── Quick Test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== What-If Scenario Optimizer — Test ===\n")

    # Test: import electronics from China
    result = simulate_scenarios(
        product_value=50000,
        hs_code="8517.12",
        origin_country="CN",
        mfn_duty_rate=5.0,
        item_count=200,
        weight_kg=100,
        incoterm="FOB",
    )

    print(f"สินค้า: มือถือ 200 เครื่อง มูลค่า $50,000 จากจีน\n")

    for opt in result.options:
        print(f"  [{opt.tag:10s}] {opt.label}")
        print(f"    Mode: {opt.transport_mode} | Transit: {opt.transit_days}")
        print(f"    Total: ${opt.total_landed_cost:.0f} | Per unit: ${opt.cost_per_unit:.2f}")
        if opt.pros:
            print(f"    Pros: {', '.join(opt.pros)}")
        print()

    print(f"แนะนำ: {result.recommendation}")
    if result.analysis:
        print(f"วิเคราะห์: {result.analysis}")

    # Test FTA
    print(f"\n--- FTA Analysis for CN ---")
    ftas = find_all_ftas("CN", 10.0)
    for f in ftas:
        print(f"  {f['fta_code']:8s} | {f['form']:12s} | Rate: {f['preferential_rate']:.1f}% | Save: {f['saving_pct']:.1f}%")

    # Test Volume
    print(f"\n--- Volume Impact ---")
    vols = simulate_volume_impact(
        product_value_per_unit=250,
        hs_code="8517.12",
        origin_country="CN",
        mfn_duty_rate=5.0,
        transport_mode="sea",
    )
    for v in vols:
        print(f"  Volume {v['volume']:>5d}: CPU ${v['cost_per_unit']:.2f} | Markup {v['markup_pct']}%")

    # Test Duty Engineering
    print(f"\n--- Duty Engineering ---")
    de = duty_engineering_analysis("8517.12", "CN", 50000, 5.0)
    for s in de["strategies"]:
        saving = f"${s['potential_saving_usd']}" if s['potential_saving_usd'] else "varies"
        print(f"  [{s['difficulty']:6s}] {s['strategy']}: {saving}")
