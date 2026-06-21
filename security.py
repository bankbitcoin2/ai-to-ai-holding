"""
security.py
Security Layer — API Key Auth + IP Allowlist + Rate Limiting

อุดช่องโหว่:
  [FIX-2] API Key บังคับทุก endpoint ที่ไม่ใช่ public
  [FIX-3] IP Allowlist ป้องกัน Chairman endpoints (เฉพาะเมื่อ CHAIRMAN_ALLOWED_IPS ตั้งค่า)
  [FIX-6] Rate Limiting แบบ Sliding Window — ไม่ต้อง pip install เพิ่ม

การตั้งค่าผ่าน Environment Variables:
  API_KEYS              = key1,key2,key3        (จำเป็น — ต้องตั้งใน production)
  CHAIRMAN_ALLOWED_IPS  = 1.2.3.4,5.6.7.8      (optional — ถ้าไม่ตั้ง = ไม่ restrict IP)
  RATE_LIMIT_GLOBAL     = 60                    (request/นาที ต่อ IP, default 60)
  RATE_LIMIT_CHAIRMAN   = 30                    (request/นาที สำหรับ /v1/chairman/*, default 30)
  RATE_LIMIT_SANDBOX    = 20                    (request/นาที สำหรับ /sandbox/*, default 20)

Public endpoints (ไม่ต้อง X-API-Key):
  GET  /health
  GET  /
  GET  /docs
  POST /v1/sandbox/*       Free trial
  ANY  /v1/chairman/*      Chairman auth ทำใน chairman_router ด้วย x-chairman-key
  POST /v1/register        Client signup
  ANY  /v1/billing/*       Billing auth ทำใน billing.py
  ANY  /.well-known/*      AI discovery
  ANY  /chairman*          Chairman Office HTML
  ANY  /static/*           Static assets
"""

import os
import secrets
import time
import asyncio
from collections import defaultdict, deque
from typing import Optional
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


# ══════════════════════════════════════════════════════════════
# Section 1 — API Key Store
# ══════════════════════════════════════════════════════════════

_raw_keys = os.getenv("API_KEYS", "")
_VALID_KEYS: set = set(k.strip() for k in _raw_keys.split(",") if k.strip())

_DEV_KEY: Optional[str] = None
if not _VALID_KEYS:
    _DEV_KEY = secrets.token_urlsafe(32)
    _VALID_KEYS.add(_DEV_KEY)
    print(f"""
╔══════════════════════════════════════════════════════════╗
║  WARNING: API_KEYS not set in environment                ║
║  Temporary dev key (NOT for production):                 ║
║  X-API-Key: {_DEV_KEY:<44}║
║  Set API_KEYS=<your-key> in .env before going live       ║
╚══════════════════════════════════════════════════════════╝
""")


def is_valid_api_key(key: Optional[str]) -> bool:
    if not key:
        return False
    return any(secrets.compare_digest(key, valid) for valid in _VALID_KEYS)


# ══════════════════════════════════════════════════════════════
# Section 2 — Chairman IP Allowlist (optional)
# ══════════════════════════════════════════════════════════════

_raw_ips = os.getenv("CHAIRMAN_ALLOWED_IPS", "")
# ถ้าไม่ตั้ง CHAIRMAN_ALLOWED_IPS = ไม่ restrict (ปล่อย chairman_router จัดการ auth เอง)
_IP_RESTRICT_ENABLED = bool(_raw_ips.strip())
CHAIRMAN_ALLOWED_IPS: set = set(ip.strip() for ip in _raw_ips.split(",") if ip.strip())


def get_real_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def is_chairman_ip_allowed(request: Request) -> bool:
    if not _IP_RESTRICT_ENABLED:
        return True
    return get_real_ip(request) in CHAIRMAN_ALLOWED_IPS


# ══════════════════════════════════════════════════════════════
# Section 3 — Sliding Window Rate Limiter
# ══════════════════════════════════════════════════════════════

class SlidingWindowLimiter:
    def __init__(self, max_requests: int, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, key: str, label: str = "endpoint"):
        async with self._lock:
            now = time.monotonic()
            window_start = now - self.window_seconds
            dq = self._buckets[key]
            while dq and dq[0] < window_start:
                dq.popleft()
            if len(dq) >= self.max_requests:
                oldest = dq[0]
                retry_after = int(oldest + self.window_seconds - now) + 1
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "RATE_LIMIT_EXCEEDED",
                        "message": f"Too many requests to {label} — retry after {retry_after}s",
                        "retry_after_seconds": retry_after,
                        "limit": f"{self.max_requests} req/{self.window_seconds}s per IP",
                    },
                    headers={"Retry-After": str(retry_after)},
                )
            dq.append(now)

    def cleanup_old_keys(self):
        now = time.monotonic()
        cutoff = now - self.window_seconds
        dead = [k for k, dq in self._buckets.items() if not dq or dq[-1] < cutoff]
        for k in dead:
            del self._buckets[k]


_global_limit   = int(os.getenv("RATE_LIMIT_GLOBAL",   "60"))
_chairman_limit = int(os.getenv("RATE_LIMIT_CHAIRMAN", "30"))
_sandbox_limit  = int(os.getenv("RATE_LIMIT_SANDBOX",  "20"))

limiter_global   = SlidingWindowLimiter(_global_limit,   60)
limiter_chairman = SlidingWindowLimiter(_chairman_limit, 60)
limiter_sandbox  = SlidingWindowLimiter(_sandbox_limit,  60)


# ══════════════════════════════════════════════════════════════
# Section 4 — Security Middleware
# ══════════════════════════════════════════════════════════════

PUBLIC_PATHS: set = {
    "/",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/dashboard",
    "/favicon.ico",
}

# Paths ที่ bypass X-API-Key check (แต่ยัง rate-limited)
# /v1/chairman/ — bypass SecurityMiddleware auth, chairman_router จัดการเอง
PUBLIC_PREFIXES: tuple = (
    "/v1/sandbox/",
    "/v1/chairman/",
    "/v1/register",
    "/v1/recover-key",
    "/v1/billing/",
    "/.well-known/",
    "/chairman",
    "/static/",
)

CHAIRMAN_PREFIX = "/v1/chairman/"


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        client_ip = get_real_ip(request)

        # ── ชั้น 1: Rate Limiting ──────────────────────────────
        try:
            if path.startswith("/v1/chairman/"):
                await limiter_chairman.check(f"{client_ip}:chairman", "Chairman API")
            elif path.startswith("/v1/sandbox/"):
                await limiter_sandbox.check(f"{client_ip}:sandbox", "Sandbox API")
            else:
                await limiter_global.check(client_ip, "API")
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content=e.detail,
                headers=dict(e.headers or {}),
            )

        # ── ชั้น 2: API Key Check (ข้าม public paths) ──────────
        is_public = (
            path in PUBLIC_PATHS
            or any(path.startswith(p) for p in PUBLIC_PREFIXES)
        )

        if not is_public:
            api_key = request.headers.get("X-API-Key")
            if not is_valid_api_key(api_key):
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "UNAUTHORIZED",
                        "message": "Missing or invalid API key — include X-API-Key header",
                        "hint": "Contact system administrator for an API key",
                    },
                    headers={"WWW-Authenticate": "ApiKey"},
                )

        # ── ชั้น 3: Chairman IP Allowlist (เฉพาะเมื่อตั้ง env) ──
        if path.startswith(CHAIRMAN_PREFIX) and not is_chairman_ip_allowed(request):
            return JSONResponse(
                status_code=403,
                content={
                    "error": "IP_FORBIDDEN",
                    "message": "Chairman endpoint does not allow this IP",
                    "hint": "Add your IP to CHAIRMAN_ALLOWED_IPS environment variable",
                },
            )

        return await call_next(request)
