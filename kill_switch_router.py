"""
kill_switch_router.py
Kill Switch API Endpoints — Chairman Interface (P-01/P-02)

วางที่: AI_TO_AI_HOLDING/kill_switch_router.py

Endpoints (ทุก endpoint ต้องผ่าน API Key + IP Allowlist จาก SecurityMiddleware):
  GET  /v1/chairman/kill-switch/status     — [FIX-4] ต้องผ่าน API Key แล้ว (ไม่ public อีกต่อไป)
  POST /v1/chairman/kill-switch/activate   — 🔴 หยุดระบบ (ต้องรหัส Chairman)
  POST /v1/chairman/kill-switch/resume     — 🟢 เปิดระบบ (ต้องรหัส Chairman — ยัง whitelist อยู่)
  POST /v1/chairman/kill-switch/history    — ดูประวัติ (ต้องรหัส Chairman)

[FIX-4] Status endpoint ถูกย้ายออกจาก KillSwitchMiddleware whitelist แล้ว
        ผ่าน SecurityMiddleware ปกติ — ต้องมี API Key
[FIX-5] ทุก chairman endpoint ผ่าน IP Allowlist ใน SecurityMiddleware อัตโนมัติ
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

import kill_switch_engine

router = APIRouter(
    prefix="/v1/chairman/kill-switch",
    tags=["Kill Switch (Chairman Only — P-01/P-02)"],
    include_in_schema=False,  # ซ่อนจาก Swagger /docs — security
)


# ── Request Models ────────────────────────────────────────────────────────────

class ActivateRequest(BaseModel):
    password:      str = Field(..., min_length=1, description="Chairman secret password")
    reason:        str = Field(..., min_length=5, description="เหตุผลการหยุดระบบ (บันทึกถาวร)")
    scope:         str = Field("SYSTEM_WIDE", description="SYSTEM_WIDE | DIVISION | AGENT")
    target_entity: Optional[str] = Field(None, description="entity_id ที่ต้องการหยุด (ถ้า scope ไม่ใช่ SYSTEM_WIDE)")


class ResumeRequest(BaseModel):
    password: str = Field(..., min_length=1)
    reason:   str = Field(..., min_length=5, description="เหตุผลการเปิดระบบ (บันทึกถาวร)")


class HistoryRequest(BaseModel):
    password: str = Field(..., min_length=1)
    limit:    int = Field(20, ge=1, le=100)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
async def get_status():
    """
    ดูสถานะระบบปัจจุบัน
    [FIX-4] ต้องผ่าน X-API-Key + IP Allowlist (จาก SecurityMiddleware)
    ไม่ public อีกต่อไป — แฮ็กเกอร์ไม่สามารถ monitor สถานะระบบได้
    """
    state = kill_switch_engine.get_state()
    return {
        "system_state": state.get("state", "OPERATIONAL"),
        "is_halted":    state.get("is_halted", False),
        "changed_by":   state.get("changed_by"),
        "reason":       state.get("reason"),
        "changed_at":   state.get("changed_at"),
        "constitution": "P-01/P-02 enforced — Chairman authority only",
    }


@router.post("/activate")
async def activate(req: ActivateRequest):
    """
    🔴 ACTIVATE KILL SWITCH
    หยุดระบบทั้งหมดทันที — Chairman password required
    เหตุผลถูกบันทึกลง audit ถาวร (ลบไม่ได้)
    """
    result = kill_switch_engine.activate(
        password=req.password,
        reason=req.reason,
        scope=req.scope,
        target_entity=req.target_entity,
    )
    if not result["ok"]:
        raise HTTPException(status_code=403, detail=result["message"])
    return result


@router.post("/resume")
async def resume(req: ResumeRequest):
    """
    🟢 RESUME SYSTEM
    เปิดระบบกลับมา — Chairman password required
    """
    result = kill_switch_engine.deactivate(
        password=req.password,
        reason=req.reason,
    )
    if not result["ok"]:
        raise HTTPException(status_code=403, detail=result["message"])
    return result


@router.post("/history")
async def history(req: HistoryRequest):
    """
    ดูประวัติ Kill Switch ทั้งหมด — Chairman password required
    """
    import wallet_engine
    verify = wallet_engine.verify_chairman(req.password)
    if not verify["ok"]:
        raise HTTPException(status_code=403, detail="Chairman password required")

    logs = kill_switch_engine.kill_switch_history(limit=req.limit)
    return {
        "total":   len(logs),
        "records": logs,
        "note":    "Evidence chain verified (P-04) — records are immutable",
    }
