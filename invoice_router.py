"""
invoice_router.py
Phase 8.1 — Invoice Upload Endpoints

POST /v1/invoice/upload  — อัปโหลดไฟล์ → classify → บันทึก DB
GET  /v1/invoice/{id}    — ดูผลลัพธ์ตาม submission_id
GET  /v1/invoice/list    — รายการ submissions ของ client นี้
"""

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.security.api_key import APIKeyHeader

from invoice_parser import parse_invoice
from invoice_service import process_invoice
from db_adapter import get_pool

router = APIRouter(prefix="/v1/invoice", tags=["invoice"])

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".xlsx", ".xls", ".csv", ".webp"}


async def _get_client(api_key: str = Depends(API_KEY_HEADER)) -> str:
    if not api_key:
        raise HTTPException(status_code=401, detail="X-API-Key required")
    try:
        # auth ด้วย hint (8 ตัวสุดท้าย) — เหมือน billing._get_agent_by_key
        hint = api_key[-8:]
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM client_agents WHERE api_key_hint=$1 AND status='ACTIVE'",
                hint
            )
        if not row:
            raise HTTPException(status_code=401, detail="Invalid API Key")
        return api_key
    except HTTPException:
        raise
    except Exception as e:
        print(f"[invoice_router] auth error: {e}")
        raise HTTPException(status_code=500, detail=f"Auth error: {str(e)[:100]}")


# ─── POST /v1/invoice/upload ──────────────────────────────────────────────────

@router.post("/upload")
async def upload_invoice(
    file: UploadFile = File(...),
    client_key: str = Depends(_get_client)
):
    """
    อัปโหลด invoice (PDF/Image/Excel/CSV)
    → parse → classify ทุก item → บันทึก DB → คืนสรุปทั้งใบ
    """
    # ตรวจ extension
    filename = file.filename or "invoice"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"ไฟล์ประเภท {ext} ไม่รองรับ รองรับ: PDF, JPG, PNG, XLSX, CSV"
        )

    # อ่านไฟล์
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="ไฟล์ใหญ่เกิน 10MB")
    if not content:
        raise HTTPException(status_code=400, detail="ไฟล์ว่างเปล่า")

    # Parse
    parsed = await parse_invoice(filename, content)
    if "error" in parsed:
        raise HTTPException(status_code=422, detail=f"อ่านไฟล์ไม่ได้: {parsed['error']}")

    items = parsed.get("items") or []
    if not items:
        raise HTTPException(status_code=422, detail="ไม่พบรายการสินค้าในเอกสาร")

    # Process + classify
    result = await process_invoice(client_key, filename, parsed)

    return {
        "success": True,
        "data": result
    }


# ─── GET /v1/invoice/{submission_id} ─────────────────────────────────────────

@router.get("/{submission_id}")
async def get_invoice_result(
    submission_id: str,
    client_key: str = Depends(_get_client)
):
    """ดูผลลัพธ์ของ submission ที่ระบุ"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        sub = await conn.fetchrow(
            "SELECT * FROM invoice_submissions WHERE id=$1 AND client_api_key=$2",
            submission_id, client_key
        )
        if not sub:
            raise HTTPException(status_code=404, detail="ไม่พบ submission นี้")

        items = await conn.fetch(
            "SELECT * FROM invoice_items WHERE submission_id=$1 ORDER BY line_no",
            submission_id
        )

    return {
        "success": True,
        "data": {
            "submission": dict(sub),
            "items": [dict(i) for i in items]
        }
    }


# ─── GET /v1/invoice/list ─────────────────────────────────────────────────────

@router.get("/list/all")
async def list_invoices(
    client_key: str = Depends(_get_client),
    limit: int = 20,
    offset: int = 0
):
    """รายการ invoice submissions ของ client นี้"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, filename, file_type, invoice_no, invoice_date,
                   seller_country, buyer_country, total_value, item_count,
                   status, created_at
            FROM invoice_submissions
            WHERE client_api_key=$1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """, client_key, limit, offset)

    return {
        "success": True,
        "data": [dict(r) for r in rows],
        "limit": limit,
        "offset": offset
    }
