import sys
import os

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
_PARENT = os.path.dirname(_THIS_DIR)
if _PARENT in sys.path:
    sys.path.remove(_PARENT)

"""
main.py - AI TO AI HOLDING: Customs Intelligence API

Security patches:
  [FIX-1] HTTPS via nginx (see nginx.conf) + bind 127.0.0.1 only
  [FIX-2] API Key auth on all non-public endpoints (SecurityMiddleware)
  [FIX-3] CORS restricted to ALLOWED_ORIGINS env var
  [FIX-4] Kill Switch status requires API Key
  [FIX-5] Chairman IP Allowlist (SecurityMiddleware)
  [FIX-6] Rate Limiting global (SecurityMiddleware)
  [FIX-7] DB absolute path (holding_config.py)
"""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from database import init_db
from holding_config import print_config, ALLOWED_ORIGINS
from customs import router as customs_router
from sandbox import router as sandbox_router
from treasury import router as treasury_router
from ceo import router as ceo_router
from treasury_wallet_router import router as wallet_router
from kill_switch_router import router as kill_switch_router
from kill_switch_middleware import KillSwitchMiddleware
from security import SecurityMiddleware
from billing import router as billing_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print_config()
    await init_db()
    yield


app = FastAPI(
    title="AI TO AI HOLDING - Customs Intelligence API",
    description="Customs Intelligence Division. All production endpoints require X-API-Key header.",
    version="1.1.0",
    lifespan=lifespan,
)

# Middleware stack (bottom = runs first)
# 1. KillSwitchMiddleware - check HALTED state
# 2. SecurityMiddleware   - rate limit + API Key + IP check
# 3. CORSMiddleware       - CORS headers
app.add_middleware(KillSwitchMiddleware)
app.add_middleware(SecurityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # [FIX-3] no wildcard
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type", "Accept"],
)


@app.get("/health", tags=["System"])
async def health():
    """Health check - public, available even when Kill Switch active"""
    import kill_switch_engine
    state = kill_switch_engine.get_state()
    return {
        "status": "ok",
        "system_state": state.get("state", "OPERATIONAL"),
        "is_halted": state.get("is_halted", False),
    }


@app.get("/", include_in_schema=False)
async def root():
    return JSONResponse({
        "organization": "AI TO AI HOLDING",
        "division": "Customs Intelligence Division",
        "phase": "Phase 1 - Foundation v1",
        "status": "OPERATIONAL",
        "auth": "X-API-Key header required on all production endpoints",
        "endpoints": {
            "sandbox_classify": "POST /v1/sandbox/classify  <- FREE trial (no key)",
            "classify_invoice": "POST /v1/customs/classify  <- Production (API key)",
            "get_case":         "GET  /v1/customs/case/{id} <- Production (API key)",
            "treasury_settle":  "POST /v1/treasury/settle   <- Internal (API key)",
            "ceo_command":      "POST /v1/ceo/command       <- Chairman (API key + IP)",
            "kill_switch":      "POST /v1/chairman/kill-switch/activate <- Chairman only",
            "docs":             "/docs",
        },
    })


# ── AI-to-AI Discovery Layer ──────────────────────────────────────────
# รองรับทุก standard: OpenAI GPT Actions, Anthropic MCP, LangChain, Gemini
_WELL_KNOWN = Path(__file__).parent / ".well-known"

@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
async def ai_plugin():
    """ChatGPT Plugin / GPT Actions discovery"""
    return FileResponse(_WELL_KNOWN / "ai-plugin.json", media_type="application/json")

@app.get("/.well-known/mcp.json", include_in_schema=False)
async def mcp_manifest():
    """Anthropic MCP (Model Context Protocol) tool manifest"""
    return FileResponse(_WELL_KNOWN / "mcp.json", media_type="application/json")

@app.get("/.well-known/function-schemas.json", include_in_schema=False)
async def function_schemas():
    """OpenAI Function Calling / Gemini Function Declarations / LangChain Tool schemas"""
    return FileResponse(_WELL_KNOWN / "function-schemas.json", media_type="application/json")

@app.get("/.well-known/", include_in_schema=False)
async def well_known_index():
    """Discovery index — list all AI integration standards we support"""
    return {
        "provider": "AI TO AI HOLDING",
        "standards_supported": {
            "openapi":           "/openapi.json",
            "gpt_actions":       "/.well-known/ai-plugin.json",
            "mcp":               "/.well-known/mcp.json",
            "function_calling":  "/.well-known/function-schemas.json",
            "langchain":         "/.well-known/function-schemas.json",
            "swagger_ui":        "/docs",
        },
        "sandbox": "POST /v1/sandbox/classify (no auth, free trial)",
        "production": "POST /v1/customs/classify (X-API-Key required)",
    }


# Routers
app.include_router(customs_router)
app.include_router(sandbox_router)
app.include_router(treasury_router)
app.include_router(ceo_router)
app.include_router(wallet_router)
app.include_router(kill_switch_router)
app.include_router(billing_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",  # [FIX-1] localhost only - nginx handles external traffic
        port=8000,
        reload=False,
    )
