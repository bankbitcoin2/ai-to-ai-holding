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
from chairman_router import router as chairman_router


async def _auto_seed():
    """Seed hs_code_master + fta_eligibility ถ้าตารางว่าง — รันครั้งเดียวอัตโนมัติ"""
    from database import USE_POSTGRES
    if not USE_POSTGRES:
        return
    try:
        from db_adapter import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Apply schema ก่อน
            schema_path = __import__('pathlib').Path(__file__).parent / 'schema_hs_master.sql'
            if schema_path.exists():
                await conn.execute(schema_path.read_text())

            # ตรวจว่า hs_code_master ว่างไหม
            count = await conn.fetchval("SELECT COUNT(*) FROM hs_code_master")
            if count and count > 0:
                print(f"[SEED] hs_code_master already has {count} rows — skip")
                return

            # Seed hs_descriptions
            import hs_descriptions_bundled as _hd
            import json, zlib, base64
            desc_db = _hd._load()
            desc_rows = [(k.strip(), v["th"], v["en"]) for k, v in desc_db.items()]
            await conn.executemany(
                "INSERT INTO hs_code_master (hs_code, desc_th, desc_en) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING",
                desc_rows
            )
            print(f"[SEED] hs_code_master: {len(desc_rows)} rows inserted")

            # Seed fta_eligibility
            import fta_eligibility_bundled as _fe
            fta_db = _fe._load()
            fta_rows = [(hs.strip(), cc, form) for cc, hs_map in fta_db.items() for hs, form in hs_map.items()]
            batch = 500
            for i in range(0, len(fta_rows), batch):
                await conn.executemany(
                    "INSERT INTO fta_eligibility (hs_code, country_code, fta_form) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING",
                    fta_rows[i:i+batch]
                )
            print(f"[SEED] fta_eligibility: {len(fta_rows)} rows inserted")
    except Exception as e:
        print(f"[SEED] Warning — auto-seed failed (non-fatal): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print_config()
    await init_db()
    await _auto_seed()
    yield


app = FastAPI(
    title="AI TO AI HOLDING - Customs Intelligence API",
    description="Customs Intelligence Division. All production endpoints require X-API-Key header.",
    version="1.1.0",
    lifespan=lifespan,
)

# Middleware stack — Starlette ใช้ stack: add_middleware ล่าสุด = outermost = รันก่อนสุด
# ลำดับที่ต้องการ: KillSwitch → Security → CORS → app
# ต้อง add ในลำดับกลับ: CORS ก่อน แล้ว Security แล้ว KillSwitch
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # [FIX-3] no wildcard
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type", "Accept"],
)
app.add_middleware(SecurityMiddleware)
# KillSwitchMiddleware เป็น outermost — เมื่อ HALTED short-circuit ทันที
# ก่อนผ่าน rate limiter เพื่อไม่เปลือง resource
app.add_middleware(KillSwitchMiddleware)


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


# ── Static Files (Landing page + Dashboard) ──────────────────
_STATIC = Path(__file__).parent / "static"

@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    return FileResponse(_STATIC / "dashboard.html", media_type="text/html")

@app.get("/chairman", include_in_schema=False)
async def chairman_office():
    return FileResponse(_STATIC / "chairman.html", media_type="text/html")

# Override root to serve landing page
@app.get("/", include_in_schema=False)
async def landing():
    return FileResponse(_STATIC / "index.html", media_type="text/html")


# Routers
app.include_router(customs_router)
app.include_router(sandbox_router)
app.include_router(treasury_router)
app.include_router(ceo_router)
app.include_router