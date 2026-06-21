"""
knowledge_service.py
Knowledge Service — Bridge ชุด B ↔ ชุด A

วางที่: AI_TO_AI_HOLDING/knowledge_service.py

หน้าที่: เรียก Engine จริงทั้งหมดของชุด A
  - tax_engine      → อัตราภาษี + FTA จาก IGTF
  - restricted_engine → OGA / ใบอนุญาต
  - halal_engine    → 21 ประเทศ Halal (offline)
  - glossary        → คลังศัพท์การค้า (offline)

⚠️ บน Railway (Production) ชุด A ไม่มีอยู่ในระบบ — _OK จะ False
   ระบบจะ fallback เป็น bundled engines โดยอัตโนมัติ ไม่ crash
"""
import sys
import os
from pathlib import Path
from typing import Optional

# ── ค้นหา root ของชุด A แบบ multi-path strategy ────────────────────────────────
_ROOT: Optional[Path] = None

_env_root = os.getenv("KNOWLEDGE_ROOT", "")
if _env_root and Path(_env_root).exists():
    _ROOT = Path(_env_root)
else:
    _candidate = Path(__file__).resolve().parent.parent
    if (_candidate / "tax_engine.py").exists():
        _ROOT = _candidate

if _ROOT and str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Import halal_engine — bundled ใน repo ────────────────────────────────────
try:
    import halal_engine as halal_engine
    _HALAL_OK = True
except ImportError:
    _HALAL_OK = False

# ── Import oga_engine — bundled ใน repo (ไม่ต้อง KNOWLEDGE_ROOT) ─────────────
try:
    import oga_engine as oga_engine
    _OGA_OK = True
except ImportError:
    _OGA_OK = False

# ── Import tax_engine_bundled — offline Thai Tariff HS2022 ───────────────────
try:
    import tax_engine_bundled as _tax_bundled
    _TAX_BUNDLED_OK = True
except ImportError:
    _tax_bundled = None  # type: ignore
    _TAX_BUNDLED_OK = False

# ── Import ชุด A — graceful fallback ถ้าไม่พบ KNOWLEDGE_ROOT ────────────────
try:
    if not _ROOT:
        raise ImportError("KNOWLEDGE_ROOT not found — running in MOCK mode")
    import tax_engine
    import restricted_engine
    import glossary
    _OK = True
    _ERR = ""
except ImportError as _err:
    _OK = False
    _ERR = str(_err)

import httpx

CKAN_BASE = "https://catalog.customs.go.th/api/3/action"
HS_4DIGIT_RESOURCE  = "b65e3b9e-6189-4869-b3fc-b8383e639d38"
HS_TARIFF_RESOURCE  = "3389251a-2240-4bc3-a797-53b82b99c767"

_TARIFF_FIELD_MAP: dict = {}


async def _probe_tariff_fields(client: httpx.AsyncClient) -> dict:
    global _TARIFF_FIELD_MAP
    if _TARIFF_FIELD_MAP:
        return _TARIFF_FIELD_MAP
    try:
        r = await client.get(
            f"{CKAN_BASE}/datastore_search",
            params={"resource_id": HS_TARIFF_RESOURCE, "limit": 1},
        )
        data = r.json()
        if data.get("success"):
            fields = {f["id"]: f.get("type","") for f in data["result"].get("fields", [])}
            records = data["result"].get("records", [])
            sample = records[0] if records else {}
            _TARIFF_FIELD_MAP = {"fields": fields, "sample": sample}
    except Exception:
        pass
    return _TARIFF_FIELD_MAP


async def fetch_hs_full(hs_code: str) -> dict:
    hs_digits = hs_code.replace(".", "").strip()
    async with httpx.AsyncClient(timeout=15.0) as client:
        probe = await _probe_tariff_fields(client)
        for q in [hs_digits, hs_digits[:6], hs_digits[:4]]:
            if not q:
                continue
            try:
                r = await client.get(
                    f"{CKAN_BASE}/datastore_search",
                    params={"resource_id": HS_TARIFF_RESOURCE, "q": q, "limit": 5},
                )
                data = r.json()
                if not data.get("success"):
                    continue
                for rec in data["result"].get("records", []):
                    rec_str = str(rec)
                    if hs_digits[:4] in rec_str:
                        return {
                            "found": True,
                            "raw_record": rec,
                            "probe_fields": list(probe.get("fields", {}).keys()),
                        }
            except Exception:
                continue
    return {"found": False, "probe_fields": list(_TARIFF_FIELD_MAP.get("fields", {}).keys())}


async def fetch_hs_candidates(keywords: list[str], limit: int = 12) -> list[dict]:
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
    if not _OK:
        return None
    try:
        return glossary.lookup_product(product_name)
    except Exception:
        return None


# ── Tax / FTA ─────────────────────────────────────────────────────────────────
def lookup_tax_rate(hs_code: str, origin_country: Optional[str]) -> dict:
    """
    ดึงอัตราภาษี ลำดับ:
    1. tax_engine (ชุด A — ข้อมูลเต็มจาก IGTF ถ้ามี KNOWLEDGE_ROOT)
    2. tax_engine_bundled (offline bundled Thai Tariff HS2022)
    """
    if not hs_code:
        return {"status": "unavailable"}

    # ── ลอง tax_engine (ชุด A) ก่อน ──
    if _OK:
        try:
            tax_engine.reload_store()
            result = tax_engine.lookup_tax(hs_code, origin_country)
            if result.get("status") == "no_data":
                try:
                    import igtf_loader
                    igtf_loader.load_heading(hs_code[:4])
                    tax_engine.reload_store()
                    result = tax_engine.lookup_tax(hs_code, origin_country)
                except Exception:
                    pass
            if result.get("status") not in ("error", "no_data", "unavailable"):
                return result
        except Exception:
            pass  # fallthrough to bundled

    # ── Fallback: tax_engine_bundled (ไม่ต้อง KNOWLEDGE_ROOT) ──
    if _TAX_BUNDLED_OK and _tax_bundled:
        try:
            return _tax_bundled.lookup_tax(hs_code, origin_country)
        except Exception as e:
            return {"status": "error", "note": str(e)}

    return {"status": "unavailable"}


# ── OGA / Restricted ──────────────────────────────────────────────────────────
def check_restricted(hs_code: str) -> dict:
    if not hs_code:
        return {"status": "unavailable", "is_restricted": False}
    if _OK:
        try:
            restricted_engine.reload_store()
            result = restricted_engine.lookup_restricted(hs_code)
            result["source"] = "RESTRICTED_ENGINE"
            return result
        except Exception:
            pass
    if _OGA_OK:
        try:
            result = oga_engine.check(hs_code)
            result["status"] = "ok"
            return result
        except Exception as e:
            return {"status": "error", "note": str(e), "is_restricted": False}
    return {"status": "unavailable", "is_restricted": False}


# ── Halal ─────────────────────────────────────────────────────────────────────
def check_halal(hs_code: str, destination_country: Optional[str]) -> dict:
    if not _HALAL_OK or not hs_code:
        return {"halal_required": False, "risk_level": "UNKNOWN"}
    try:
        return halal_engine.check(hs_code, destination_country)
    except Exception as e:
        return {"halal_required": False, "risk_level": "ERROR", "note": str(e)}


# ── Status ────────────────────────────────────────────────────────────────────
def status() -> dict:
    return {
        "status": "OK" if _OK else "MOCK",
        "halal_engine": "OK" if _HALAL_OK else "UNAVAILABLE",
        "oga_engine": "OK" if _OGA_OK else "UNAVAILABLE",
        "tax_engine_bundled": "OK" if _TAX_BUNDLED_OK else "UNAVAILABLE",
        "error": _ERR if not _OK else None,
        "root": str(_ROOT) if _ROOT else "NOT_FOUND",
    }


# ── HS Descriptions bundled (AHTN 2022, 12,247 codes) ─────────────────────────
try:
    import hs_descriptions_bundled as _hs_desc
    _HS_DESC_OK = True
except ImportError:
    _hs_desc = None  # type: ignore
    _HS_DESC_OK = False

# ── FTA Eligibility bundled (RCEP/ATIGA/AANZFTA/JTEPA, 14 countries) ─────────
try:
    import fta_eligibility_bundled as _fta_elig
    _FTA_ELIG_OK = True
except ImportError:
    _fta_elig = None  # type: ignore
    _FTA_ELIG_OK = False


def get_hs_description(hs_code: str) -> dict:
    """Return {'th': ..., 'en': ...} from bundled AHTN 2022 data. Empty strings if not found."""
    if _HS_DESC_OK and _hs_desc:
        try:
            r = _hs_desc.get_description(hs_code)
            if r:
                return r
        except Exception:
            pass
    return {"th": None, "en": None}


def get_fta_form(hs_code: str, origin_country: str) -> dict:
    """
    Return FTA form info for hs_code from origin_country.
    {'eligible': True, 'form': 'FORM RCEP', 'all_eligible': [...]}
    """
    if _FTA_ELIG_OK and _fta_elig:
        try:
            form = _fta_elig.get_fta_form(hs_code, origin_country)
            eligible_all = _fta_elig.get_eligible_countries(hs_code)
            return {
                "eligible": form is not None,
                "form": form,
                "all_eligible_countries": [c for c, _ in eligible_all],
            }
        except Exception:
            pass
    return {"eligible": False, "form": None, "all_eligible_countries": []}
