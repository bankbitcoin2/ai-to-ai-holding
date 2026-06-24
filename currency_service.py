"""
currency_service.py — Phase 17: Exchange Rate Service
AI TO AI HOLDING — Customs Intelligence Division

ดึงอัตราแลกเปลี่ยนจาก exchangerate-api.com (free tier: 1,500 req/mo)
Cache in-memory 1 ชั่วโมง — ลด API call
รองรับ: USD, THB, CNY, JPY, EUR, KRW, SGD, MYR, VND, IDR

Usage:
    rate = await get_rate("USD", "THB")        # 1 USD = ? THB
    converted = await convert(100, "USD", "THB")  # 100 USD → THB
    snapshot = await get_rate_snapshot()         # ทุกสกุลเทียบ USD
"""

import os
import time
import asyncio
from typing import Optional

import httpx

# ── Config ─────────────────────────────────────────────────────────────────────

# Free tier: https://open.er-api.com/v6/latest/USD (no key needed, 1,500/mo)
# Paid tier: https://v6.exchangerate-api.com/v6/{KEY}/latest/USD
_ER_API_KEY = os.getenv("EXCHANGERATE_API_KEY", "")
_BASE_URL = (
    f"https://v6.exchangerate-api.com/v6/{_ER_API_KEY}/latest"
    if _ER_API_KEY
    else "https://open.er-api.com/v6/latest"
)

# สกุลเงินที่สนใจ (ASEAN trade + major)
SUPPORTED_CURRENCIES = [
    "USD", "THB", "CNY", "JPY", "EUR", "KRW",
    "SGD", "MYR", "VND", "IDR", "TWD", "HKD", "GBP", "AUD",
]

# Cache TTL: 1 ชั่วโมง (exchange rate ไม่เปลี่ยนทุกวินาที)
_CACHE_TTL = 3600
_cache: dict = {}       # {base_currency: {"rates": {...}, "fetched_at": float}}
_cache_lock = asyncio.Lock()


# ── Core Functions ─────────────────────────────────────────────────────────────

async def get_rate(from_currency: str, to_currency: str) -> Optional[float]:
    """
    ดึงอัตราแลกเปลี่ยน 1 from_currency = ? to_currency
    คืน None ถ้าดึงไม่ได้
    """
    fr = from_currency.upper().strip()
    to = to_currency.upper().strip()
    if fr == to:
        return 1.0

    rates = await _get_cached_rates(fr)
    if rates and to in rates:
        return rates[to]

    # Fallback: ดึงผ่าน USD cross rate
    if fr != "USD":
        usd_rates = await _get_cached_rates("USD")
        if usd_rates and fr in usd_rates and to in usd_rates:
            return usd_rates[to] / usd_rates[fr]

    return None


async def convert(amount: float, from_currency: str, to_currency: str) -> Optional[float]:
    """แปลงจำนวนเงินจากสกุลหนึ่งเป็นอีกสกุล"""
    rate = await get_rate(from_currency, to_currency)
    if rate is None:
        return None
    return round(amount * rate, 4)


async def get_rate_snapshot(base: str = "USD") -> dict:
    """
    ดึง snapshot อัตราแลกเปลี่ยนทุกสกุลเทียบ base
    คืน: {"base": "USD", "rates": {"THB": 34.5, ...}, "fetched_at": "...", "source": "..."}
    """
    base = base.upper().strip()
    rates = await _get_cached_rates(base)
    cached = _cache.get(base, {})

    if not rates:
        return {
            "base": base,
            "rates": {},
            "fetched_at": None,
            "source": "unavailable",
            "error": "ไม่สามารถดึงอัตราแลกเปลี่ยนได้",
        }

    # กรองเฉพาะสกุลที่สนใจ
    filtered = {k: round(v, 6) for k, v in rates.items() if k in SUPPORTED_CURRENCIES}

    return {
        "base": base,
        "rates": filtered,
        "fetched_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(cached.get("fetched_at", 0))
        ),
        "source": "exchangerate-api.com",
        "cache_ttl_seconds": _CACHE_TTL,
    }


async def record_transaction_rate(from_currency: str, to_currency: str) -> dict:
    """
    บันทึก exchange rate ณ เวลาทำรายการ — สำหรับแนบไปกับ invoice/billing
    คืน dict ที่เก็บลง DB ได้เลย
    """
    rate = await get_rate(from_currency, to_currency)
    return {
        "from_currency": from_currency.upper(),
        "to_currency": to_currency.upper(),
        "rate": rate,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "exchangerate-api.com" if rate else "unavailable",
    }


# ── Internal: Cache + Fetch ────────────────────────────────────────────────────

async def _get_cached_rates(base: str) -> Optional[dict]:
    """ดึง rates จาก cache หรือ fetch ใหม่ถ้า expired"""
    async with _cache_lock:
        cached = _cache.get(base)
        now = time.time()
        if cached and (now - cached["fetched_at"]) < _CACHE_TTL:
            return cached["rates"]

    # Cache miss หรือ expired → fetch
    rates = await _fetch_rates(base)
    if rates:
        async with _cache_lock:
            _cache[base] = {"rates": rates, "fetched_at": time.time()}
    return rates


async def _fetch_rates(base: str) -> Optional[dict]:
    """เรียก API จริง — มี retry 1 ครั้ง"""
    url = f"{_BASE_URL}/{base}"
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    rates = data.get("rates") or data.get("conversion_rates")
                    if rates:
                        return rates
                print(f"[CURRENCY] API returned {resp.status_code} for {base}")
        except Exception as e:
            print(f"[CURRENCY] Fetch error (attempt {attempt+1}): {e}")
            if attempt == 0:
                await asyncio.sleep(1)
    return None


# ── Fallback Rates (ใช้เมื่อ API ล่ม) ──────────────────────────────────────────

_FALLBACK_USD = {
    "THB": 35.0, "CNY": 7.25, "JPY": 155.0, "EUR": 0.92,
    "KRW": 1380.0, "SGD": 1.35, "MYR": 4.70, "VND": 25400.0,
    "IDR": 16200.0, "TWD": 32.5, "HKD": 7.82, "GBP": 0.79, "AUD": 1.55,
}


async def get_rate_with_fallback(from_currency: str, to_currency: str) -> tuple[float, str]:
    """
    ดึง rate พร้อม source label — ใช้ fallback ถ้า API ล่ม
    คืน (rate, source) เช่น (35.0, "live") หรือ (35.0, "fallback")
    """
    rate = await get_rate(from_currency, to_currency)
    if rate is not None:
        return rate, "live"

    # Fallback: cross-rate ผ่าน USD
    fr = from_currency.upper()
    to = to_currency.upper()
    if fr == "USD" and to in _FALLBACK_USD:
        return _FALLBACK_USD[to], "fallback"
    if to == "USD" and fr in _FALLBACK_USD:
        return round(1.0 / _FALLBACK_USD[fr], 6), "fallback"
    if fr in _FALLBACK_USD and to in _FALLBACK_USD:
        return round(_FALLBACK_USD[to] / _FALLBACK_USD[fr], 6), "fallback"

    return 1.0, "unknown"
