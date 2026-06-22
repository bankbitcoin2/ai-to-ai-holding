"""
billing.py — AI TO AI HOLDING: Billing System
Handles: Client registration, Credit top-up via Stripe, Webhook, Auto-deduct
"""
import hashlib
import hmac
import os
import secrets
import uuid
import time
from datetime import datetime, timezone
from typing import Optional

import aiosqlite
from fastapi import APIRouter, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from database import DB_PATH, USE_POSTGRES
from holding_config import PRICE_PER_ITEM

router = APIRouter(prefix="/v1", tags=["Billing"])

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
BASE_URL = os.getenv("BASE_URL", "https://web-production-c9da4.up.railway.app")

# ── Models ────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    agent_name: str = Field(..., description="ชื่อ AI agent ของคุณ")
    contact_email: str = Field(..., description="Email สำหรับรับ API key และแจ้งเตือน")
    profession: str = Field(default="UNKNOWN", description="ประเภทงาน AI")
    origin_system: Optional[str] = Field(None, description="ระบบที่ใช้ เช่น Claude, GPT-4, LangChain")

class TopupRequest(BaseModel):
    api_key: str = Field(..., description="API key ที่ได้จากการ register")
    amount_usd: float = Field(..., ge=5.0, le=10000.0, description="จำนวนเงิน USD (ขั้นต่ำ $5)")

class RecoverKeyRequest(BaseModel):
    contact_email: str = Field(..., description="Email ที่ใช้สมัคร")
    agent_name: str = Field(..., description="ชื่อ Agent ที่ใช้สมัคร (ยืนยันตัวตน)")

# ── Helpers ───────────────────────────────────────────────────

def _generate_api_key() -> str:
    return "sk-aitai-" + secrets.token_hex(24)

def _ph(n: int) -> str:
    """Return placeholder: $n for PostgreSQL, ? for SQLite"""
    return f"${n}" if USE_POSTGRES else "?"

async def _get_db():
    if USE_POSTGRES:
        from db_adapter import connect
        return await connect()
    else:
        db = await aiosqlite.connect(DB_PATH)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        return db

async def _get_agent_by_key(db, api_key: str):
    hint = api_key[-8:]
    p1 = _ph(1)
    async with db.execute(f"""
        SELECT a.*, COALESCE(c.credit_balance, 0.0) as credit_balance,
               COALESCE(c.credit_topup_total, 0.0) as credit_topup_total
        FROM client_agents a
        LEFT JOIN client_credits c ON c.agent_id = a.id
        WHERE a.api_key_hint = {p1} AND a.status = 'ACTIVE'
    """, (hint,)) as cur:
        row = await cur.fetchone()
    return row

async def _audit(db, event_type: str, actor_id: str, action: str, payload: str):
    """บันทึก audit event — ใช้ column names จาก schema_v1.sql จริง"""
    try:
        p1, p2, p3, p4, p5, p6 = _ph(1), _ph(2), _ph(3), _ph(4), _ph(5), _ph(6)
        ev_id = str(uuid.uuid4())
        evidence_hash = hashlib.sha256(f"{ev_id}{actor_id}{action}{payload}".encode()).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            f"INSERT INTO audit_events (id, event_type, actor_id, action, payload, evidence_hash, occurred_at) "
            f"VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {_ph(7)})",
            (ev_id, event_type, actor_id, action, payload, evidence_hash, now)
        )
    except Exception as e:
        # audit ไม่ควร block main flow
        print(f"[AUDIT] Warning — could not write audit event: {e}")

# ── Register ──────────────────────────────────────────────────


async def log_agent_call(agent_id: str, endpoint: str, status_code: int,
                         latency_ms: int, tokens_used: int = 0,
                         session_id: str = None):
    """บันทึก API call ลง client_agent_calls — non-blocking, never raises"""
    try:
        from db_adapter import get_pool, USE_POSTGRES
        if not USE_POSTGRES:
            return
        pool = await get_pool()
        async with pool.acquire() as conn:
            import uuid as _uuid
            from datetime import datetime, timezone
            await conn.execute(
                "INSERT INTO client_agent_calls "
                "(id, agent_id, endpoint, method, status_code, latency_ms, tokens_used, called_at, session_id) "
                "VALUES ($1,$2,$3,'POST',$4,$5,$6,$7,$8)",
                str(_uuid.uuid4()), agent_id, endpoint, status_code,
                latency_ms, tokens_used,
                datetime.now(timezone.utc).isoformat(),
                session_id
            )
    except Exception as e:
        pass  # log failure ไม่ควร crash main flow


@router.post("/register", summary="ลงทะเบียน AI Client — รับ API Key")
async def register_client(req: RegisterRequest):
    api_key = _generate_api_key()
    agent_id = str(uuid.uuid4())
    hint = api_key[-8:]
    now = datetime.now(timezone.utc).isoformat()
    p1, p2, p3, p4, p5, p6, p7 = _ph(1), _ph(2), _ph(3), _ph(4), _ph(5), _ph(6), _ph(7)

    db = await _get_db()
    try:
        async with db.execute(
            f"SELECT id FROM client_agents WHERE contact_email = {p1}",
            (req.contact_email,)
        ) as cur:
            existing = await cur.fetchone()
        if existing:
            raise HTTPException(400, "Email นี้ลงทะเบียนไปแล้ว กรุณาใช้ Recover Key")

        await db.execute(f"""
            INSERT INTO client_agents
            (id, agent_name, profession, origin_system, contact_email,
             api_key_hint, status, registered_at)
            VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, 'ACTIVE', {p7})
        """, (agent_id, req.agent_name, req.profession,
              req.origin_system, req.contact_email, hint, now))

        if USE_POSTGRES:
            await db.execute(f"""
                INSERT INTO client_credits (agent_id, credit_balance, credit_topup_total)
                VALUES ({p1}, 0.0, 0.0)
                ON CONFLICT (agent_id) DO NOTHING
            """, (agent_id,))
        else:
            await db.execute(f"""
                INSERT OR IGNORE INTO client_credits (agent_id, credit_balance, credit_topup_total)
                VALUES ({p1}, 0.0, 0.0)
            """, (agent_id,))

        await db.commit()  # commit ก่อน audit — audit ต้องไม่ block

        await _audit(db, 'TRANSACTION', agent_id, 'REGISTER',
                     f'{{"agent_name":"{req.agent_name}","email":"{req.contact_email}"}}')
        try:
            await db.commit()
        except Exception:
            pass
    finally:
        await db.close()

    return {
        "success": True,
        "agent_id": agent_id,
        "agent_name": req.agent_name,
        "api_key": api_key,
        "api_key_hint": f"...{hint}",
        "credit_balance": 0.0,
        "message": "ลงทะเบียนสำเร็จ เก็บ api_key ไว้ให้ดี จะไม่แสดงอีก",
        "next_step": "เติม credit ที่ POST /v1/billing/topup เพื่อใช้งาน production",
        "sandbox": "ทดลองฟรีได้ที่ POST /v1/sandbox/classify (ไม่ต้องใช้ API key)",
    }

# ── Recover Key ───────────────────────────────────────────────

@router.post("/recover-key", summary="กู้คืน API Key ด้วย email + ชื่อ Agent")
async def recover_key(req: RecoverKeyRequest):
    email = req.contact_email.strip()
    name  = req.agent_name.strip()

    if USE_POSTGRES:
        # ── PostgreSQL: ใช้ asyncpg pool โดยตรง (ข้าม db_adapter) ────────────
        from db_adapter import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, agent_name, contact_email, status FROM client_agents "
                "WHERE LOWER(contact_email) = LOWER($1) AND LOWER(agent_name) = LOWER($2)",
                email, name
            )
            if not row:
                raise HTTPException(404, {
                    "error": "NOT_FOUND",
                    "message": "ไม่พบบัญชีที่ตรงกับ email และชื่อ Agent ที่ระบุ"
                })
            if row["status"] != "ACTIVE":
                raise HTTPException(403, {
                    "error": "ACCOUNT_SUSPENDED",
                    "message": "บัญชีนี้ถูกระงับ ติดต่อ support"
                })
            new_key  = _generate_api_key()
            new_hint = new_key[-8:]
            await conn.execute(
                "UPDATE client_agents SET api_key_hint = $1 WHERE id = $2",
                new_hint, row["id"]
            )
            try:
                ev_id = str(uuid.uuid4())
                now   = datetime.now(timezone.utc).isoformat()
                evidence_hash = hashlib.sha256(
                    f"{ev_id}{row['id']}KEY_RECOVERED{email}".encode()).hexdigest()
                await conn.execute(
                    "INSERT INTO audit_events (id, event_type, actor_id, action, payload, evidence_hash, occurred_at) "
                    "VALUES ($1,$2,$3,$4,$5,$6,$7)",
                    ev_id, 'TRANSACTION', row["id"], 'KEY_RECOVERED',
                    f'{{"email":"{email}","new_hint":"...{new_hint}"}}',
                    evidence_hash, now
                )
            except Exception as ae:
                print(f"[AUDIT] recover_key audit warning: {ae}")
    else:
        # ── SQLite fallback ───────────────────────────────────────────────────
        p1, p2 = _ph(1), _ph(2)
        db = await _get_db()
        try:
            async with db.execute(
                f"SELECT id, agent_name, contact_email, status FROM client_agents "
                f"WHERE contact_email = {p1} AND LOWER(agent_name) = LOWER({p2})",
                (email, name)
            ) as cur:
                row = await cur.fetchone()
            if not row:
                raise HTTPException(404, {"error": "NOT_FOUND", "message": "ไม่พบบัญชี"})
            if row["status"] != "ACTIVE":
                raise HTTPException(403, {"error": "ACCOUNT_SUSPENDED", "message": "บัญชีถูกระงับ"})
            new_key  = _generate_api_key()
            new_hint = new_key[-8:]
            await db.execute(f"UPDATE client_agents SET api_key_hint = {p1} WHERE id = {p2}",
                             (new_hint, row["id"]))
            await db.commit()
            await _audit(db, 'TRANSACTION', row["id"], 'KEY_RECOVERED',
                         f'{{"email":"{email}","new_hint":"...{new_hint}"}}')
            try: await db.commit()
            except Exception: pass
        finally:
            await db.close()

    return {
        "success": True,
        "message": "ออก API Key ใหม่สำเร็จ Key เก่าถูก invalidate แล้ว",
        "api_key": new_key,
        "api_key_hint": f"...{new_hint}",
        "agent_name": row["agent_name"],
        "warning": "บันทึก key ใหม่นี้ไว้ให้ดี จะไม่แสดงอีก",
    }

# ── Check Balance ─────────────────────────────────────────────

@router.get("/billing/balance", summary="ตรวจสอบ credit คงเหลือ")
async def check_balance(x_api_key: str = Header(..., alias="X-API-Key")):
    db = await _get_db()
    try:
        row = await _get_agent_by_key(db, x_api_key)
    finally:
        await db.close()
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
    db = await _get_db()
    try:
        row = await _get_agent_by_key(db, req.api_key)
    finally:
        await db.close()
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
    p1, p2, p3, p4, p5 = _ph(1), _ph(2), _ph(3), _ph(4), _ph(5)
    db = await _get_db()
    try:
        await db.execute(f"""
            INSERT INTO credit_topups
            (id, agent_id, amount_usd, stripe_session_id, status, created_at)
            VALUES ({p1}, {p2}, {p3}, {p4}, 'pending', {p5})
        """, (session_id, row["id"], req.amount_usd,
              stripe_data["id"], datetime.now(timezone.utc).isoformat()))
        await db.commit()
    finally:
        await db.close()

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
        try:
            parts = {k: v for part in sig.split(",")
                     for k, v in [part.split("=", 1)]}
            ts = parts.get("t", "")
            v1 = parts.get("v1", "")
            signed = f"{ts}.{payload.decode()}"
            expected = hmac.new(
                STRIPE_WEBHOOK_SECRET.encode(),
                signed.encode(),
                digestmod=hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(expected, v1):
                raise HTTPException(400, "Invalid signature")
        except HTTPException:
            raise
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
            p1, p2, p3 = _ph(1), _ph(2), _ph(3)
            db = await _get_db()
            try:
                async with db.execute(
                    f"SELECT status FROM credit_topups WHERE stripe_session_id = {p1}",
                    (stripe_session_id,)
                ) as cur:
                    topup_row = await cur.fetchone()

                if topup_row and topup_row["status"] == "completed":
                    print(f"[BILLING] Webhook duplicate ignored: {stripe_session_id}")
                    return {"received": True}

                await db.execute(f"""
                    INSERT INTO client_credits (agent_id, credit_balance, credit_topup_total)
                    VALUES ({p1}, {p2}, {p3})
                    ON CONFLICT(agent_id) DO UPDATE SET
                        credit_balance = client_credits.credit_balance + {p2},
                        credit_topup_total = client_credits.credit_topup_total + {p3}
                """, (agent_id, amount_usd, amount_usd))

                await db.execute(
                    f"UPDATE credit_topups SET status = 'completed' WHERE stripe_session_id = {p1}",
                    (stripe_session_id,)
                )

                await _audit(db, 'TRANSACTION', agent_id, 'CREDIT_TOPUP',
                             f'{{"amount_usd":{amount_usd},"stripe_session":"{stripe_session_id}"}}')
                await db.commit()
                print(f"[BILLING] Credit +{amount_usd} USD → agent {agent_id}")

            except Exception as exc:
                print(f"[BILLING] Webhook processing error: {exc}")
                raise HTTPException(500, "Internal error processing webhook")
            finally:
                await db.close()

    return {"received": True}

# ── Stripe Success / Cancel ───────────────────────────────────

@router.get("/billing/success")
async def billing_success(session_id: str = ""):
    return JSONResponse({
        "status": "success",
        "message": "ชำระเงินสำเร็จ! Credit จะถูกเติมภายใน 1-2 นาที",
        "session_id": session_id,
    })

@router.get("/billing/cancel")
async def billing_cancel():
    return JSONResponse({
        "status": "cancelled",
        "message": "ยกเลิกการชำระเงิน ไม่มีการตัดเงิน",
    })
