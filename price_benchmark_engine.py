"""
price_benchmark_engine.py — Phase 22: Price Benchmark Intelligence
AI TO AI HOLDING — Customs Intelligence Division

ระบบเปรียบเทียบราคานำเข้าและตรวจจับ Under-valuation:
  - เก็บ price data จาก invoice items (anonymized)
  - คำนวณ benchmark ต่อ HS code + origin country
  - ตรวจจับ unit price ต่ำผิดปกติ → Red Flag
  - Valuation Risk Score 0-100

Data sources:
  1. Invoice items ที่ผ่านระบบ (primary)
  2. Reference prices (manual seed / future: กรมศุลกากร)

Under-valuation logic:
  unit_price < benchmark_median × (1 - THRESHOLD) → Red Flag
  Default THRESHOLD = 0.30 (30% ต่ำกว่า median)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import math
import statistics

# ── Configuration ────────────────────────────────────────────────────────────

UNDERVALUATION_THRESHOLD = 0.30   # 30% ต่ำกว่า median = Red Flag
OVERVALUATION_THRESHOLD = 2.0     # 200% สูงกว่า median = ราคาสูงผิดปกติ
MIN_DATA_POINTS = 3               # ต้องมีอย่างน้อย 3 จุดข้อมูลจึงจะคำนวณ benchmark ได้
STALE_MONTHS = 12                 # ข้อมูลเก่ากว่า 12 เดือน weight ลดลง


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class PriceBenchmark:
    """ข้อมูล benchmark ราคาต่อ HS code"""
    hs_code: str
    hs_code_group: str              # 4-digit heading for broader comparison
    origin_country: Optional[str]   # None = ทุกประเทศรวม
    currency: str                   # normalized to USD
    unit: str                       # dominant unit (KG, PCS, etc.)

    # Statistics
    data_points: int = 0
    median_price: float = 0.0
    mean_price: float = 0.0
    min_price: float = 0.0
    max_price: float = 0.0
    std_dev: float = 0.0
    p25: float = 0.0               # percentile 25
    p75: float = 0.0               # percentile 75
    iqr: float = 0.0               # interquartile range

    # Thresholds (auto-calculated)
    red_flag_below: float = 0.0     # < this = under-valued
    yellow_flag_below: float = 0.0  # < this = suspicious
    red_flag_above: float = 0.0     # > this = over-valued

    last_updated: str = ""
    source_invoices: int = 0        # unique invoices contributing data

    def to_dict(self) -> dict:
        return {
            "hs_code": self.hs_code,
            "hs_code_group": self.hs_code_group,
            "origin_country": self.origin_country or "ALL",
            "currency": self.currency,
            "unit": self.unit,
            "statistics": {
                "data_points": self.data_points,
                "median": round(self.median_price, 4),
                "mean": round(self.mean_price, 4),
                "min": round(self.min_price, 4),
                "max": round(self.max_price, 4),
                "std_dev": round(self.std_dev, 4),
                "p25": round(self.p25, 4),
                "p75": round(self.p75, 4),
                "iqr": round(self.iqr, 4),
            },
            "thresholds": {
                "red_flag_below": round(self.red_flag_below, 4),
                "yellow_flag_below": round(self.yellow_flag_below, 4),
                "red_flag_above": round(self.red_flag_above, 4),
            },
            "source_invoices": self.source_invoices,
            "last_updated": self.last_updated,
        }


@dataclass
class ValuationRisk:
    """ผลตรวจ Valuation Risk ต่อ item"""
    hs_code: str
    declared_price: float
    benchmark_median: float
    deviation_pct: float            # % ห่างจาก median (negative = ต่ำกว่า)
    risk_score: int                 # 0-100 (0=ปกติ, 100=เสี่ยงสูงสุด)
    risk_level: str                 # GREEN / YELLOW / RED
    flag_reason: str                # คำอธิบาย
    benchmark_data_points: int
    recommendation: str

    def to_dict(self) -> dict:
        return {
            "hs_code": self.hs_code,
            "declared_price": round(self.declared_price, 4),
            "benchmark_median": round(self.benchmark_median, 4),
            "deviation_pct": round(self.deviation_pct, 2),
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "flag_reason": self.flag_reason,
            "benchmark_data_points": self.benchmark_data_points,
            "recommendation": self.recommendation,
        }


@dataclass
class BenchmarkSummary:
    """สรุปภาพรวม benchmark ทั้งระบบ"""
    total_hs_codes: int = 0
    total_data_points: int = 0
    total_invoices: int = 0
    red_flags_today: int = 0
    yellow_flags_today: int = 0
    top_flagged_hs: list = field(default_factory=list)
    coverage_by_chapter: dict = field(default_factory=dict)


# ── Core Functions ───────────────────────────────────────────────────────────

def calculate_benchmark(prices: list[float], unit: str = "KG") -> Optional[PriceBenchmark]:
    """
    คำนวณ benchmark จากชุดราคา
    Returns None ถ้าข้อมูลไม่พอ
    """
    # กรอง outlier สุดขีด (ราคา 0 หรือ negative)
    clean = [p for p in prices if p and p > 0]

    if len(clean) < MIN_DATA_POINTS:
        return None

    clean.sort()
    n = len(clean)

    median = statistics.median(clean)
    mean = statistics.mean(clean)
    std = statistics.stdev(clean) if n > 1 else 0.0

    # Percentiles
    p25 = _percentile(clean, 25)
    p75 = _percentile(clean, 75)
    iqr = p75 - p25

    bm = PriceBenchmark(
        hs_code="",  # caller sets
        hs_code_group="",
        origin_country=None,
        currency="USD",
        unit=unit,
        data_points=n,
        median_price=median,
        mean_price=mean,
        min_price=clean[0],
        max_price=clean[-1],
        std_dev=std,
        p25=p25,
        p75=p75,
        iqr=iqr,
        red_flag_below=median * (1 - UNDERVALUATION_THRESHOLD),
        yellow_flag_below=median * (1 - UNDERVALUATION_THRESHOLD * 0.6),  # 18% = yellow
        red_flag_above=median * OVERVALUATION_THRESHOLD,
        last_updated=datetime.now(timezone.utc).isoformat(),
    )
    return bm


def assess_valuation_risk(
    unit_price: float,
    benchmark: PriceBenchmark,
    hs_code: str = "",
    origin_country: str = "",
) -> ValuationRisk:
    """
    ประเมินความเสี่ยง under/over-valuation ของราคาที่ประกาศ

    Risk Score Logic:
      0-20:  GREEN  — ราคาอยู่ในช่วงปกติ
      21-50: YELLOW — ราคาน่าสงสัย ควรตรวจสอบเพิ่ม
      51-100: RED   — ราคาผิดปกติชัดเจน แนะนำตรวจสอบ
    """
    median = benchmark.median_price
    if median <= 0:
        return ValuationRisk(
            hs_code=hs_code,
            declared_price=unit_price,
            benchmark_median=0,
            deviation_pct=0,
            risk_score=0,
            risk_level="UNKNOWN",
            flag_reason="ไม่มีข้อมูล benchmark เพียงพอ",
            benchmark_data_points=benchmark.data_points,
            recommendation="รอข้อมูลเพิ่มเติม",
        )

    # Deviation from median (negative = ต่ำกว่า)
    deviation = (unit_price - median) / median
    deviation_pct = deviation * 100

    # Calculate risk score
    risk_score = 0
    risk_level = "GREEN"
    flag_reason = "ราคาอยู่ในช่วงปกติ"
    recommendation = "ไม่จำเป็นต้องตรวจสอบเพิ่มเติม"

    if unit_price < benchmark.red_flag_below:
        # Under-valued — RED
        severity = abs(deviation) / UNDERVALUATION_THRESHOLD
        risk_score = min(100, int(50 + severity * 30))
        risk_level = "RED"
        flag_reason = (
            f"ราคาต่ำกว่า median {abs(deviation_pct):.1f}% "
            f"(ประกาศ ${unit_price:.2f} vs median ${median:.2f}/{benchmark.unit})"
        )
        recommendation = "แนะนำตรวจสอบ — อาจเป็น under-valuation เพื่อหลีกเลี่ยงภาษี"

    elif unit_price < benchmark.yellow_flag_below:
        # Suspicious — YELLOW
        severity = abs(deviation) / (UNDERVALUATION_THRESHOLD * 0.6)
        risk_score = min(50, int(20 + severity * 20))
        risk_level = "YELLOW"
        flag_reason = (
            f"ราคาต่ำกว่า median {abs(deviation_pct):.1f}% "
            f"(ประกาศ ${unit_price:.2f} vs median ${median:.2f}/{benchmark.unit})"
        )
        recommendation = "ราคาอยู่ในเขตเตือน — พิจารณาตรวจสอบเอกสารเพิ่มเติม"

    elif unit_price > benchmark.red_flag_above:
        # Over-valued — YELLOW (less common fraud but still suspicious)
        severity = deviation / OVERVALUATION_THRESHOLD
        risk_score = min(70, int(30 + severity * 20))
        risk_level = "YELLOW"
        flag_reason = (
            f"ราคาสูงกว่า median {deviation_pct:.1f}% "
            f"(ประกาศ ${unit_price:.2f} vs median ${median:.2f}/{benchmark.unit})"
        )
        recommendation = "ราคาสูงผิดปกติ — อาจเป็นการ over-invoice เพื่อย้ายเงินออก"

    else:
        # Normal range
        risk_score = max(0, int(abs(deviation_pct) / 3))

    # Adjust confidence by data points (more data = more confident)
    if benchmark.data_points < 5:
        risk_score = int(risk_score * 0.6)  # ลดความมั่นใจถ้าข้อมูลน้อย
        recommendation += " (ข้อมูล benchmark ยังน้อย — ความมั่นใจปานกลาง)"
    elif benchmark.data_points < 10:
        risk_score = int(risk_score * 0.8)

    return ValuationRisk(
        hs_code=hs_code,
        declared_price=unit_price,
        benchmark_median=median,
        deviation_pct=deviation_pct,
        risk_score=risk_score,
        risk_level=risk_level,
        flag_reason=flag_reason,
        benchmark_data_points=benchmark.data_points,
        recommendation=recommendation,
    )


def batch_assess(
    items: list[dict],
    benchmarks: dict[str, PriceBenchmark],
) -> list[ValuationRisk]:
    """
    ตรวจ valuation risk ทีเดียวทั้ง invoice
    items: list of {"hs_code": ..., "unit_price": ..., "origin_country": ...}
    benchmarks: dict hs_code → PriceBenchmark
    """
    results = []
    for item in items:
        hs = item.get("hs_code", "")
        price = float(item.get("unit_price", 0))
        origin = item.get("origin_country", "")

        if not hs or price <= 0:
            results.append(ValuationRisk(
                hs_code=hs,
                declared_price=price,
                benchmark_median=0,
                deviation_pct=0,
                risk_score=0,
                risk_level="UNKNOWN",
                flag_reason="ข้อมูลไม่ครบ (HS code หรือราคาหายไป)",
                benchmark_data_points=0,
                recommendation="กรุณาระบุ HS code และราคาต่อหน่วย",
            ))
            continue

        # ลอง exact HS match ก่อน, fallback ไป 6-digit, 4-digit
        bm = _find_benchmark(hs, origin, benchmarks)
        if bm:
            results.append(assess_valuation_risk(price, bm, hs, origin))
        else:
            results.append(ValuationRisk(
                hs_code=hs,
                declared_price=price,
                benchmark_median=0,
                deviation_pct=0,
                risk_score=0,
                risk_level="NO_DATA",
                flag_reason=f"ยังไม่มีข้อมูล benchmark สำหรับ HS {hs}",
                benchmark_data_points=0,
                recommendation="ระบบยังไม่มีข้อมูลเพียงพอ — จะสะสมจาก invoice ที่เข้ามา",
            ))

    return results


# ── Database Functions (PostgreSQL) ──────────────────────────────────────────

async def build_benchmarks_from_db(pool) -> dict[str, PriceBenchmark]:
    """
    ดึงข้อมูลจาก invoice_items แล้วสร้าง benchmark per HS code
    Returns: dict[hs_code] → PriceBenchmark
    """
    query = """
        SELECT
            hs_code_final AS hs_code,
            country_origin,
            unit_price,
            unit,
            submission_id
        FROM invoice_items
        WHERE hs_code_final IS NOT NULL
          AND unit_price IS NOT NULL
          AND unit_price > 0
          AND created_at > NOW() - INTERVAL '24 months'
        ORDER BY hs_code_final, country_origin
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query)

    if not rows:
        return {}

    # Group by HS code
    hs_groups: dict[str, list] = {}
    hs_units: dict[str, dict] = {}       # track dominant unit per HS
    hs_invoices: dict[str, set] = {}     # unique invoices per HS

    for row in rows:
        hs = row["hs_code"]
        price = float(row["unit_price"])
        unit = (row["unit"] or "PCS").upper()
        sub_id = row["submission_id"]

        if hs not in hs_groups:
            hs_groups[hs] = []
            hs_units[hs] = {}
            hs_invoices[hs] = set()

        hs_groups[hs].append(price)
        hs_units[hs][unit] = hs_units[hs].get(unit, 0) + 1
        hs_invoices[hs].add(sub_id)

    # Build benchmarks
    benchmarks = {}
    for hs, prices in hs_groups.items():
        bm = calculate_benchmark(prices)
        if bm:
            # Set dominant unit
            dominant_unit = max(hs_units[hs], key=hs_units[hs].get)
            bm.hs_code = hs
            bm.hs_code_group = hs[:4] if len(hs) >= 4 else hs
            bm.unit = dominant_unit
            bm.source_invoices = len(hs_invoices[hs])
            benchmarks[hs] = bm

    return benchmarks


async def check_item_valuation(
    pool,
    hs_code: str,
    unit_price: float,
    origin_country: str = "",
) -> ValuationRisk:
    """
    ตรวจ valuation risk ของ item เดียว โดยดึง benchmark จาก DB
    """
    benchmarks = await build_benchmarks_from_db(pool)
    bm = _find_benchmark(hs_code, origin_country, benchmarks)

    if not bm:
        return ValuationRisk(
            hs_code=hs_code,
            declared_price=unit_price,
            benchmark_median=0,
            deviation_pct=0,
            risk_score=0,
            risk_level="NO_DATA",
            flag_reason=f"ยังไม่มีข้อมูล benchmark สำหรับ HS {hs_code}",
            benchmark_data_points=0,
            recommendation="ระบบยังไม่มีข้อมูลเพียงพอ",
        )

    return assess_valuation_risk(unit_price, bm, hs_code, origin_country)


async def get_benchmark(pool, hs_code: str, origin_country: str = "") -> Optional[dict]:
    """ดึง benchmark สำหรับ HS code เดียว"""
    benchmarks = await build_benchmarks_from_db(pool)
    bm = _find_benchmark(hs_code, origin_country, benchmarks)
    return bm.to_dict() if bm else None


async def get_all_benchmarks(pool, limit: int = 50) -> list[dict]:
    """ดึง benchmarks ทั้งหมด (Chairman view)"""
    benchmarks = await build_benchmarks_from_db(pool)
    sorted_bm = sorted(benchmarks.values(), key=lambda b: b.data_points, reverse=True)
    return [b.to_dict() for b in sorted_bm[:limit]]


async def get_flagged_items(pool, days: int = 30, limit: int = 50) -> list[dict]:
    """ดึง items ที่ถูก flag ว่า valuation ผิดปกติ"""
    query = """
        SELECT
            ii.id,
            ii.submission_id,
            ii.description,
            ii.hs_code_final AS hs_code,
            ii.unit_price,
            ii.line_value,
            ii.unit,
            ii.country_origin,
            ii.valuation_flag,
            ii.valuation_note,
            ii.confidence,
            ii.created_at,
            inv.invoice_no,
            inv.seller_name,
            inv.seller_country
        FROM invoice_items ii
        JOIN invoice_submissions inv ON inv.id = ii.submission_id
        WHERE ii.valuation_flag = TRUE
          AND ii.created_at > NOW() - ($1 || ' days')::INTERVAL
        ORDER BY ii.created_at DESC
        LIMIT $2
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, str(days), limit)

    return [dict(row) for row in rows]


async def get_benchmark_summary(pool) -> dict:
    """สรุปภาพรวม benchmark ทั้งระบบ (Chairman dashboard)"""
    benchmarks = await build_benchmarks_from_db(pool)

    # Flagged items count
    async with pool.acquire() as conn:
        flag_30d = await conn.fetchval(
            "SELECT COUNT(*) FROM invoice_items WHERE valuation_flag=TRUE AND created_at > NOW() - INTERVAL '30 days'"
        )
        total_items = await conn.fetchval(
            "SELECT COUNT(*) FROM invoice_items WHERE hs_code_final IS NOT NULL AND unit_price > 0"
        )

    # Coverage by chapter (2-digit)
    chapters = {}
    for hs, bm in benchmarks.items():
        ch = hs[:2] if len(hs) >= 2 else "??"
        if ch not in chapters:
            chapters[ch] = {"hs_codes": 0, "data_points": 0}
        chapters[ch]["hs_codes"] += 1
        chapters[ch]["data_points"] += bm.data_points

    # Top flagged HS (by data points, showing thresholds)
    top = sorted(benchmarks.values(), key=lambda b: b.data_points, reverse=True)[:10]

    return {
        "total_hs_codes_with_benchmark": len(benchmarks),
        "total_data_points": sum(b.data_points for b in benchmarks.values()),
        "total_source_items": total_items or 0,
        "flagged_items_30d": flag_30d or 0,
        "coverage_by_chapter": chapters,
        "top_benchmarks": [b.to_dict() for b in top],
    }


async def flag_invoice_items(pool, submission_id: str) -> list[dict]:
    """
    ตรวจทุก item ใน invoice แล้ว update valuation_flag + valuation_note
    เรียกหลัง classify เสร็จ
    Returns: list of flagged items
    """
    benchmarks = await build_benchmarks_from_db(pool)
    if not benchmarks:
        return []

    async with pool.acquire() as conn:
        items = await conn.fetch(
            """
            SELECT id, hs_code_final, unit_price, country_origin, unit
            FROM invoice_items
            WHERE submission_id = $1
              AND hs_code_final IS NOT NULL
              AND unit_price IS NOT NULL
              AND unit_price > 0
            """,
            submission_id
        )

        flagged = []
        for item in items:
            hs = item["hs_code_final"]
            price = float(item["unit_price"])
            origin = item["country_origin"] or ""

            bm = _find_benchmark(hs, origin, benchmarks)
            if not bm:
                continue

            risk = assess_valuation_risk(price, bm, hs, origin)

            if risk.risk_level in ("RED", "YELLOW"):
                await conn.execute(
                    """
                    UPDATE invoice_items
                    SET valuation_flag = TRUE,
                        valuation_note = $2
                    WHERE id = $1
                    """,
                    item["id"],
                    risk.flag_reason,
                )
                flagged.append(risk.to_dict())
            else:
                # Clear flag ถ้าเคย flag แล้วตอนนี้ปกติ
                await conn.execute(
                    """
                    UPDATE invoice_items
                    SET valuation_flag = FALSE,
                        valuation_note = NULL
                    WHERE id = $1
                    """,
                    item["id"],
                )

        return flagged


# ── Reference Price Seed ─────────────────────────────────────────────────────
# ข้อมูลราคาอ้างอิงเบื้องต้น (สำหรับ bootstrap ก่อนมี invoice data จริง)
# Source: ราคาตลาดโดยประมาณ ณ 2026

REFERENCE_PRICES: dict[str, dict] = {
    # HS Chapter 03 — สัตว์น้ำ
    "0306.17": {"description": "กุ้งแช่แข็ง (Frozen shrimp)", "unit": "KG",
                "prices": [8.0, 9.5, 10.0, 11.0, 12.5, 8.5, 9.0, 10.5, 11.5, 13.0]},
    "0302.71": {"description": "ปลานิล (Tilapia)", "unit": "KG",
                "prices": [2.5, 3.0, 3.5, 2.8, 3.2, 2.6, 3.1, 3.3, 2.9, 3.4]},

    # HS Chapter 08 — ผลไม้
    "0804.50": {"description": "มะม่วง (Mango)", "unit": "KG",
                "prices": [1.2, 1.5, 1.8, 2.0, 1.3, 1.6, 1.4, 1.7, 1.9, 2.1]},
    "0803.10": {"description": "กล้วย (Banana)", "unit": "KG",
                "prices": [0.5, 0.6, 0.7, 0.55, 0.65, 0.8, 0.58, 0.62, 0.72, 0.68]},

    # HS Chapter 39 — พลาสติก
    "3901.10": {"description": "โพลีเอทิลีน (Polyethylene PE)", "unit": "KG",
                "prices": [1.0, 1.1, 1.2, 1.15, 0.95, 1.05, 1.08, 1.18, 1.22, 1.0]},
    "3907.61": {"description": "PET resin", "unit": "KG",
                "prices": [0.9, 0.95, 1.0, 1.05, 0.92, 0.98, 1.02, 0.88, 0.96, 1.08]},

    # HS Chapter 72 — เหล็ก
    "7208.51": {"description": "เหล็กแผ่นรีดร้อน (Hot-rolled steel)", "unit": "KG",
                "prices": [0.55, 0.60, 0.65, 0.58, 0.62, 0.56, 0.63, 0.59, 0.61, 0.57]},

    # HS Chapter 84 — เครื่องจักร
    "8471.30": {"description": "คอมพิวเตอร์พกพา (Laptop)", "unit": "PCS",
                "prices": [350, 450, 550, 400, 500, 380, 420, 480, 520, 600]},
    "8443.32": {"description": "เครื่องพิมพ์ (Printer)", "unit": "PCS",
                "prices": [80, 120, 150, 100, 130, 90, 110, 140, 95, 135]},

    # HS Chapter 85 — อิเล็กทรอนิกส์
    "8517.12": {"description": "โทรศัพท์มือถือ (Mobile phone)", "unit": "PCS",
                "prices": [150, 200, 300, 180, 250, 170, 220, 280, 350, 190]},
    "8528.72": {"description": "จอ LED TV", "unit": "PCS",
                "prices": [200, 250, 300, 350, 220, 280, 320, 260, 310, 340]},

    # HS Chapter 61-62 — เสื้อผ้า
    "6109.10": {"description": "เสื้อยืดผ้าฝ้าย (Cotton T-shirt)", "unit": "PCS",
                "prices": [2.0, 2.5, 3.0, 2.3, 2.8, 3.5, 2.2, 2.6, 3.2, 2.4]},

    # HS Chapter 40 — ยาง
    "4001.22": {"description": "ยางแผ่นรมควัน (RSS)", "unit": "KG",
                "prices": [1.5, 1.6, 1.7, 1.55, 1.65, 1.45, 1.58, 1.62, 1.48, 1.52]},

    # HS Chapter 27 — เชื้อเพลิง
    "2710.12": {"description": "น้ำมันเบนซิน (Gasoline)", "unit": "L",
                "prices": [0.6, 0.65, 0.7, 0.62, 0.68, 0.72, 0.58, 0.64, 0.66, 0.71]},
}


def get_reference_benchmarks() -> dict[str, PriceBenchmark]:
    """สร้าง benchmark จากข้อมูลอ้างอิง (ใช้ bootstrap)"""
    benchmarks = {}
    for hs, data in REFERENCE_PRICES.items():
        bm = calculate_benchmark(data["prices"], data.get("unit", "KG"))
        if bm:
            bm.hs_code = hs
            bm.hs_code_group = hs[:4]
            bm.source_invoices = 0  # reference data, not from invoices
            benchmarks[hs] = bm
    return benchmarks


async def get_combined_benchmarks(pool) -> dict[str, PriceBenchmark]:
    """รวม benchmark จาก DB + reference (DB overrides reference)"""
    ref = get_reference_benchmarks()
    db = await build_benchmarks_from_db(pool)
    # DB data takes priority
    combined = {**ref, **db}
    return combined


# ── Helper Functions ─────────────────────────────────────────────────────────

def _percentile(sorted_data: list[float], p: int) -> float:
    """คำนวณ percentile จาก sorted list"""
    if not sorted_data:
        return 0.0
    k = (len(sorted_data) - 1) * (p / 100)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)


def _find_benchmark(
    hs_code: str,
    origin_country: str,
    benchmarks: dict[str, PriceBenchmark],
) -> Optional[PriceBenchmark]:
    """
    ค้นหา benchmark ที่ใกล้เคียงที่สุด:
    1. Exact HS code match
    2. 6-digit match
    3. 4-digit (heading) match
    """
    # 1. Exact match
    if hs_code in benchmarks:
        return benchmarks[hs_code]

    # 2. Try 6-digit
    hs6 = hs_code[:7] if len(hs_code) > 7 else hs_code[:6] if len(hs_code) > 6 else None
    if hs6 and hs6 in benchmarks:
        return benchmarks[hs6]

    # 3. Try 4-digit heading
    hs4 = hs_code[:4] if len(hs_code) >= 4 else None
    if hs4:
        # Find any benchmark that starts with same 4 digits
        candidates = [b for k, b in benchmarks.items() if k.startswith(hs4)]
        if candidates:
            # Return the one with most data points
            return max(candidates, key=lambda b: b.data_points)

    return None


# ── Quick Test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Price Benchmark Engine — Test ===\n")

    # Test with reference data
    ref = get_reference_benchmarks()
    print(f"Reference benchmarks: {len(ref)} HS codes\n")

    # Test shrimp benchmark
    shrimp = ref.get("0306.17")
    if shrimp:
        print(f"กุ้งแช่แข็ง (0306.17):")
        print(f"  Median: ${shrimp.median_price:.2f}/KG")
        print(f"  Mean: ${shrimp.mean_price:.2f}/KG")
        print(f"  Range: ${shrimp.min_price:.2f} - ${shrimp.max_price:.2f}")
        print(f"  Red flag below: ${shrimp.red_flag_below:.2f}/KG")
        print()

        # Test normal price
        risk1 = assess_valuation_risk(10.0, shrimp, "0306.17", "VN")
        print(f"  Price $10.00: {risk1.risk_level} (score {risk1.risk_score})")

        # Test suspicious price
        risk2 = assess_valuation_risk(5.0, shrimp, "0306.17", "VN")
        print(f"  Price $5.00:  {risk2.risk_level} (score {risk2.risk_score}) — {risk2.flag_reason}")

        # Test red flag price
        risk3 = assess_valuation_risk(3.0, shrimp, "0306.17", "VN")
        print(f"  Price $3.00:  {risk3.risk_level} (score {risk3.risk_score}) — {risk3.flag_reason}")

    # Test mobile phone
    phone = ref.get("8517.12")
    if phone:
        print(f"\nมือถือ (8517.12):")
        print(f"  Median: ${phone.median_price:.2f}/PCS")
        risk4 = assess_valuation_risk(50.0, phone, "8517.12", "CN")
        print(f"  Price $50:  {risk4.risk_level} (score {risk4.risk_score}) — {risk4.flag_reason}")
        risk5 = assess_valuation_risk(200.0, phone, "8517.12", "CN")
        print(f"  Price $200: {risk5.risk_level} (score {risk5.risk_score})")
