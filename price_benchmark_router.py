"""
price_benchmark_router.py — Phase 22: Price Benchmark API
AI TO AI HOLDING — Customs Intelligence Division

Public endpoints:
  POST /v1/benchmark/check          — ตรวจ valuation risk ของ item
  GET  /v1/benchmark/lookup         — ดู benchmark ราคาของ HS code
  GET  /v1/benchmark/reference      — ดูราคาอ้างอิงทั้งหมด

Chairman endpoints (hidden from Swagger):
  GET  /v1/chairman/benchmark/summary   — ภาพรวม benchmark ทั้งระบบ
  GET  /v1/chairman/benchmark/flagged   — รายการที่ถูก flag
  GET  /v1/chairman/benchmark/all       — benchmarks ทั้งหมด
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

from db_adapter import get_pool
from price_benchmark_engine import (
    get_benchmark,
    get_combined_benchmarks,
    get_all_benchmarks,
    get_flagged_items,
    get_benchmark_summary,
    get_reference_benchmarks,
    assess_valuation_risk,
    batch_assess,
    check_item_valuation,
    UNDERVALUATION_THRESHOLD,
)

router = APIRouter(tags=["Price Benchmark"])


# ── Request/Response Models ──────────────────────────────────────────────────

class ValuationCheckRequest(BaseModel):
    hs_code: str = Field(..., description="HS code (4-11 หลัก)")
    unit_price: float = Field(..., gt=0, description="ราคาต่อหน่วย (USD)")
    origin_country: str = Field("", description="ประเทศต้นทาง ISO 2-letter (เช่น CN, VN)")

    model_config = {"json_schema_extra": {
        "examples": [{"hs_code": "0306.17", "unit_price": 5.0, "origin_country": "VN"}]
    }}


class BatchCheckRequest(BaseModel):
    items: list[ValuationCheckRequest] = Field(
        ..., min_length=1, max_length=100,
        description="รายการ items ที่ต้องการตรวจ (สูงสุด 100)"
    )


# ── Public Endpoints ─────────────────────────────────────────────────────────

@router.post(
    "/v1/benchmark/check",
    summary="ตรวจ Valuation Risk",
    description=(
        "ตรวจว่าราคาที่ประกาศต่ำ/สูงผิดปกติหรือไม่ "
        "เทียบกับ benchmark จาก invoice data + ราคาอ้างอิง "
        f"Under-valuation threshold: {int(UNDERVALUATION_THRESHOLD*100)}% ต่ำกว่า median = Red Flag"
    ),
)
async def check_valuation(req: ValuationCheckRequest):
    pool = await get_pool()
    risk = await check_item_valuation(
        pool,
        hs_code=req.hs_code.strip(),
        unit_price=req.unit_price,
        origin_country=req.origin_country.strip().upper(),
    )
    return {
        "success": True,
        "result": risk.to_dict(),
        "threshold_info": {
            "undervaluation_pct": int(UNDERVALUATION_THRESHOLD * 100),
            "note": "risk_score 0-20=GREEN, 21-50=YELLOW, 51-100=RED",
        },
    }


@router.post(
    "/v1/benchmark/check-batch",
    summary="ตรวจ Valuation Risk ทีละหลาย items",
    description="ส่ง items ทั้ง invoice มาตรวจพร้อมกัน (สูงสุด 100 items)",
)
async def check_valuation_batch(req: BatchCheckRequest):
    pool = await get_pool()
    benchmarks = await get_combined_benchmarks(pool)

    items_data = [
        {"hs_code": it.hs_code.strip(), "unit_price": it.unit_price,
         "origin_country": it.origin_country.strip().upper()}
        for it in req.items
    ]

    results = batch_assess(items_data, benchmarks)

    red_count = sum(1 for r in results if r.risk_level == "RED")
    yellow_count = sum(1 for r in results if r.risk_level == "YELLOW")

    return {
        "success": True,
        "total_items": len(results),
        "red_flags": red_count,
        "yellow_flags": yellow_count,
        "overall_risk": "HIGH" if red_count > 0 else "MEDIUM" if yellow_count > 0 else "LOW",
        "results": [r.to_dict() for r in results],
    }


@router.get(
    "/v1/benchmark/lookup",
    summary="ดู benchmark ราคาของ HS code",
    description="แสดงสถิติราคา (median, mean, min, max, percentiles) และเกณฑ์ flag",
)
async def lookup_benchmark(
    hs_code: str = Query(..., description="HS code (4-11 หลัก)"),
    origin_country: str = Query("", description="ประเทศต้นทาง (optional)"),
):
    pool = await get_pool()
    result = await get_benchmark(pool, hs_code.strip(), origin_country.strip().upper())

    if not result:
        # ลอง reference data
        ref = get_reference_benchmarks()
        hs = hs_code.strip()
        if hs in ref:
            result = ref[hs].to_dict()
            result["source"] = "reference"
        else:
            return {
                "success": True,
                "found": False,
                "hs_code": hs_code,
                "message": f"ยังไม่มีข้อมูล benchmark สำหรับ HS {hs_code} — ข้อมูลจะสะสมจาก invoice ที่ผ่านระบบ",
            }

    result["source"] = result.get("source", "invoice_data")
    return {"success": True, "found": True, "benchmark": result}


@router.get(
    "/v1/benchmark/reference",
    summary="ดูราคาอ้างอิงทั้งหมด",
    description="แสดงราคาอ้างอิง (reference prices) ที่ฝังในระบบ สำหรับ HS codes ที่ยังไม่มีข้อมูล invoice",
)
async def list_reference_prices():
    ref = get_reference_benchmarks()
    from price_benchmark_engine import REFERENCE_PRICES

    items = []
    for hs, data in REFERENCE_PRICES.items():
        bm = ref.get(hs)
        items.append({
            "hs_code": hs,
            "description": data["description"],
            "unit": data["unit"],
            "median_price": round(bm.median_price, 2) if bm else None,
            "price_range": f"${min(data['prices']):.2f} - ${max(data['prices']):.2f}",
            "data_points": len(data["prices"]),
        })

    return {
        "success": True,
        "total": len(items),
        "reference_prices": items,
        "note": "ราคาอ้างอิงโดยประมาณ — ใช้ bootstrap ก่อนมีข้อมูล invoice จริง",
    }


# ── Chairman Endpoints (hidden from Swagger) ─────────────────────────────────

@router.get(
    "/v1/chairman/benchmark/summary",
    summary="[Chairman] ภาพรวม Price Benchmark ทั้งระบบ",
    include_in_schema=False,
)
async def chairman_benchmark_summary():
    pool = await get_pool()
    summary = await get_benchmark_summary(pool)
    return {"success": True, "data": summary}


@router.get(
    "/v1/chairman/benchmark/flagged",
    summary="[Chairman] รายการที่ถูก flag valuation ผิดปกติ",
    include_in_schema=False,
)
async def chairman_flagged_items(
    days: int = Query(30, ge=1, le=365, description="ย้อนหลังกี่วัน"),
    limit: int = Query(50, ge=1, le=200, description="จำนวนสูงสุด"),
):
    pool = await get_pool()
    items = await get_flagged_items(pool, days=days, limit=limit)
    return {
        "success": True,
        "total": len(items),
        "period_days": days,
        "flagged_items": items,
    }


@router.get(
    "/v1/chairman/benchmark/all",
    summary="[Chairman] Benchmarks ทั้งหมด",
    include_in_schema=False,
)
async def chairman_all_benchmarks(
    limit: int = Query(50, ge=1, le=500, description="จำนวนสูงสุด"),
):
    pool = await get_pool()
    benchmarks = await get_all_benchmarks(pool, limit=limit)
    ref = get_reference_benchmarks()

    return {
        "success": True,
        "from_invoices": len(benchmarks),
        "from_reference": len(ref),
        "benchmarks": benchmarks,
    }
