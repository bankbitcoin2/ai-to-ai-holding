"""
line_webhook.py — Phase 19: LINE OA Integration
AI TO AI HOLDING — Customs Intelligence Division

Flow:
  1. ผู้ใช้ส่งรูป invoice / ไฟล์ PDF ใน LINE
  2. Webhook รับ event → download content จาก LINE
  3. ตรวจว่าผู้ใช้ผูก LINE กับ account + มี credit
  4. เรียก invoice_parser → invoice_service.process_invoice
  5. Reply ผลกลับ LINE (Flex Message)

Env vars ที่ต้องตั้ง:
  LINE_CHANNEL_SECRET   — สำหรับ verify signature
  LINE_CHANNEL_TOKEN    — สำหรับ reply + download content
"""

import hashlib
import hmac
import base64
import json
import os
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/webhook", tags=["LINE"])

_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
_CHANNEL_TOKEN = os.getenv("LINE_CHANNEL_TOKEN", "")
_LINE_API = "https://api.line.me/v2/bot"
_LINE_DATA = "https://api-data.line.me/v2/bot"

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
SUPPORTED_FILE_EXTS = {".pdf", ".xlsx", ".xls", ".csv"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


# ── Webhook Entry ──────────────────────────────────────────────────────────────

@router.post("/line", include_in_schema=False)
async def line_webhook(request: Request):
    """LINE Messaging API webhook endpoint"""
    body = await request.body()

    # Verify signature
    if _CHANNEL_SECRET:
        signature = request.headers.get("X-Line-Signature", "")
        if not _verify_signature(body, signature):
            raise HTTPException(400, "Invalid signature")

    payload = json.loads(body)
    events = payload.get("events", [])

    for event in events:
        try:
            await _handle_event(event)
        except Exception as e:
            print(f"[LINE] event error: {e}")

    return {"status": "ok"}


# ── Event Handler ──────────────────────────────────────────────────────────────

async def _handle_event(event: dict):
    """Route event ตามประเภท"""
    event_type = event.get("type")
    reply_token = event.get("replyToken")

    if event_type == "follow":
        # ผู้ใช้ add friend
        await _reply_text(reply_token, (
            "สวัสดีครับ! ยินดีต้อนรับสู่ AI TO AI HOLDING 🤖\n\n"
            "ส่งรูป invoice หรือไฟล์ PDF มาได้เลย\n"
            "ระบบจะจัดพิกัดศุลกากร + ตรวจ FTA + OGA ให้อัตโนมัติ\n\n"
            "📌 ก่อนใช้งาน กรุณาผูกบัญชีด้วยคำสั่ง:\n"
            "พิมพ์: ผูกบัญชี [API Key ของคุณ]"
        ))

    elif event_type == "message":
        await _handle_message(event)

    elif event_type == "postback":
        # สำหรับ Flex Message buttons (Phase ถัดไป)
        pass


async def _handle_message(event: dict):
    """จัดการข้อความ / รูป / ไฟล์"""
    msg = event.get("message", {})
    msg_type = msg.get("type")
    reply_token = event.get("replyToken")
    user_id = event.get("source", {}).get("userId", "")

    if msg_type == "text":
        text = msg.get("text", "").strip()
        await _handle_text(reply_token, user_id, text)

    elif msg_type == "image":
        await _handle_invoice_upload(reply_token, user_id, msg["id"], "image.jpg")

    elif msg_type == "file":
        filename = msg.get("fileName", "document")
        await _handle_invoice_upload(reply_token, user_id, msg["id"], filename)

    else:
        await _reply_text(reply_token,
            "รองรับเฉพาะรูปภาพ (JPG/PNG) หรือไฟล์ (PDF/Excel/CSV) ครับ")


# ── Text Commands ──────────────────────────────────────────────────────────────

async def _handle_text(reply_token: str, user_id: str, text: str):
    """จัดการคำสั่งข้อความ"""

    if text.startswith("ผูกบัญชี") or text.lower().startswith("bind "):
        # ผูก LINE userId กับ API key
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            await _reply_text(reply_token,
                "กรุณาระบุ API Key:\nพิมพ์: ผูกบัญชี sk-aitai-xxxx...")
            return
        api_key = parts[1].strip()
        await _bind_account(reply_token, user_id, api_key)

    elif text in ("สถานะ", "status", "ยอด", "balance"):
        await _check_status(reply_token, user_id)

    elif text in ("ช่วยเหลือ", "help", "วิธีใช้"):
        await _reply_text(reply_token, (
            "📖 วิธีใช้ AI TO AI HOLDING LINE Bot:\n\n"
            "1. ผูกบัญชี: พิมพ์ 'ผูกบัญชี [API Key]'\n"
            "2. ส่งรูป invoice → รับผล HS Code + FTA + OGA\n"
            "3. ส่งไฟล์ PDF/Excel → วิเคราะห์ทั้งใบ\n"
            "4. พิมพ์ 'สถานะ' → ดู credit คงเหลือ\n\n"
            "🌐 เว็บ: https://web-production-c9da4.up.railway.app"
        ))

    else:
        await _reply_text(reply_token, (
            "ส่งรูป invoice หรือไฟล์ PDF มาได้เลยครับ\n"
            "พิมพ์ 'ช่วยเหลือ' เพื่อดูคำสั่งทั้งหมด"
        ))


# ── Invoice Processing ─────────────────────────────────────────────────────────

async def _handle_invoice_upload(reply_token: str, user_id: str,
                                 message_id: str, filename: str):
    """Download content จาก LINE → parse → classify → reply"""

    # 1. ตรวจว่าผูกบัญชีแล้ว
    binding = await _get_binding(user_id)
    if not binding:
        await _reply_text(reply_token, (
            "⚠️ กรุณาผูกบัญชีก่อนใช้งาน\n"
            "พิมพ์: ผูกบัญชี [API Key ของคุณ]\n\n"
            "ยังไม่มี API Key? สมัครที่: POST /v1/register"
        ))
        return

    api_key = binding["api_key"]

    # 2. Download content จาก LINE
    await _reply_text(reply_token, "⏳ กำลังวิเคราะห์ invoice... กรุณารอสักครู่")

    content = await _download_line_content(message_id)
    if not content:
        await _push_text(user_id, "❌ ดาวน์โหลดไฟล์ไม่สำเร็จ กรุณาลองใหม่")
        return

    if len(content) > MAX_FILE_SIZE:
        await _push_text(user_id, "❌ ไฟล์ใหญ่เกิน 10MB")
        return

    # 3. Parse + Classify
    try:
        from invoice_parser import parse_invoice
        from invoice_service import process_invoice

        parsed = await parse_invoice(filename, content)
        if "error" in parsed:
            await _push_text(user_id, f"❌ อ่านไฟล์ไม่ได้: {parsed['error']}")
            return

        items = parsed.get("items") or []
        if not items:
            await _push_text(user_id, "❌ ไม่พบรายการสินค้าในเอกสาร")
            return

        result = await process_invoice(api_key, filename, parsed)

        # 4. Format + Reply
        reply = _format_result(result)
        await _push_text(user_id, reply)

    except Exception as e:
        print(f"[LINE] process error: {e}")
        await _push_text(user_id, f"❌ ประมวลผลไม่สำเร็จ: {str(e)[:100]}")


def _format_result(result: dict) -> str:
    """Format invoice result เป็นข้อความ LINE"""
    if "error" in result:
        return f"❌ {result['error']}"

    lines = [
        f"✅ วิเคราะห์ Invoice สำเร็จ",
        f"📄 Invoice: {result.get('invoice_no', '-')}",
        f"📦 รายการ: {result.get('total_items', 0)} items",
        f"💰 มูลค่ารวม: ${result.get('total_value_usd', 0):,.2f}",
        f"🏦 ภาษีประมาณ: ${result.get('total_duty_estimate_usd', 0):,.2f}",
        f"💚 ประหยัด FTA: ${result.get('total_fta_saving_usd', 0):,.2f}",
        "",
    ]

    # Top 3 items
    items = result.get("items", [])[:3]
    for item in items:
        desc = (item.get("description") or "")[:30]
        hs = item.get("hs_code") or "-"
        conf = item.get("confidence", 0)
        fta = "🟢 FTA" if item.get("fta_eligible") else ""
        lines.append(f"  {item.get('line_no', '-')}. {desc}")
        lines.append(f"     HS: {hs} ({conf:.0%}) {fta}")

    if len(result.get("items", [])) > 3:
        lines.append(f"  ... อีก {len(result['items']) - 3} รายการ")

    # Billing
    billing = result.get("billing", {})
    if billing.get("charged"):
        lines.append(f"\n💳 หัก credit: ${billing['amount_usd']:.2f}")
        lines.append(f"   คงเหลือ: ${billing['balance_after']:.2f}")

    # Warnings
    warnings = result.get("warnings", [])
    if warnings:
        lines.append(f"\n⚠️ คำเตือน {len(warnings)} รายการ")
        for w in warnings[:2]:
            lines.append(f"  - {w.get('message', '')[:60]}")

    lines.append(f"\n🔗 ดูรายละเอียด: /v1/invoice/{result.get('submission_id', '')}")

    return "\n".join(lines)


# ── Account Binding ────────────────────────────────────────────────────────────

async def _bind_account(reply_token: str, user_id: str, api_key: str):
    """ผูก LINE userId กับ API key"""
    if not api_key.startswith("sk-aitai-"):
        await _reply_text(reply_token, "❌ API Key ไม่ถูกต้อง (ต้องขึ้นต้นด้วย sk-aitai-)")
        return

    try:
        from db_adapter import get_pool
        pool = await get_pool()
        hint = api_key[-8:]

        async with pool.acquire() as conn:
            # ตรวจว่า API key ถูกต้อง
            agent = await conn.fetchrow(
                "SELECT id, agent_name FROM client_agents "
                "WHERE api_key_hint=$1 AND status='ACTIVE'", hint
            )
            if not agent:
                await _reply_text(reply_token, "❌ API Key ไม่ถูกต้องหรือถูกระงับ")
                return

            # บันทึก binding
            now = datetime.now(timezone.utc).isoformat()
            await conn.execute("""
                INSERT INTO client_line_binding (line_user_id, agent_id, api_key_hint, bound_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (line_user_id) DO UPDATE SET
                    agent_id = $2, api_key_hint = $3, bound_at = $4
            """, user_id, agent["id"], hint, now)

        await _reply_text(reply_token, (
            f"✅ ผูกบัญชีสำเร็จ!\n"
            f"Agent: {agent['agent_name']}\n\n"
            f"ส่งรูป invoice มาได้เลยครับ 📸"
        ))

    except Exception as e:
        print(f"[LINE] bind error: {e}")
        await _reply_text(reply_token, f"❌ ผูกบัญชีไม่สำเร็จ: {str(e)[:80]}")


async def _get_binding(user_id: str) -> dict | None:
    """ดึง binding ของ LINE user"""
    try:
        from db_adapter import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT agent_id, api_key_hint FROM client_line_binding "
                "WHERE line_user_id = $1", user_id
            )
        if row:
            # reconstruct api_key hint for process_invoice
            # (process_invoice ต้องการ full key แต่เราเก็บแค่ hint)
            # ใช้ hint padded เป็น dummy key — _deduct_credit ใช้ [-8:] อยู่แล้ว
            return {
                "agent_id": row["agent_id"],
                "api_key": "line-bound-" + row["api_key_hint"],
                "api_key_hint": row["api_key_hint"],
            }
    except Exception as e:
        print(f"[LINE] get_binding error: {e}")
    return None


async def _check_status(reply_token: str, user_id: str):
    """ตรวจสถานะ credit ของ LINE user"""
    binding = await _get_binding(user_id)
    if not binding:
        await _reply_text(reply_token, "⚠️ ยังไม่ได้ผูกบัญชี\nพิมพ์: ผูกบัญชี [API Key]")
        return

    try:
        from db_adapter import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT ca.agent_name, COALESCE(cc.credit_balance, 0) AS balance,
                       COALESCE(cm.tier_level, 'VIP') AS tier
                FROM client_agents ca
                LEFT JOIN client_credits cc ON cc.agent_id = ca.id
                LEFT JOIN client_membership cm ON cm.agent_id = ca.id
                WHERE ca.id = $1
            """, binding["agent_id"])

        if row:
            await _reply_text(reply_token, (
                f"📊 สถานะบัญชี\n"
                f"Agent: {row['agent_name']}\n"
                f"Tier: {row['tier']}\n"
                f"Credit: ${float(row['balance']):.2f}\n"
            ))
        else:
            await _reply_text(reply_token, "❌ ไม่พบข้อมูลบัญชี")

    except Exception as e:
        await _reply_text(reply_token, f"❌ ตรวจสถานะไม่สำเร็จ: {str(e)[:60]}")


# ── LINE API Helpers ───────────────────────────────────────────────────────────

def _verify_signature(body: bytes, signature: str) -> bool:
    """Verify LINE webhook signature"""
    if not _CHANNEL_SECRET:
        return True  # skip if not configured
    mac = hmac.new(
        _CHANNEL_SECRET.encode(), body, hashlib.sha256
    ).digest()
    return signature == base64.b64encode(mac).decode()


async def _download_line_content(message_id: str) -> bytes | None:
    """Download image/file content จาก LINE"""
    if not _CHANNEL_TOKEN:
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{_LINE_DATA}/message/{message_id}/content",
                headers={"Authorization": f"Bearer {_CHANNEL_TOKEN}"},
            )
            if resp.status_code == 200:
                return resp.content
    except Exception as e:
        print(f"[LINE] download error: {e}")
    return None


async def _reply_text(reply_token: str, text: str):
    """Reply ข้อความกลับ LINE (ใช้ reply token — ฟรี)"""
    if not _CHANNEL_TOKEN or not reply_token:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{_LINE_API}/message/reply",
                headers={
                    "Authorization": f"Bearer {_CHANNEL_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "replyToken": reply_token,
                    "messages": [{"type": "text", "text": text[:5000]}],
                },
            )
    except Exception as e:
        print(f"[LINE] reply error: {e}")


async def _push_text(user_id: str, text: str):
    """Push ข้อความหาผู้ใช้ (ใช้เมื่อ reply token หมดอายุ — มีค่าใช้จ่าย)"""
    if not _CHANNEL_TOKEN or not user_id:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{_LINE_API}/message/push",
                headers={
                    "Authorization": f"Bearer {_CHANNEL_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "to": user_id,
                    "messages": [{"type": "text", "text": text[:5000]}],
                },
            )
    except Exception as e:
        print(f"[LINE] push error: {e}")
