"""
treasury_wallet_router.py
Chairman Wallet API Endpoints

วางที่: AI_TO_AI_HOLDING/treasury_wallet_router.py

Endpoints (Chairman เท่านั้น):
  POST /v1/treasury/chairman/wallet/verify   — ตรวจว่า password ถูกต้อง
  POST /v1/treasury/chairman/wallet/update   — เปลี่ยน wallet address
  POST /v1/treasury/chairman/wallet/password — เปลี่ยนรหัสลับ
  GET  /v1/treasury/chairman/wallet/status   — ดูสถานะ (ไม่แสดง address)

Security rules:
  - ไม่มี endpoint ใด return wallet address ใน response
  - rate limit 5 ครั้ง / 30 นาที (enforce ใน wallet_engine)
  - ทุก request บันทึกลง wallet_access_log (P-04)
  - ไม่มี GET parameter รับ password — POST body เท่านั้น
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

import wallet_engine

router = APIRouter(
    prefix="/v1/treasury/chairman",
    tags=["Chairman Wallet (Private)"],
    include_in_schema=False,  # ซ่อนจาก Swagger /docs — security
)


# ── Request Models ────────────────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    password: str = Field(..., min_length=1, description="Chairman secret password")


class UpdateWalletRequest(BaseModel):
    password:   str = Field(..., min_length=1)
    new_wallet: str = Field(..., min_length=10, description="New wallet address")


class UpdatePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=12)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/wallet/verify")
async def verify_wallet(req: VerifyRequest):
    """
    ยืนยันตัวตน Chairman — คืนแค่ ok/fail
    ไม่เปิดเผย wallet address ใน response
    """
    result = wallet_engine.verify_chairman(req.password)
    # ไม่ส่ง wallet กลับ — แค่บอกว่าผ่านหรือไม่
    return {
        "ok":      result["ok"],
        "message": result["message"],
        "wallet":  "VERIFIED — see treasury routing" if result["ok"] else None,
    }


@router.post("/wallet/update")
async def update_wallet(req: UpdateWalletRequest):
    """
    เปลี่ยน Wallet Address — ต้องผ่านรหัสลับก่อน
    """
    result = wallet_engine.update_wallet(req.password, req.new_wallet)
    return {"ok": result["ok"], "message": result["message"]}


@router.post("/wallet/password")
async def update_password(req: UpdatePasswordRequest):
    """
    เปลี่ยนรหัสลับ Chairman — ต้องใส่รหัสเก่าถูกต้อง
    """
    result = wallet_engine.update_password(req.old_password, req.new_password)
    return {"ok": result["ok"], "message": result["message"]}


@router.get("/wallet/status")
async def wallet_status():
    """
    ดูสถานะ Wallet — ไม่แสดง address, แสดงเฉพาะ status/security info
    """
    return wallet_engine.wallet_status()
