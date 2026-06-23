"""
invoice_parser.py
Phase 8.1 — Invoice Upload Channel
อ่านไฟล์ PDF / Image / Excel / CSV → structured JSON

รองรับ:
- PDF (text)   → pdfplumber
- PDF (scanned)→ ส่งให้ Claude Vision
- Image        → ส่งให้ Claude Vision
- Excel/XLSX   → openpyxl / pandas
- CSV          → pandas
"""

import io
import os
import json
import base64
from typing import Optional

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


# ─── Detect file type ────────────────────────────────────────────────────────

def detect_file_type(filename: str, content: bytes) -> str:
    """คืน PDF_TEXT / PDF_SCAN / IMAGE / EXCEL / CSV"""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext in ("jpg", "jpeg", "png", "webp", "gif", "bmp"):
        return "IMAGE"
    if ext in ("xlsx", "xls"):
        return "EXCEL"
    if ext == "csv":
        return "CSV"
    if ext == "pdf" or content[:4] == b"%PDF":
        # ลอง extract text ดูก่อน ถ้ามีข้อความพอ = PDF_TEXT ไม่งั้น = PDF_SCAN
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                text = " ".join(
                    (p.extract_text() or "") for p in pdf.pages[:3]
                )
            return "PDF_TEXT" if len(text.strip()) > 100 else "PDF_SCAN"
        except Exception:
            return "PDF_SCAN"
    return "UNKNOWN"


# ─── Extract raw text ─────────────────────────────────────────────────────────

def extract_text_from_pdf(content: bytes) -> str:
    """pdfplumber → raw text ทุกหน้า"""
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                # ลอง extract table ด้วย
                tables = page.extract_tables() or []
                for table in tables:
                    for row in table:
                        if row:
                            parts.append(" | ".join(str(c or "") for c in row))
                if text:
                    parts.append(text)
        return "\n".join(parts)
    except ImportError:
        return ""
    except Exception as e:
        return f"[PDF parse error: {e}]"


def extract_text_from_excel(content: bytes, filename: str) -> str:
    """openpyxl (raw cell values) + pandas fallback — คืน text ที่ Claude อ่านได้ดี"""
    if filename.lower().endswith(".csv"):
        try:
            import pandas as pd
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8", errors="replace")
            return df.to_string(index=False)
        except Exception as e:
            return f"[CSV parse error: {e}]"

    # Excel — อ่านด้วย openpyxl แบบ raw (ได้ทุก cell รวม merged)
    try:
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(content), data_only=True)
        lines = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            lines.append(f"=== Sheet: {sheet_name} ===")
            for row in ws.iter_rows(values_only=True):
                row_vals = [str(v).strip() if v is not None else "" for v in row]
                # ข้ามแถวว่างทั้งหมด
                if any(v for v in row_vals):
                    lines.append("\t".join(row_vals))
        return "\n".join(lines)
    except ImportError:
        pass
    except Exception as e:
        pass

    # Fallback pandas
    try:
        import pandas as pd
        xl = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None)
        parts = []
        for name, df in xl.items():
            parts.append(f"=== Sheet: {name} ===")
            parts.append(df.fillna("").to_string(index=False, header=False))
        return "\n".join(parts)
    except Exception as e:
        return f"[Excel parse error: {e}]"


def image_to_base64(content: bytes) -> str:
    return base64.b64encode(content).decode()


# ─── Claude Vision / Text extraction ─────────────────────────────────────────

EXTRACTION_PROMPT = """You are an expert customs document reader. Extract ALL information from this commercial invoice.

Return a JSON object with this exact structure:
{
  "invoice_no": "string or null",
  "invoice_date": "YYYY-MM-DD or null",
  "seller_name": "string or null",
  "seller_country": "ISO 2-letter code or null",
  "buyer_name": "string or null",
  "buyer_country": "ISO 2-letter code or null",
  "incoterms": "FOB/CIF/EXW/DDP/etc or null",
  "currency": "USD/THB/CNY/EUR/etc or null",
  "items": [
    {
      "line_no": 1,
      "description": "exact product description from invoice",
      "hs_code_declared": "HS code if shown, else null",
      "qty": number or null,
      "unit": "KG/PCS/CARTON/CBM/L/etc or null",
      "unit_price": number or null,
      "line_value": number or null,
      "country_origin": "ISO 2-letter or null",
      "marks_numbers": "string or null"
    }
  ]
}

Rules:
- Extract ALL line items, do not skip any
- Use null for missing fields, never guess
- description must be verbatim from the document
- Return ONLY the JSON, no explanation"""


async def extract_with_claude_vision(content: bytes, file_type: str) -> dict:
    """ส่งรูปภาพ/PDF scan ให้ Claude Vision อ่าน"""
    if not ANTHROPIC_API_KEY:
        return {"error": "ANTHROPIC_API_KEY not set"}
    try:
        import httpx

        media_type = "image/jpeg"
        if file_type == "PDF_SCAN":
            try:
                from pdf2image import convert_from_bytes
                images = convert_from_bytes(content, first_page=1, last_page=3)
                img_io = io.BytesIO()
                images[0].save(img_io, format="JPEG")
                content = img_io.getvalue()
                media_type = "image/jpeg"
            except ImportError:
                media_type = "application/pdf"

        b64 = image_to_base64(content)
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 4096,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                            {"type": "text", "text": EXTRACTION_PROMPT}
                        ]
                    }]
                }
            )
            resp.raise_for_status()
            data = resp.json()
        raw = data["content"][0]["text"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        return {"error": str(e)}


async def extract_with_claude_text(raw_text: str) -> dict:
    """ส่ง raw text ให้ Claude สกัด structured JSON"""
    if not ANTHROPIC_API_KEY:
        return {"error": "ANTHROPIC_API_KEY not set"}
    try:
        import httpx
        prompt = EXTRACTION_PROMPT + f"\n\nDocument text:\n{raw_text[:8000]}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            resp.raise_for_status()
            data = resp.json()
        raw = data["content"][0]["text"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        return {"error": str(e)}


# ─── Main parse function ──────────────────────────────────────────────────────

async def parse_invoice(filename: str, content: bytes) -> dict:
    """
    Entry point — ส่ง filename + bytes → คืน structured dict พร้อม raw_text
    {
      file_type, raw_text,
      invoice_no, invoice_date,
      seller_name, seller_country,
      buyer_name, buyer_country,
      incoterms, currency,
      items: [ {...} ]
    }
    """
    file_type = detect_file_type(filename, content)
    raw_text = ""
    extracted = {}

    if file_type == "PDF_TEXT":
        raw_text = extract_text_from_pdf(content)
        extracted = await extract_with_claude_text(raw_text)

    elif file_type in ("PDF_SCAN", "IMAGE"):
        extracted = await extract_with_claude_vision(content, file_type)
        raw_text = json.dumps(extracted, ensure_ascii=False)

    elif file_type in ("EXCEL", "CSV"):
        raw_text = extract_text_from_excel(content, filename)
        extracted = await extract_with_claude_text(raw_text)

    else:
        return {"error": f"Unsupported file type: {filename}", "file_type": "UNKNOWN"}

    if "error" in extracted:
        return {"error": extracted["error"], "file_type": file_type, "raw_text": raw_text}

    extracted["file_type"] = file_type
    extracted["raw_text"] = raw_text[:5000]  # เก็บแค่ 5000 chars
    return extracted
