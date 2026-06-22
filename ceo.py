"""
api/ceo.py
Chairman → AI CEO Command Interface
ท่านประธานส่งคำสั่งมาที่นี่ → AI CEO วิเคราะห์ → กระจายงาน → รายงานกลับ
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional

from db_adapter import get_pool
from ceo_agent import AICEOAgent
from office_heads import OFFICE_HEADS

router = APIRouter(prefix="/v1/ceo", tags=["AI CEO (Chairman Interface)"])

ceo = AICEOAgent()


class ChairmanCommand(BaseModel):
    command: str = Field(..., description="คำสั่งจาก Chairman")
    context: Optional[dict] = None


class OrgStatusResponse(BaseModel):
    briefing_date: str
    prepared_by: str
    mode: str
    sections: dict
    chairman_action_required: bool
    notes: str


@router.post(
    "/command",
    summary="ส่งคำสั่งจาก Chairman → AI CEO",
    description="AI CEO รับคำสั่ง วิเคราะห์ และกระจายงานไปทุก Office ที่เกี่ยวข้อง",
)
async def chairman_command(req: ChairmanCommand):
    pool = await get_pool()
    # AI CEO รับคำสั่ง
    decision = await ceo.process_command(req.command, req.context)

    # Office Heads ดำเนินการตาม actions ที่ CEO dispatch
    office_results = []
    async with pool.acquire() as conn:
        for action in decision.actions_dispatched:
            office_key = action["office"].lower()
            head = OFFICE_HEADS.get(office_key)
            if head:
                report = await head.handle(action["task_type"], action, conn)
                office_results.append({
                    "office": report.office,
                    "status": report.status,
                    "findings": report.findings,
                    "recommendation": report.recommendation,
                })

    return {
        "decision_id": decision.decision_id,
        "command": decision.command_received,
        "ceo_analysis": decision.analysis,
        "ceo_summary": decision.summary,
        "confidence": decision.confidence,
        "offices_engaged": office_results,
        "timestamp": decision.timestamp,
    }


@router.get(
    "/briefing",
    response_model=OrgStatusResponse,
    summary="รายงานสถานะองค์กรรายวัน (Daily Briefing)",
    description="AI CEO รวบรวมรายงานจากทุก Office แล้วสรุปให้ Chairman",
)
async def daily_briefing():
    pool = await get_pool()
    async with pool.acquire() as conn:
        briefing = await ceo.daily_briefing(conn)
        # เสริมด้วยข้อมูลจริงจาก Office Heads
        for key, head in OFFICE_HEADS.items():
            report = await head.handle("REPORT_REQUEST", {}, conn)
            briefing["sections"][key] = report.findings

    return briefing


@router.get(
    "/org-chart",
    summary="โครงสร้างองค์กรปัจจุบัน",
)
async def org_chart():
    return {
        "chairman": {
            "role": "Supreme Authority",
            "entity_id": "ent-chairman",
            "kill_switch": True,
        },
        "ai_ceo": {
            "role": "AI CEO",
            "entity_id": AICEOAgent.ENTITY_ID,
            "mode": "MOCK" if __import__('holding_config').MOCK_MODE else "REAL",
            "reports_to": "ent-chairman",
        },
        "offices": [
            {
                "name": head.OFFICE_NAME,
                "entity_id": head.ENTITY_ID,
                "reports_to": AICEOAgent.ENTITY_ID,
                "status": "ACTIVE",
            }
            for head in OFFICE_HEADS.values()
        ],
        "divisions": [
            {
                "name": "Customs Intelligence Division",
                "entity_id": "ent-div-customs",
                "reports_to": AICEOAgent.ENTITY_ID,
                "status": "ACTIVE",
                "agents": ["Classification Agent"],
            }
        ],
    }
