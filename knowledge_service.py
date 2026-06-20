"""
knowledge_service.py
Knowledge Service — Bridge ชุด B ↔ ชุด A

วางที่: AI_TO_AI_HOLDING/knowledge_service.py

หน้าที่: เรียก Engine จริงทั้งหมดของชุด A
  - tax_engine      → อัตราภาษี + FTA จาก IGTF
  - restricted_engine → OGA / ใบอนุญาต
  - halal_engine    → 21 ประเทศ Halal (offline)
  - glossary        → คลังศัพท์การค้า (offline)
"""
import sys
from pathlib import Path
from typing import Optional

# ── ชี้ path ไปที่ root (ชุด A อยู่ที่ root = พ่อของโฟลเดอร์นี้) ──────────────
# AI_TO_AI_HOLDING/knowledge_service.py → parent = AI_TO_AI_HOLDING → parent = root
_ROOT = Path(__file__).resolve().parent.parent  # e:\ส่วนตัว2\Ai_to_Ai_CEO\
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Import ชุด A ──────────────────────────────────────────────────────────────
try:
    import tax_engine
    import restricted_engine
    import halal_engine
    import glossary
    _OK = True
except ImportError as _err:
    _OK = False
    _ERR = str(_err)

import httpx

CKAN_BASE = "https://catalog.customs.go.th/api/3/action"
HS_4DIGIT_RESOURCE = "b65e3b9e-6189-4869-b3fc-b8383e639d38"


# ── CKAN: ดึง HS Candidates ───────────────────────────────────────────────────
async def fetch_hs_candidates(keywords: list[str], limit: int = 12) -> list[dict]:
    """ค้น HS Code 4 หลักจาก CKAN กรมศุลกากร (ฟรี)"""
    seen, results = set(), []
    async with httpx.AsyncClient(timeout=15.0) as client:
        for kw in keywords:
            if len(results) >= limit:
                break
            try:
                r = await client.get(
                    f"{CKAN_BASE}/datastore_search",
                    params={"resource_id": HS_4DIGIT_RESOURCE, "q": kw, "limit": 6},
                )
                data = r.json()
                if not data.get("success"):
                    continue
                for rec in data["result"].get("records", []):
                    code = str(rec.get("trfsec", "")).strip().zfill(4)
                    if code not in seen:
                        seen.add(code)
                        results.append({"hs_code": code, "description": rec.get("secdsc", "")})
            except Exception:
                continue
    return results[:limit]


# ── Glossary fast-path ────────────────────────────────────────────────────────
def search_glossary(product_name: str) -> Optional[dict]:
    """ค้นคลังศัพท์ ถ้าเจอ = ข้าม Claude ประหยัด token"""
    if not _OK:
        return None
    try:
        return glossary.lookup_product(product_name)
    except Exception:
        return None


# ── Tax / FTA ─────────────────────────────────────────────────────────────────
def lookup_tax_rate(hs_code: str, origin_country: Optional[str]) -> dict:
    """ดึงอัตราภาษีจริงจาก tax_engine + igtf_loader"""
    if not _OK or not hs_code:
        return {"status": "unavailable"}
    try:
        tax_engine.reload_store()
        result = tax_engine.lookup_tax(hs_code, origin_country)
        # ถ้าไม่มีในคลัง → ลอง lazy-load จาก IGTF
        if result.get("status") == "no_data":
            try:
                import igtf_loader
                igtf_loader.load_heading(hs_code[:4])
                tax_engine.reload_store()
                result = tax_engine.lookup_tax(hs_code, origin_country)
            except Exception:
                pass
        return result
    except Exception as e:
        return {"status": "error", "note": str(e)}


# ── OGA / Restricted ──────────────────────────────────────────────────────────
def check_restricted(hs_code: str) -> dict:
    """ตรวจ OGA / ของต้องกำกัดจาก restricted_engine"""
    if not _OK or not hs_code:
        return {"status": "unavailable", "is_restricted": False}
    try:
        restricted_engine.reload_store()
        return restricted_engine.lookup_restricted(hs_code)
    except Exception as e:
        return {"status": "error", "note": str(e), "is_restricted": False}


# ── Halal ─────────────────────────────────────────────────────────────────────
def check_halal(hs_code: str, destination_country: Optional[str]) -> dict:
    """ตรวจ Halal 21 ประเทศ (offline ฟรี)"""
    if not _OK or not hs_code:
        return {"halal_required": False, "risk_level": "UNKNOWN"}
    try:
        return halal_engine.check(hs_code, destination_country)
    except Exception as e:
        return {"halal_required": False, "risk_level": "ERROR", "note": str(e)}


# ── Status ────────────────────────────────────────────────────────────────────
def status() -> dict:
    if not _OK:
        return {"status": "DEGRADED", "error": _ERR, "root": str(_ROOT)}
    engines = {}
    try:
        tax_engine.reload_store()
        engines["tax_engine"] = "OK"
    except Exception as e:
        engines["tax_engine"] = f"ERROR:{e}"
    try:
        restricted_engine.reload_store()
        engines["restricted_engine"] = "OK"
    except Exception as e:
        engines["restricted_engine"] = f"ERROR:{e}"
    try:
        engines["halal_engine"] = f"OK ({len(halal_engine.list_halal_countries())} countries)"
    except Exception as e:
        engines["halal_engine"] = f"ERROR:{e}"
    try:
        g = glossary.lookup_product("battery")
        engines["glossary"] = f"OK (battery→{g['hs_hint'] if g else '?'})"
    except Exception as e:
        engines["glossary"] = f"ERROR:{e}"
    all_ok = all("OK" in v for v in engines.values())
    return {"status": "OK" if all_ok else "PARTIAL", "root": str(_ROOT), "engines": engines}
