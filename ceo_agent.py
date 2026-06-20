"""
agents/ceo_agent.py
AI CEO — สมองกลางขององค์กร
รับคำสั่งจาก Chairman → วิเคราะห์ → กระจายงานไป Offices → รวบรวมรายงาน
ทำงานใน Mock Mode: ไม่เรียก Claude API
"""
import uuid
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

from holding_config import MOCK_MODE


@dataclass
class CEODecision:
    decision_id: str
    command_received: str
    analysis: str
    actions_dispatched: list[dict]
    summary: str
    confidence: float
    timestamp: str


class AICEOAgent:
    """
    AI CEO Agent
    ใน Mock Mode: rule-based decision engine
    ใน Real Mode: Claude API with full org context
    """
    ENTITY_ID = "ent-ai-ceo"
    NAME = "AI CEO"

    # ── รู้จัก Offices ทั้งหมด ──
    OFFICES = {
        "knowledge":   "ent-office-knowledge",
        "governance":  "ent-office-governance",
        "audit":       "ent-office-audit",
        "risk":        "ent-office-risk",
        "treasury":    "ent-office-treasury",
        "trust":       "ent-office-trust",
        "discovery":   "ent-office-discovery",
        "customs":     "ent-div-customs",
    }

    def __init__(self):
        self.mode = "MOCK" if MOCK_MODE else "REAL"

    async def process_command(self, command: str, context: Optional[dict] = None) -> CEODecision:
        """รับคำสั่งจาก Chairman และตัดสินใจกระจายงาน"""
        if MOCK_MODE:
            return await self._mock_process(command, context)
        else:
            return await self._real_process(command, context)

    async def _mock_process(self, command: str, context: Optional[dict] = None) -> CEODecision:
        """Mock: rule-based routing ตาม keyword"""
        cmd_lower = command.lower()
        decision_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        actions = []

        # ── Routing Logic ──────────────────────────────────────
        if any(k in cmd_lower for k in ["revenue", "money", "income", "รายได้", "เงิน"]):
            actions = [
                self._dispatch("treasury", "REPORT_REQUEST", "Generate revenue summary"),
                self._dispatch("audit",    "REPORT_REQUEST", "Pull financial audit log"),
            ]
            analysis = "Command relates to financial performance. Routing to Treasury and Audit."
            summary  = "Requested revenue report from Treasury Office and audit trail from Audit Office."

        elif any(k in cmd_lower for k in ["risk", "threat", "danger", "ความเสี่ยง"]):
            actions = [
                self._dispatch("risk",       "REPORT_REQUEST", "Run risk assessment"),
                self._dispatch("governance", "REPORT_REQUEST", "Check policy compliance"),
            ]
            analysis = "Risk-related command. Routing to Risk and Governance."
            summary  = "Initiated risk assessment and compliance check."

        elif any(k in cmd_lower for k in ["classify", "invoice", "hs", "customs", "ศุลกากร"]):
            actions = [
                self._dispatch("customs", "TASK_ASSIGN", "Process classification request"),
            ]
            analysis = "Classification task. Routing directly to Customs Intelligence Division."
            summary  = "Dispatched classification task to Customs Division."

        elif any(k in cmd_lower for k in ["learn", "knowledge", "lesson", "เรียนรู้"]):
            actions = [
                self._dispatch("knowledge", "TASK_ASSIGN", "Process pending learning triggers"),
                self._dispatch("trust",     "TASK_ASSIGN", "Evaluate confidence improvements"),
            ]
            analysis = "Learning cycle command. Routing to Knowledge and Trust offices."
            summary  = "Initiated learning loop — Knowledge and Trust offices engaged."

        elif any(k in cmd_lower for k in ["market", "discover", "client", "ลูกค้า"]):
            actions = [
                self._dispatch("discovery", "TASK_ASSIGN", "Identify new AI agent clients"),
                self._dispatch("trust",     "TASK_ASSIGN", "Update external confidence rating"),
            ]
            analysis = "Market development command. Routing to Discovery and Trust."
            summary  = "Discovery Office tasked with client outreach. Trust Office updating ratings."

        elif any(k in cmd_lower for k in ["status", "report", "summary", "สถานะ", "รายงาน"]):
            actions = [o for name, o in [
                ("treasury",   self._dispatch("treasury",   "REPORT_REQUEST", "Revenue summary")),
                ("audit",      self._dispatch("audit",      "REPORT_REQUEST", "Event summary")),
                ("risk",       self._dispatch("risk",       "REPORT_REQUEST", "Risk summary")),
                ("knowledge",  self._dispatch("knowledge",  "REPORT_REQUEST", "Knowledge state")),
            ]]
            analysis = "Full status requested. Polling all core offices."
            summary  = "Full org status report initiated across Treasury, Audit, Risk, and Knowledge."

        else:
            # ไม่รู้จัก command → escalate ถึง Chairman
            actions = [
                self._dispatch("governance", "ESCALATION",
                               f"Unknown command received: '{command}' — awaiting Chairman clarification")
            ]
            analysis = "Command not recognized by routing engine. Escalating to Governance for Chairman review."
            summary  = "Command unclear. Governance Office notified. Awaiting Chairman instruction."

        return CEODecision(
            decision_id=decision_id,
            command_received=command,
            analysis=f"[MOCK CEO] {analysis}",
            actions_dispatched=actions,
            summary=f"[MOCK CEO] {summary}",
            confidence=0.88 if actions else 0.40,
            timestamp=now,
        )

    def _dispatch(self, office_key: str, task_type: str, detail: str) -> dict:
        return {
            "to": self.OFFICES.get(office_key, office_key),
            "office": office_key.upper(),
            "task_type": task_type,
            "detail": detail,
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _real_process(self, command: str, context: Optional[dict] = None) -> CEODecision:
        """Real Mode: เรียก Claude API พร้อม org context (Phase 2)"""
        raise NotImplementedError("Real CEO Agent requires MOCK_MODE=false and valid API key")

    async def daily_briefing(self, db) -> dict:
        """สรุปรายวันให้ Chairman — รวบรวมจากทุก Office"""
        now = datetime.now(timezone.utc)
        return {
            "briefing_date": now.date().isoformat(),
            "prepared_by": self.NAME,
            "mode": self.mode,
            "sections": {
                "treasury":  "[MOCK] Revenue pipeline operational. Split pipeline P-03 active.",
                "audit":     "[MOCK] Evidence chain intact. No anomalies detected.",
                "risk":      "[MOCK] No high-risk transactions in last 24h.",
                "knowledge": "[MOCK] 0 pending learning triggers.",
                "discovery": "[MOCK] Sandbox API available for new client onboarding.",
                "trust":     "[MOCK] Avg confidence score: 88%.",
            },
            "chairman_action_required": False,
            "notes": "All systems nominal. Mock mode active — no real API calls.",
        }
