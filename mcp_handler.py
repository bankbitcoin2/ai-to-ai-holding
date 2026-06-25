"""
mcp_handler.py — Phase 19: Claude MCP Plugin Handler
AI TO AI HOLDING — Customs Intelligence Division

MCP tools สำหรับ Claude Desktop / Claude Code:
  - classify_hs    → เรียก /v1/customs/classify
  - check_fta      → เรียก /v1/customs/classify + กรอง FTA
  - analyze_invoice → เรียก /v1/invoice/upload
  - exchange_rate   → เรียก /v1/exchange-rates/convert

ใช้เป็น FastAPI router — mount เข้า main.py
"""

import json
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(prefix="/v1/mcp", tags=["MCP Plugin"])


# ── Models ─────────────────────────────────────────────────────────────────────

class ClassifyRequest(BaseModel):
    description: str = Field(..., description="คำบรรยายสินค้า")
    origin_country: Optional[str] = Field(None, description="ประเทศแหล่งกำเนิด ISO 2-letter")

class FTARequest(BaseModel):
    hs_code: str = Field(..., description="HS Code 6-11 หลัก")
    origin_country: str = Field(..., description="ประเทศแหล่งกำเนิด")
    dest_country: str = Field("TH", description="ประเทศปลายทาง")

class ExchangeRequest(BaseModel):
    from_currency: str = Field("USD", alias="from")
    to_currency: str = Field("THB", alias="to")
    amount: float = Field(1.0)

    class Config:
        populate_by_name = True


# ── Tools ──────────────────────────────────────────────────────────────────────

@router.post("/classify_hs", summary="MCP: จัดพิกัดศุลกากร")
async def mcp_classify(req: ClassifyRequest, x_api_key: str = Header(..., alias="X-API-Key")):
    """
    จัดพิกัด HS Code จากคำบรรยายสินค้า
    คืน: HS code, confidence, FTA, OGA, Halal, XAI reasoning
    """
    try:
        from db_adapter import get_pool
        from classification_agent import classify_item

        pool = await get_pool()
        async with pool.acquire() as db:
            result = await classify_item(
                description=req.description,
                origin_country=req.origin_country,
                db=db,
            )

        best = result.best
        if not best:
            return {"error": "ไม่สามารถจัดพิกัดได้", "description": req.description}

        # FTA check
        fta_info = None
        if best.hs_code and req.origin_country:
            try:
                from fta_engine import check_fta_eligibility
                fta_info = await check_fta_eligibility(
                    best.hs_code, req.origin_country, "TH"
                )
            except Exception:
                pass

        # OGA check
        oga_info = None
        try:
            from oga_engine import check_oga_all
            oga_info = await check_oga_all(best.hs_code, req.description)
        except Exception:
            pass

        return {
            "hs_code": best.hs_code,
            "hs_code_11": best.hs_code_11,
            "hs_description": best.hs_description,
            "hs_description_th": best.hs_description_th,
            "confidence": best.confidence_score,
            "source": best.source_reference,
            "reasoning": best.reasoning_steps,
            "fta": fta_info,
            "oga": oga_info,
            "candidates": [
                {"rank": c.rank, "hs_code": c.hs_code,
                 "description": c.hs_description, "confidence": c.confidence_score}
                for c in result.candidates[:3]
            ],
        }

    except Exception as e:
        raise HTTPException(500, "Classification error — internal processing failed")


@router.post("/check_fta", summary="MCP: ตรวจสอบ FTA")
async def mcp_check_fta(req: FTARequest, x_api_key: str = Header(..., alias="X-API-Key")):
    """ตรวจสอบสิทธิ FTA สำหรับ HS Code + origin country"""
    try:
        from fta_engine import check_fta_eligibility
        result = await check_fta_eligibility(
            req.hs_code, req.origin_country, req.dest_country
        )
        return {"success": True, "data": result}
    except ImportError:
        return {"success": False, "error": "FTA engine not available yet"}
    except Exception as e:
        raise HTTPException(500, "FTA check error — internal processing failed")


@router.post("/exchange_rate", summary="MCP: แปลงสกุลเงิน")
async def mcp_exchange(req: ExchangeRequest):
    """แปลงสกุลเงิน"""
    from currency_service import convert, get_rate
    rate = await get_rate(req.from_currency, req.to_currency)
    converted = await convert(req.amount, req.from_currency, req.to_currency)

    return {
        "from": req.from_currency,
        "to": req.to_currency,
        "amount": req.amount,
        "rate": rate,
        "converted": converted,
    }
