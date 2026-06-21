"""
cache_classification.py
HS Classification Cache Layer
- Cache lookup before Claude call
- Save candidates log after Claude call
- Feedback ingestion -> promote/demote cache
"""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Optional

# ── Helpers ──────────────────────────────────────────────────────────────────

def _desc_hash(description: str) -> str:
    normalized = description.lower().strip()
    return hashlib.sha256(normalized.encode()).hexdigest()

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _evidence_hash(data: dict) -> str:
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()

# ── Cache Lookup ──────────────────────────────────────────────────────────────

async def cache_lookup(db, description: str) -> Optional[dict]:
    """
    ค้นหาจาก cache ก่อน Claude
    คืน dict ถ้าเจอ (source + hs_code + confidence) หรือ None
    """
    h = _desc_hash(description)
    try:
        row = await db.fetchone(
            """SELECT hs_code, hs_code_11, hs_description, hs_description_th,
                      confidence_score, source, hit_count
               FROM hs_classification_cache
               WHERE description_hash = ?
                 AND (expires_at IS NULL OR expires_at > ?)""",
            (h, _now())
        )
        if row:
            # อัปเดต hit_count + last_hit_at
            await db.execute(
                """UPDATE hs_classification_cache
                   SET hit_count = hit_count + 1, last_hit_at = ?
                   WHERE description_hash = ?""",
                (_now(), h)
            )
            await db.commit()
            return dict(row)
    except Exception:
        pass
    return None

# ── Save to Cache ─────────────────────────────────────────────────────────────

async def cache_save(db, description: str, best_candidate: dict, source: str = "CLAUDE"):
    """
    บันทึก best candidate เข้า cache
    เรียกหลัง Claude คืนผล confidence >= 0.85
    """
    h = _desc_hash(description)
    data = {**best_candidate, "description_hash": h, "source": source}
    try:
        await db.execute(
            """INSERT INTO hs_classification_cache
               (description_hash, description_sample, hs_code, hs_code_11,
                hs_description, hs_description_th, confidence_score, source, evidence_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(description_hash) DO UPDATE SET
                 hs_code = excluded.hs_code,
                 hs_code_11 = excluded.hs_code_11,
                 confidence_score = excluded.confidence_score,
                 source = CASE WHEN excluded.source IN ('CONFIRMED','CHAIRMAN_OVERRIDE')
                               THEN excluded.source ELSE hs_classification_cache.source END,
                 last_hit_at = excluded.last_hit_at,
                 hit_count = hs_classification_cache.hit_count + 1,
                 evidence_hash = excluded.evidence_hash""",
            (
                h,
                description[:200],
                best_candidate.get("hs_code"),
                best_candidate.get("hs_code_11"),
                best_candidate.get("hs_description"),
                best_candidate.get("hs_description_th"),
                best_candidate.get("confidence_score", 0),
                source,
                _evidence_hash(data),
            )
        )
        await db.commit()
    except Exception:
        pass

# ── Save Candidates Log ───────────────────────────────────────────────────────

async def log_candidates(db, session_id: str, session_type: str,
                         description: str, candidates: list) -> list:
    """
    บันทึก candidates ทุกตัวลง classification_candidates_log
    คืน list ของ log_id แต่ละตัว (ใช้สำหรับ feedback)
    """
    log_ids = []
    for c in candidates:
        import uuid
        log_id = str(uuid.uuid4()).replace("-", "")
        data = {"session_id": session_id, "hs_code": c.get("hs_code"), "rank": c.get("rank", 0)}
        try:
            await db.execute(
                """INSERT INTO classification_candidates_log
                   (id, session_id, session_type, description, candidate_rank,
                    hs_code, hs_code_11, hs_description, confidence_score,
                    source_reference, was_selected, evidence_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    log_id,
                    session_id,
                    session_type,
                    description[:500],
                    c.get("rank", 0),
                    c.get("hs_code"),
                    c.get("hs_code_11"),
                    c.get("hs_description"),
                    c.get("confidence_score", 0),
                    c.get("source_reference", ""),
                    1 if c.get("rank") == 1 else 0,
                    _evidence_hash(data),
                )
            )
            log_ids.append(log_id)
        except Exception:
            pass
    try:
        await db.commit()
    except Exception:
        pass
    return log_ids

# ── Feedback ──────────────────────────────────────────────────────────────────

async def submit_feedback(db, log_id: str, status: str,
                          amended_hs: Optional[str], feedback_by: str) -> bool:
    """
    รับ feedback จากลูกค้า/Chairman
    status: CONFIRMED | REJECTED | AMENDED
    """
    if status not in ("CONFIRMED", "REJECTED", "AMENDED"):
        return False
    try:
        # อัปเดต log
        await db.execute(
            """UPDATE classification_candidates_log
               SET feedback_status = ?, amended_hs_code = ?,
                   feedback_by = ?, feedback_at = ?, learning_triggered = 1
               WHERE id = ?""",
            (status, amended_hs, feedback_by, _now(), log_id)
        )
        # Queue action
        action = ("PROMOTE_TO_CACHE" if status == "CONFIRMED"
                  else "DEMOTE_FROM_CACHE" if status == "REJECTED"
                  else "CREATE_LESSON")
        await db.execute(
            """INSERT INTO cache_feedback_queue (candidate_log_id, action)
               VALUES (?, ?)""",
            (log_id, action)
        )
        await db.commit()
        return True
    except Exception:
        return False

# ── Cache Stats ────────────────────────────────────────────────────────────────

async def cache_stats(db) -> dict:
    """สรุปสถานะ cache สำหรับ Chairman dashboard"""
    try:
        total = (await db.fetchone("SELECT COUNT(*) as n FROM hs_classification_cache"))["n"]
        confirmed = (await db.fetchone(
            "SELECT COUNT(*) as n FROM hs_classification_cache WHERE source='CONFIRMED'"))["n"]
        top_hits = await db.fetchall(
            """SELECT hs_code, description_sample, hit_count, source
               FROM hs_classification_cache
               ORDER BY hit_count DESC LIMIT 10""")
        pending_feedback = (await db.fetchone(
            "SELECT COUNT(*) as n FROM cache_feedback_queue WHERE status='PENDING'"))["n"]
        return {
            "total_cached": total,
            "confirmed": confirmed,
            "pending_feedback_queue": pending_feedback,
            "top_hits": [dict(r) for r in (top_hits or [])],
        }
    except Exception:
        return {"total_cached": 0, "confirmed": 0, "pending_feedback_queue": 0, "top_hits": []}
