"""
api/treasury.py
Treasury API — Revenue Pillar: Splitting Pipeline (P-03)
Internal endpoint — ถูกเรียกจาก customs_service หลัง case complete
ไม่ expose ให้ client AI ภายนอกเรียกตรง
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import aiosqlite

from database import get_db
from treasury_service import settle_transaction, get_ledger_summary

router = APIRouter(
    prefix="/v1/treasury",
    tags=["Treasury (Internal)"],
    include_in_schema=False,  # ซ่อนจาก Swagger /docs — internal only
)


class SettleRequest(BaseModel):
    source_type: str = Field(..., description="CUSTOMS_GATEWAY | KAAS | ESCROW | LABOR")
    gross_amount: float = Field(..., gt=0)
    client_id: str
    reference_id: Optional[str] = None
    api_calls: int = Field(default=1, ge=1)


class SplitDetail(BaseModel):
    split_type: str
    amount: float
    ratio: float
    routed_to: str
    evidence_hash: str


class SettleResponse(BaseModel):
    transaction_id: str
    source_type: str
    gross_amount: float
    energy_cost: float
    net_amount: float
    splits: list[SplitDetail]
    settled_at: str


@router.post(
    "/settle",
    response_model=SettleResponse,
    summary="รับรายได้และ split 60/40 อัตโนมัติ (P-03)",
)
async def settle(
    req: SettleRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    try:
        result = await settle_transaction(
            db,
            source_type=req.source_type,
            gross_amount=req.gross_amount,
            client_id=req.client_id,
            reference_id=req.reference_id,
            api_calls=req.api_calls,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid request parameters")


@router.get(
    "/ledger/{period}",
    summary="ดูสรุปรายรับรายจ่าย (YYYY-MM)",
)
async def ledger(
    period: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    return await get_ledger_summary(db, period)
