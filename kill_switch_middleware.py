"""
kill_switch_middleware.py
Kill Switch Middleware - blocks all requests when system is HALTED

Whitelist (allowed even when HALTED):
  GET  /health
  POST /v1/chairman/kill-switch/resume  <- Chairman can always recover
  GET  /docs
  GET  /openapi.json

[FIX-4] Removed /v1/chairman/kill-switch/status from whitelist
        status now requires API Key + IP via SecurityMiddleware
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timezone

import kill_switch_engine

WHITELIST = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/v1/chairman/kill-switch/resume",
}


class KillSwitchMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in WHITELIST:
            return await call_next(request)

        if kill_switch_engine.is_halted():
            state = kill_switch_engine.get_state()
            return JSONResponse(
                status_code=503,
                content={
                    "error": "SYSTEM_HALTED",
                    "message": "System temporarily halted by Chairman (Kill Switch Active)",
                    "reason": state.get("reason", "-"),
                    "halted_at": state.get("changed_at"),
                    "resume_endpoint": "POST /v1/chairman/kill-switch/resume",
                    "constitution": "P-01/P-02: Chairman authority enforced",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

        return await call_next(request)
