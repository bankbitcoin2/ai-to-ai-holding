"""
billing.py — AI TO AI HOLDING: Billing System
Handles: Client registration, Credit top-up via Stripe, Webhook, Auto-deduct
"""
import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

import aiosqlite
from fastapi import APIRouter, HTTPException, Request, Header
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from database import get_db
from holding_config import PRICE_PER_ITEM

router = APIRouter(prefix="/v1", tags=["Billing"])

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
BASE_URL = os.getenv("BASE_URL", "https://web-production-c9da4.up.railway.app")

# ── Models ────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    agent_name: str = Field(..., description="ชื่อ AI agent ของคุณ")
    contact_email: str = Field(..., description="Email สำหรับรับ API key และแจ้งเตือน")
    profession: str = Field(
        default="UNKNOWN",
        description="ประเภทงาน AI",
    )
    origin_system: Optional[str] = Field(None, description="ระบบที่ใช้ เช่น Claude, GPT-4, LangChain")

class TopupRequest(BaseModel):
    api_key: str = Field(..., description="API key ที่ได้จากการ register")
    amount_usd: float = Field(..., ge=5.0, le=10000.0, description="จำนวนเงิน USD (ขั้นต่ำ $5)")

# ── Helpers ───────────────────────────────────────────────────

def _generate_api_key() -> str:
    return "sk-aitai-" + secrets.token_hex(24)

async def _get_agent_by_key(db: aiosqlite.Connection, api_key: str):
    hint = api_key[-8:]
    async with db.execute("""
        SELECT a.*, COALESCE(c.credit_balance, 0.0) as credit_balance,
               COALESCE(c.credit_topup_total, 0.0) as credit_topup_total
        FROM client_agents a
        LEFT JOIN client_credits c ON c.agent_id = a.id
        WHERE a.api_key_hint = ? AND a.status = 'active'
    """, (hint,)) as cur:
        row = await cur.fetchone()
    return row

# ── Register ──────────────────────────────────────────────────

@router.post("/register", summary="ลงทะเบียน AI Client — รับ API Key")
async def register_client(req: RegisterRequest):
    """
    AI client หรือเจ้าของลงทะเบียนเพื่อรับ API Key
    ไม่มีค่าใช้จ่ายในการสมัคร — เติม credit เมื่อต้องการใช้งาน production
    """
    api_key = _generate_api_key()
    agent_id = str(uuid.uuid4())
    hint = api_key[-8:]
    now = datetime.now(timezone.utc).isoformat()

    async with get_db() as db:
        # ตรวจ email ซ้ำ
        async with db.execute(
            "SELECT id FROM client_agents WHERE contact_email = ?",
            (req.contact_email,)
        ) as cur:
            existing = await cur.fetchone()
        if existing:
            raise HTTPException(400, "Email นี้ลงทะเบียนไปแล้ว")

        await db.execute("""
            INSERT INTO client_agents
            (id, agent_name, profession, origin_system, contact_email,
             api_key_hint, status, registered_at)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?)
        """, (agent_id, req.agent_name, req.profession,
              req.origin_system, req.contact_email, hint, now))
        await db.execute("""
            INSERT OR IGNORE INTO client_credits (agent_id, credit_balance, credit_topup_total)
            VALUES (?, 0.0, 0.0)
        """, (agent_id,))
        await db.commit()

    return {
        "success": True,
        "agent_id": agent_id,
        "agent_name": req.agent_name,
        "api_key": api_key,
        "api_key_hint": f"...{hint}",
        "credit_balance": 0.0,
        "message": "ลงทะเบียนสำเร็จ เก็บ api_key ไว้ให้ดี จะไม่แสดงอีก",
        "next_step": f"เติม credit ที่ POST /v1/billing/topup เพื่อใช้งาน production",
        "sandbox": "ทดลองฟรีได้ที่ POST /v1/sandbox/classify (ไม่ต้องใช้ API key)",
    }

# ── Check Balance ─────────────────────────────────────────────

@router.get("/billing/balance", summary="ตรวจสอบ credit คงเหลือ")
async def check_balance(x_api_key: str = Header(..., alias="X-API-Key")):
    async with get_db() as db:
        row = await _get_agent_by_key(db, x_api_key)
    if not row:
        raise HTTPException(401, "API key ไม่ถูกต้อง")
    return {
        "agent_name": row["agent_name"],
        "credit_balance": row["credit_balance"],
        "price_per_item": PRICE_PER_ITEM,
        "estimated_calls_remaining": int(row["credit_balance"] / PRICE_PER_ITEM),
    }

# ── Top-up via Stripe ─────────────────────────────────────────

@router.post("/billing/topup", summary="เติม credit ผ่าน Stripe")
async def create_topup(req: TopupRequest):
    if not STRIPE_SECRET_KEY or STRIPE_SECRET_KEY.startswith("sk_live_xxx"):
        raise HTTPException(503, "ระบบชำระเงินยังไม่พร้อม — Stripe ยังไม่ได้ตั้งค่า")

    import httpx
    async with get_db() as db:
        row = await _get_agent_by_key(db, req.api_key)
    if not row:
        raise HTTPException(401, "API key ไม่ถูกต้อง")

    amount_cents = int(req.amount_usd * 100)
    session_id = str(uuid.uuid4())

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.stripe.com/v1/checkout/sessions",
            auth=(STRIPE_SECRET_KEY, ""),
            data={
                "payment_method_types[]": "card",
                "mode": "payment",
                "line_items[0][price_data][currency]": "usd",
                "line_items[0][price_data][product_data][name]": f"AI TO AI HOLDING Credit — {req.amount_usd} USD",
                "line_items[0][price_data][unit_amount]": amount_cents,
                "line_items[0][quantity]": 1,
                "success_url": f"{BASE_URL}/v1/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
                "cancel_url": f"{BASE_URL}/v1/billing/cancel",
                "metadata[agent_id]": row["id"],
                "metadata[amount_usd]": str(req.amount_usd),
            }
        )
    if resp.status_code != 200:
        raise HTTPException(502, f"Stripe error: {resp.text}")

    stripe_data = resp.json()
    async with get_db() as db:
        await db.execute("""
            INSERT INTO credit_topups
            (id, agent_id, amount_usd, stripe_session_id, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
        """, (session_id, row["id"], req.amount_usd,
              stripe_data["id"], datetime.now(timezone.utc).isoformat()))
        await db.commit()

    return {
        "checkout_url": stripe_data["url"],
        "session_id": stripe_data["id"],
        "amount_usd": req.amount_usd,
        "message": "ไปที่ checkout_url เพื่อชำระเงิน",
    }

# ── Stripe Webhook ────────────────────────────────────────────

@router.post("/billing/webhook", include_in_schema=False)
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    if STRIPE_WEBHOOK_SECRET and not STRIPE_WEBHOOK_SECRET.startswith("whsec_xxx"):
        # verify signature
        try:
            parts = {k: v for part in sig.split(",")
                     for k, v in [part.split("=", 1)]}
            ts = parts.get("t", "")
            v1 = parts.get("v1", "")
            signed = f"{ts}.{payload.decode()}"
            expected = hmac.new(
                STRIPE_WEBHOOK_SECRET.encode(),
                signed.encode(),
                hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(expected, v1):
                raise HTTPException(400, "Invalid signature")
        except Exception:
            raise HTTPException(400, "Webhook signature verification failed")

    import json
    event = json.loads(payload)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        agent_id = session.get("metadata", {}).get("agent_id")
        amount_usd = float(session.get("metadata", {}).get("amount_usd", 0))
        stripe_session_id = session["id"]

        if agent_id and amount_usd > 0:
            async with get_db() as db:
                await db.execute("""
                    INSERT INTO client_credits (agent_id, credit_balance, credit_topup_total)
                    VALUES (?, ?, ?)
                    ON CONFLICT(agent_id) DO UPDATE SET
                        credit_balance = credit_balance + excluded.credit_balance,
                        credit_topup_total = credit_topup_total + excluded.credit_topup_total,
                        updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
                """, (agent_id, amount_usd, amount_usd))
                await db.execute("""
                    UPDATE credit_topups
                    SET status = 'completed',
                        completed_at = ?,
                        stripe_payment_intent = ?
                    WHERE stripe_session_id = ?
                """, (datetime.now(timezone.utc).isoformat(),
                      session.get("payment_intent", ""),
                      stripe_session_id))
                await db.commit()

    return {"received": True}

@router.get("/billing/success", include_in_schema=False)
async def billing_success():
    return {"message": "ชำระเงินสำเร็จ! Credit จะเข้าบัญชีภายใน 1-2 นาที"}

@router.get("/billing/cancel", include_in_schema=False)
async def billing_cancel():
    return {"message": "ยกเลิกการชำระเงิน กลับมาเติมได้ใหม่ที่ POST /v1/billing/topup"}

# ── Auto-deduct helper (เรียกจาก customs.py) ─────────────────

async def deduct_credit(api_key: str, item_count: int) -> dict:
    """
    หัก credit ก่อน classify จริง
    return: {"success": True, "remaining": float} หรือ raise HTTPException 402
    """
    cost = round(PRICE_PER_ITEM * item_count, 4)
    async with get_db() as db:
        row = await _get_agent_by_key(db, api_key)
        if not row:
            raise HTTPException(401, "API key ไม่ถูกต้อง")
        balance = row["credit_balance"]
        if balance < cost:
            raise HTTPException(
                402,
                f"Credit ไม่พอ — ต้องการ ${cost:.2f} แต่มี ${balance:.2f} "
                f"เติมได้ที่ POST /v1/billing/topup"
            )
        new_balance = round(balance - cost, 4)
        await db.execute("""
            UPDATE client_credits SET credit_balance = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
            WHERE agent_id = ?
        """, (new_balance, row["id"]))
        await db.execute(
            "UPDATE client_agents SET total_spend = total_spend + ? WHERE id = ?",
            (cost, row["id"])
        )
        await db.commit()
    return {"success": True, "cost": cost, "remaining": new_balance, "agent_id": row["id"]}
