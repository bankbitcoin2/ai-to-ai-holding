"""
api/customs.py
Customs Intelligence API — Revenue Pillar 1: The Customs Gateway
Endpoint ที่ client AI agent เรียกใช้เพื่อจำแนกสินค้าและคำนวณภาษี
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import aiosqlite

from database import get_db
from customs_service import process_invoice

router = APIRouter(prefix="/v1/customs", tags=["Customs Intelligence"])


# ============================================================
# Request / Response Models
# ============================================================

class InvoiceItem(BaseModel):
    description: str = Field(..., description="คำบรรยายสินค้าจาก invoice")
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    origin_country: Optional[str] = Field(None, description="ISO 3166-1 alpha-2 เช่น CN, JP, US")


class ClassifyInvoiceRequest(BaseModel):
    client_id: str = Field(..., description="Identifier ของ client AI agent")
    invoice_number: Optional[str] = None
    seller_name: Optional[str] = None
    seller_country: Optional[str] = Field(None, description="ISO 3166-1 alpha-2")
    buyer_name: Optional[str] = None
    buyer_country: Optional[str] = Field(None, description="ISO 3166-1 alpha-2")
    invoice_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    currency: str = Field(default="USD")
    items: list[InvoiceItem] = Field(..., min_length=1, description="รายการสินค้าใน invoice")


class ClassifiedItem(BaseModel):
    line_number: int
    description: str
    hs_code: Optional[str]
    hs_description: Optional[str]
    confidence_score: float
    source_reference: str
    duty_rate: float
    duty_amount: Optional[float]
    vat_rate: float
    vat_amount: Optional[float]
    oga_required: bool
    oga_agencies: list[str]
    notes: Optional[str]


class InvoiceSummary(BaseModel):
    total_items: int
    total_duty_estimate: float
    currency: str
    avg_confidence: float
    oga_flagged: int


class ClassifyInvoiceResponse(BaseModel):
    case_id: str
    invoice_id: str
    status: str
    items: list[ClassifiedItem]
    summary: InvoiceSummary


# ============================================================
# Endpoints
# ============================================================

@router.post(
    "/classify",
    response_model=ClassifyInvoiceResponse,
    summary="จำแนก HS Code และคำนวณภาษีสำหรับ invoice",
    description="""
    รับ invoice พร้อมรายการสินค้า → จำแนก HS Code ทุก item โดย Classification Agent
    → คำนวณ duty และ VAT → ตรวจสอบ OGA → คืนผลพร้อม Confidence Score และ Source Reference
    
    ทุก transaction บันทึกใน Evidence Chain อัตโนมัติ (P-04)
    """,
)
async def classify_invoice(
    request: ClassifyInvoiceRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    if not request.items:
        raise HTTPException(status_code=400, detail="Invoice must have at least one item")

    result = await process_invoice(
        db,
        client_id=request.client_id,
        invoice_number=request.invoice_number,
        seller_name=request.seller_name,
        seller_country=request.seller_country,
        buyer_name=request.buyer_name,
        buyer_country=request.buyer_country,
        invoice_date=request.invoice_date,
        currency=request.currency,
        items=[item.model_dump() for item in request.items],
    )

    return result


@router.get(
    "/case/{case_id}",
    summary="ดูผลการจำแนกของ case ที่ผ่านมา",
)
async def get_case(
    case_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    rows = await db.execute_fetchall(
        """
        SELECT ci.*, ii.*
        FROM customs_invoices ci
        JOIN customs_invoice_items ii ON ii.invoice_id = ci.id
        WHERE ci.case_id = ?
        ORDER BY ii.line_number
        """,
        (case_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Case not found")

    return {"case_id": case_id, "items": [dict(r) for r in rows]}
