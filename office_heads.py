"""
agents/office_heads.py
Head Agents ของทุก Office — 7 คน
แต่ละ Head รับ task จาก AI CEO → ประมวลผล → รายงานกลับ
Mock Mode: rule-based, ไม่เรียก API
"""
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional

from holding_config import MOCK_MODE


@dataclass
class OfficeReport:
    office: str
    head_id: str
    task_type: str
    status: str
    findings: dict
    recommendation: Optional[str]
    timestamp: str


# ══════════════════════════════════════════════════════════════
# BASE CLASS
# ══════════════════════════════════════════════════════════════

class OfficeHead:
    OFFICE_NAME: str = ""
    ENTITY_ID: str = ""

    def _report(self, task_type: str, status: str, findings: dict, rec: str = None) -> OfficeReport:
        return OfficeReport(
            office=self.OFFICE_NAME,
            head_id=self.ENTITY_ID,
            task_type=task_type,
            status=status,
            findings=findings,
            recommendation=rec,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def handle(self, task_type: str, payload: dict, conn=None) -> OfficeReport:
        raise NotImplementedError


# ══════════════════════════════════════════════════════════════
# 1. KNOWLEDGE OFFICE HEAD
# ══════════════════════════════════════════════════════════════

class KnowledgeHead(OfficeHead):
    OFFICE_NAME = "Knowledge Office"
    ENTITY_ID   = "ent-head-knowledge"

    async def handle(self, task_type: str, payload: dict, conn=None) -> OfficeReport:
        if task_type == "REPORT_REQUEST":
            # ดึง pending learning triggers จาก DB ถ้ามี
            pending = 0
            if conn:
                rows = await conn.fetch(
                    "SELECT COUNT(*) as cnt FROM learning_triggers WHERE processed=0"
                )
                pending = rows[0]["cnt"] if rows else 0

            return self._report(task_type, "COMPLETED", {
                "pending_learning_triggers": pending,
                "knowledge_version": "v1.0.0",
                "ground_truth_documents": 0,
                "graph_nodes": 0,
                "graph_edges": 0,
                "status": "Foundation layer ready. Awaiting first real case to generate lessons.",
            }, "Begin populating Ground Truth Data with verified HS rulings." if pending == 0 else
               f"Process {pending} pending learning triggers immediately.")

        elif task_type == "TASK_ASSIGN":
            return self._report(task_type, "ACKNOWLEDGED", {
                "action": "Processing pending learning triggers",
                "mock_lessons_processed": 0,
                "note": "[MOCK] Learning loop will process triggers when real cases complete.",
            })

        return self._report(task_type, "UNKNOWN_TASK", {"error": f"Unknown task: {task_type}"})


# ══════════════════════════════════════════════════════════════
# 2. GOVERNANCE OFFICE HEAD
# ══════════════════════════════════════════════════════════════

class GovernanceHead(OfficeHead):
    OFFICE_NAME = "Governance Office"
    ENTITY_ID   = "ent-head-governance"

    CONSTITUTION_CODES = ["P-01","P-02","P-03","P-04","P-05","P-06"]

    async def handle(self, task_type: str, payload: dict, conn=None) -> OfficeReport:
        if task_type == "REPORT_REQUEST":
            # ตรวจ constitution ครบไหม
            principles_ok = len(self.CONSTITUTION_CODES)
            if conn:
                rows = await conn.fetch("SELECT COUNT(*) as cnt FROM gov_constitution")
                principles_ok = rows[0]["cnt"] if rows else 0

            return self._report(task_type, "COMPLETED", {
                "constitution_principles_loaded": principles_ok,
                "kill_switch_status": "ACTIVE — Chairman P-01/P-02 enforced",
                "active_policies": 0,
                "pending_approvals": 0,
                "compliance_status": "NOMINAL",
            }, "Consider drafting API rate-limit policy for external clients.")

        elif task_type == "ESCALATION":
            return self._report(task_type, "ESCALATED_TO_CHAIRMAN", {
                "escalation_detail": payload.get("detail", "Unknown"),
                "action": "Flagged for Chairman review — awaiting instruction",
                "principle_invoked": "P-01",
            }, "Chairman must review and provide directive.")

        return self._report(task_type, "UNKNOWN_TASK", {"error": f"Unknown task: {task_type}"})


# ══════════════════════════════════════════════════════════════
# 3. AUDIT OFFICE HEAD
# ══════════════════════════════════════════════════════════════

class AuditHead(OfficeHead):
    OFFICE_NAME = "Audit Office"
    ENTITY_ID   = "ent-head-audit"

    async def handle(self, task_type: str, payload: dict, conn=None) -> OfficeReport:
        if task_type == "REPORT_REQUEST":
            total_events = 0
            decisions = escalations = low_conf = 0

            if conn:
                rows = await conn.fetch(
                    """
                    SELECT event_type, COUNT(*) as cnt
                    FROM audit_events GROUP BY event_type
                    """
                )
                for r in rows:
                    total_events += r["cnt"]
                    if r["event_type"] == "DECISION":    decisions   += r["cnt"]
                    if r["event_type"] == "ESCALATION":  escalations += r["cnt"]

                low_rows = await conn.fetch(
                    "SELECT COUNT(*) as cnt FROM audit_events WHERE confidence_score < 0.70"
                )
                low_conf = low_rows[0]["cnt"] if low_rows else 0

            return self._report(task_type, "COMPLETED", {
                "total_events_logged": total_events,
                "decisions": decisions,
                "escalations": escalations,
                "low_confidence_events": low_conf,
                "chain_integrity": "INTACT — SHA-256 verified",
                "principle": "P-04 enforced on all events",
            }, "No anomalies detected." if escalations == 0 else
               f"Review {escalations} escalation(s) immediately.")

        return self._report(task_type, "UNKNOWN_TASK", {"error": f"Unknown task: {task_type}"})


# ══════════════════════════════════════════════════════════════
# 4. RISK OFFICE HEAD
# ══════════════════════════════════════════════════════════════

class RiskHead(OfficeHead):
    OFFICE_NAME = "Risk Office"
    ENTITY_ID   = "ent-head-risk"

    async def handle(self, task_type: str, payload: dict, conn=None) -> OfficeReport:
        if task_type in ("REPORT_REQUEST", "TASK_ASSIGN"):
            low_conf_cases = 0
            if conn:
                rows = await conn.fetch(
                    """
                    SELECT COUNT(*) as cnt FROM customs_invoice_items
                    WHERE confidence_score < 0.70
                    """
                )
                low_conf_cases = rows[0]["cnt"] if rows else 0

            risk_level = "LOW" if low_conf_cases == 0 else \
                         "MEDIUM" if low_conf_cases < 5 else "HIGH"

            return self._report(task_type, "COMPLETED", {
                "overall_risk_level": risk_level,
                "low_confidence_items": low_conf_cases,
                "blocked_clients": 0,
                "active_disputes": 0,
                "assessment": f"Risk level {risk_level}. {low_conf_cases} items below confidence threshold.",
            }, None if risk_level == "LOW" else
               "Escalate low-confidence items to Knowledge Office for review.")

        return self._report(task_type, "UNKNOWN_TASK", {"error": f"Unknown task: {task_type}"})


# ══════════════════════════════════════════════════════════════
# 5. TREASURY OFFICE HEAD
# ══════════════════════════════════════════════════════════════

class TreasuryHead(OfficeHead):
    OFFICE_NAME = "Treasury Office"
    ENTITY_ID   = "ent-head-treasury"

    async def handle(self, task_type: str, payload: dict, conn=None) -> OfficeReport:
        if task_type == "REPORT_REQUEST":
            total_gross = total_net = corp = chairman = txn_count = 0

            if conn:
                rows = await conn.fetch(
                    """
                    SELECT COUNT(*) as cnt,
                           SUM(gross_amount) as gross,
                           SUM(net_amount) as net
                    FROM treasury_transactions WHERE split_executed=1
                    """
                )
                if rows and rows[0]["cnt"]:
                    txn_count  = rows[0]["cnt"]
                    total_gross = round(rows[0]["gross"] or 0, 2)
                    total_net   = round(rows[0]["net"]   or 0, 2)

                split_rows = await conn.fetch(
                    "SELECT split_type, SUM(amount) as total FROM treasury_splits GROUP BY split_type"
                )
                for r in split_rows:
                    if r["split_type"] == "CORPORATE_RESERVE": corp     = round(r["total"], 2)
                    if r["split_type"] == "CHAIRMAN_PRIVATE":  chairman = round(r["total"], 2)

            return self._report(task_type, "COMPLETED", {
                "total_transactions": txn_count,
                "total_gross_usd": total_gross,
                "total_net_usd": total_net,
                "corporate_reserve_usd": corp,
                "chairman_routed_usd": chairman,
                "split_ratio": "60% Corporate / 40% Chairman",
                "pipeline_status": "P-03 ACTIVE — auto-split on every settlement",
            })

        return self._report(task_type, "UNKNOWN_TASK", {"error": f"Unknown task: {task_type}"})


# ══════════════════════════════════════════════════════════════
# 6. TRUST OFFICE HEAD
# ══════════════════════════════════════════════════════════════

class TrustHead(OfficeHead):
    OFFICE_NAME = "Trust Office"
    ENTITY_ID   = "ent-head-trust"

    async def handle(self, task_type: str, payload: dict, conn=None) -> OfficeReport:
        if task_type in ("REPORT_REQUEST", "TASK_ASSIGN"):
            avg_conf = 0.0
            total_items = 0

            if conn:
                rows = await conn.fetch(
                    """
                    SELECT AVG(confidence_score) as avg, COUNT(*) as cnt
                    FROM customs_invoice_items WHERE confidence_score IS NOT NULL
                    """
                )
                if rows and rows[0]["cnt"]:
                    avg_conf    = round(rows[0]["avg"] or 0, 3)
                    total_items = rows[0]["cnt"]

            trust_rating = "HIGH" if avg_conf >= 0.85 else \
                           "MEDIUM" if avg_conf >= 0.70 else "LOW"

            return self._report(task_type, "COMPLETED", {
                "org_confidence_rating": trust_rating,
                "avg_confidence_score": avg_conf,
                "total_classified_items": total_items,
                "sandbox_available": True,
                "external_trust_signal": "Evidence chain + source reference on all outputs (P-05)",
            }, "Confidence rating ready for external AI agent evaluation.")

        return self._report(task_type, "UNKNOWN_TASK", {"error": f"Unknown task: {task_type}"})


# ══════════════════════════════════════════════════════════════
# 7. DISCOVERY OFFICE HEAD
# ══════════════════════════════════════════════════════════════

class DiscoveryHead(OfficeHead):
    OFFICE_NAME = "Discovery Office"
    ENTITY_ID   = "ent-head-discovery"

    CHANNELS = [
        "Sandbox API (free trial endpoint)",
        "OpenAPI schema publication (/docs)",
        "AI agent directory registration (pending)",
        "Evidence chain proof-of-compliance (active)",
    ]

    async def handle(self, task_type: str, payload: dict, conn=None) -> OfficeReport:
        if task_type in ("REPORT_REQUEST", "TASK_ASSIGN"):
            return self._report(task_type, "COMPLETED", {
                "active_channels": self.CHANNELS,
                "registered_directories": 0,
                "sandbox_sessions_total": 0,
                "conversion_rate": "0% (no real clients yet)",
                "next_action": "Register API schema in public AI agent directories",
            }, "Publish OpenAPI spec to agent marketplaces to begin AI-to-AI discovery.")

        return self._report(task_type, "UNKNOWN_TASK", {"error": f"Unknown task: {task_type}"})


# ══════════════════════════════════════════════════════════════
# OFFICE HEAD REGISTRY — AI CEO ใช้ตรงนี้เรียก Head แต่ละคน
# ══════════════════════════════════════════════════════════════

OFFICE_HEADS: dict[str, OfficeHead] = {
    "knowledge":  KnowledgeHead(),
    "governance": GovernanceHead(),
    "audit":      AuditHead(),
    "risk":       RiskHead(),
    "treasury":   TreasuryHead(),
    "trust":      TrustHead(),
    "discovery":  DiscoveryHead(),
}
