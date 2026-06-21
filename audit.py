"""
audit.py - Evidence Chain Engine P-04
รองรับทั้ง aiosqlite.Connection และ PGConnection
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


async def get_last_hash(db) -> str:
    try:
        async with db.execute(
            "SELECT evidence_hash FROM audit_events ORDER BY occurred_at DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
            return row["evidence_hash"] if row else "GENESIS"
    except Exception:
        return "GENESIS"


async def log_event(
    db,
    *,
    event_type: str,
    actor_id: str,
    action: str,
    target_resource: Optional[str] = None,
    payload: Optional[dict] = None,
    result: Optional[dict] = None,
    confidence_score: Optional[float] = None,
    source_reference: Optional[str] = None,
    reasoning_steps: Optional[list] = None,
) -> str:
    """บันทึก audit event พร้อม SHA-256 chain (P-04). ไม่ raise exception."""
    event_id = str(uuid.uuid4())
    occurred_at = datetime.now(timezone.utc).isoformat()
    prev_hash = await get_last_hash(db)

    payload_str = json.dumps(payload or {}, ensure_ascii=False)
    result_str = json.dumps(result or {}, ensure_ascii=False)
    chain_input = f"{event_id}|{actor_id}|{action}|{payload_str}|{prev_hash}"
    evidence_hash = _sha256(chain_input)

    try:
        await db.execute(
            "INSERT INTO audit_events"
            " (id, event_type, actor_id, target_resource, action,"
            "  payload, result, confidence_score, source_reference,"
            "  occurred_at, prev_hash, evidence_hash)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                event_id, event_type, actor_id, target_resource, action,
                payload_str, result_str, confidence_score, source_reference,
                occurred_at, prev_hash, evidence_hash,
            ),
        )
        if reasoning_steps:
            rationale_id = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO audit_decision_rationale"
                " (id, event_id, reasoning_steps, principle_cited)"
                " VALUES (?,?,?,?)",
                (
                    rationale_id, event_id,
                    json.dumps(reasoning_steps, ensure_ascii=False),
                    "P-04,P-05",
                ),
            )
    except Exception as e:
        print(f"[AUDIT WARN] log_event non-fatal: {e}")

    return event_id
