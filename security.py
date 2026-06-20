"""
security.py
Security Layer — API Key Auth + IP Allowlist + Rate Limiting

อุดช่องโหว่:
  [FIX-2] API Key บังคับทุก endpoint ที่ไม่ใช่ public
  [FIX-3] IP Allowlist ป้องกัน Chairman endpoints
  [FIX-6] Rate Limiting แบบ Sliding Window — ไม่ต้อง pip install เพิ่ม

การตั้งค่าผ่าน Environment Variables:
  API_KEYS              = key1,key2,key3        (จำเป็น — ต้องตั้งใน production)
  CHAIRMAN_ALLOWED_IPS  = 127.0.0.1,10.0.0.5   (default: localhost เท่านั้น)
  RATE_LIMIT_GLOBAL     = 60                    (request/นาที ต่อ IP, default 60)
  RATE_LIMIT_CHAIRMAN   = 10                    (request/นาที สำหรับ /chairman/*, default 10)
  RATE_LIMIT_SANDBOX    = 20                    (request/นาที สำหรับ /sandbox/*, default 20)

Public endpoints (ไม่ต้อง API Key):
  GET  /health
  GET  /
  GET  /docs
  GET  /openapi.json
  POST /v1/sandbox/*    ← Free trial (แต่ยัง rate-limited)
  POST /v1/chairman/kill-switch/resume  ← emergency resume ยังต้องมี Chairman password อยู่
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
║  ⚠️  WARNING: API_KEYS not set in environment            ║
║  Temporary dev key (NOT for production):                 ║
║  X-API-Key: {_DEV_KEY:<44}║
║  Set API_KEYS=<your-key> in .env before going live       ║
╚══════════════════════════════════════════════════════════╝
""")


def is_valid_api_key(key: Optional[str]) -> bool:
    if not key:
        return False
    # constant-time compare เพื่อป้องกัน timing attack
    return any(secrets.compare_digest(key, valid) for valid in _VALID_KEYS)


# ══════════════════════════════════════════════════════════════
# Section 2 — Chairman IP Allowlist
# ══════════════════════════════════════════════════════════════

_raw_ips = os.getenv("CHAIRMAN_ALLOWED_IPS", "127.0.0.1,::1,0.0.0.0")
CHAIRMAN_ALLOWED_IPS: set = set(ip.strip() for ip in _raw_ips.split(",") if ip.strip())


def get_real_ip(request: Request) -> str:
    """ดึง real client IP — รองรับ X-Forwarded-For จาก nginx"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def is_chairman_ip_allowed(request: Request) -> bool:
    client_ip = get_real_ip(request)
    return client_ip in CHAIRMAN_ALLOWED_IPS


# ══════════════════════════════════════════════════════════════
# Section 3 — Sliding Window Rate Limiter (no extra deps)
# ══════════════════════════════════════════════════════════════

class SlidingWindowLimiter:
    """
    Thread-safe sliding window rate limiter
    ไม่ต้อง pip install slowapi หรือ redis
    เหมาะสำหรับ single-process deployment
    """
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

            # ลบ timestamps เก่าออก
            while dq and dq[0] < window_start:
                dq.popleft()

            if len(dq) >= self.max_requests:
                oldest = dq[0]
                retry_after = int(oldest + self.window_seconds - now) + 1
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "RATE_LIMIT_EXCEEDED",
                        "message": f"⚠️ Too many requests to {label} — retry after {retry_after}s",
                        "retry_after_seconds": retry_after,
                        "limit": f"{self.max_requests} req/{self.window_seconds}s per IP",
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            dq.append(now)

    def cleanup_old_keys(self):
        """ลบ entries เก่าที่ไม่ active เพื่อป้องกัน memory leak"""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        dead = [k for k, dq in self._buckets.items() if not dq or dq[-1] < cutoff]
        for k in dead:
            del self._buckets[k]


# สร้าง limiter instances
_global_limit    = int(os.getenv("RATE_LIMIT_GLOBAL",   "60"))
_chairman_limit  = int(os.getenv("RATE_LIMIT_CHAIRMAN", "10"))
_sandbox_limit   = int(os.getenv("RATE_LIMIT_SANDBOX",  "20"))

limiter_global   = SlidingWindowLimiter(_global_limit,   60)
limiter_chairman = SlidingWindowLimiter(_chairman_limit, 60)
limiter_sandbox  = SlidingWindowLimiter(_sandbox_limit,  60)


# ══════════════════════════════════════════════════════════════
# Section 4 — Security Middleware
# ══════════════════════════════════════════════════════════════

# Public paths ที่ไม่ต้อง API Key (แต่ยัง rate limited)
PUBLIC_PATHS: set = {
    "/",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
}

# Path prefixes ที่ถือว่า public
PUBLIC_PREFIXES: tuple = (
    "/v1/sandbox/",                       # Free trial — เรียกได้โดยไม่ต้อง key
    "/v1/chairman/kill-switch/resume",    # emergency resume ต้องผ่าน Chairman password อยู่
    "/v1/register",                       # Client signup — ต้องเข้าได้โดยไม่มี key
    "/v1/billing/",                       # Billing — จัดการ auth เองผ่าน api_key ใน body
    "/.well-known/",                      # AI discovery
)

# Chairman path prefix — ต้อง IP check เพิ่ม
CHAIRMAN_PREFIX = "/v1/chairman/"


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    รวม 3 ชั้นป้องกันใน middleware เดียว:
      1. Rate Limiting (ทุก path)
      2. API Key Check (non-public paths)
      3. IP Allowlist (chairman paths)
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        client_ip = get_real_ip(request)
        ip_key = f"{client_ip}:{path}"

        # ── ชั้น 1: Rate Limiting ──────────────────────────────
        try:
            if path.startswith("/v1/chairman/"):
                await limiter_chairman.check(f"{client_ip}:chairman", "Chairman API")
            elif path.startswith("/v1/sandbox/"):
                await limiter_sandbox.check(f"{client_ip}:sandbox", "Sandbox API")
            else:
                await limiter_global.check(client_ip, "API")
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content=e.detail,
                                headers=dict(e.headers or {}))

        # ── ชั้น 2: API Key Check ──────────────────────────────
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
                        "message": "❌ Missing or invalid API key — include X-API-Key header",
                        "hint": "Contact system administrator for an API key",
                    },
                    headers={"WWW-Authenticate": "ApiKey"},
                )

        # ── ชั้น 3: Chairman IP Allowlist ──────────────────────
        if path.startswith(CHAIRMAN_PREFIX):
            if not is_chairman_ip_allowed(request):
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "IP_FORBIDDEN",
                        "message": f"❌ Chairman endpoint ไม่อนุญาต IP นี้",
                        "constitution": "P-01: Chairman authority protected by IP allowlist",
                        "hint": "เพิ่ม IP ของคุณใน CHAIRMAN_ALLOWED_IPS environment variable",
                    },
                )

        return await call_next(request)
