"""
agents_router.py
GET /v1/agents/status  — สถานะ classify engine ปัจจุบัน
GET /v1/agents/config  — ค่า config ที่กำลังใช้งาน (Chairman only)
"""
import os
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/v1/agents", tags=["agents"])

# ── selector (backward compat) ────────────────────────────────────────────────
from holding_config import MOCK_MODE

if MOCK_MODE:
    from mock_classification_agent import classify_item, ClassificationResult
else:
    from classification_agent import classify_item, ClassificationResult

__all__ = ["classify_item", "ClassificationResult", "router"]


# ── helpers ───────────────────────────────────────────────────────────────────

def _chairman_key() -> str:
    return os.getenv("CHAIRMAN_KEY", "")


def _check_chairman(req: Request):
    key = req.headers.get("x-chairman-key", "")
    ck  = _chairman_key()
    if not ck or key != ck:
        raise HTTPException(403, detail={"error": "FORBIDDEN",
                                         "message": "x-chairman-key required"})


# ── GET /v1/agents/status ─────────────────────────────────────────────────────

@router.get("/status", summary="สถานะ Classify Engine — public info")
async def agents_status():
    """
    คืนสถานะ classify engine ที่กำลังใช้อยู่
    ไม่ต้องมี API Key — เหมาะสำหรับ health check / monitoring
    """
    from holding_config import MOCK_MODE as _mock
    engine      = "mock" if _mock else "claude"
    api_key_set = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())

    # ดึง cache stats (non-blocking)
    cache_info: dict = {}
    try:
        from cache_classification import cache_stats
        cache_info = await cache_stats()
    except Exception:
        pass

    # ดึง normalize rule count
    try:
        from normalize_description import _COMPOUNDS, _SINGLES
        normalize_rules = len(_COMPOUNDS) + len(_SINGLES)
    except Exception:
        normalize_rules = 0

    return {
        "engine":          engine,
        "api_key_set":     api_key_set,
        "engines_loaded": {
            "halal":    True,
            "oga":      True,
            "tax":      True,
            "fta":      True,
            "normalize_rules": normalize_rules,
        },
        "cache": {
            "total_cached":          cache_info.get("total_cached", 0),
            "confirmed":             cache_info.get("confirmed", 0),
            "pending_feedback_queue": cache_info.get("pending_feedback_queue", 0),
        },
        "thresholds": {
            "confidence_min":  0.75,
            "cache_save_min":  0.85,
            "max_candidates":  5,
        },
    }


# ── GET /v1/agents/config ─────────────────────────────────────────────────────

@router.get("/config", summary="ค่า config ทั้งหมด — Chairman only")
async def agents_config(req: Request):
    """
    คืน config ทั้งหมดที่ระบบ classify ใช้อยู่
    ต้องใช้ x-chairman-key
    """
    _check_chairman(req)

    from holding_config import (
        MOCK_MODE as _mock,
        PRICE_PER_ITEM,
        SANDBOX_ITEM_LIMIT,
        LOW_CONFIDENCE_THRESHOLD,
        ALLOWED_ORIGINS,
    )

    db_url_set  = bool(os.getenv("DATABASE_URL", "").strip())
    stripe_set  = bool(os.getenv("STRIPE_SECRET_KEY", "").strip())
    api_key_set = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    chair_key   = bool(_chairman_key())

    # Cache top hits
    top_hits: list = []
    cache_info: dict = {}
    try:
        from cache_classification import cache_stats
        cache_info = await cache_stats()
        top_hits   = cache_info.get("top_hits", [])
    except Exception:
        pass

    return {
        "mode":    "mock" if _mock else "real",
        "env": {
            "DATABASE_URL":       "set" if db_url_set else "NOT SET",
            "ANTHROPIC_API_KEY":  "set" if api_key_set else "NOT SET",
            "STRIPE_SECRET_KEY":  "set" if stripe_set else "NOT SET",
            "CHAIRMAN_KEY":       "set" if chair_key else "NOT SET",
            "PRICE_PER_ITEM":     PRICE_PER_ITEM,
            "SANDBOX_ITEM_LIMIT": SANDBOX_ITEM_LIMIT,
            "LOW_CONF_THRESHOLD": LOW_CONFIDENCE_THRESHOLD,
            "ALLOWED_ORIGINS":    ALLOWED_ORIGINS,
        },
        "classify": {
            "engine":             "mock" if _mock else "claude-3-5-haiku",
            "confidence_min":     0.75,
            "cache_save_min":     0.85,
            "max_candidates":     5,
            "parallel_semaphore": 5,
        },
        "cache_summary": {
            "total_cached":           cache_info.get("total_cached", 0),
            "confirmed":              cache_info.get("confirmed", 0),
            "pending_feedback_queue": cache_info.get("pending_feedback_queue", 0),
        },
        "cache_top_hits": top_hits[:5],
    }
