"""
cache_classification.py
HS Classification Cache Layer — PostgreSQL (asyncpg)
- Cache lookup before Claude call
- Save candidates log after Claude call
- Feedback ingestion → promote / demote cache entries
- process_feedback_queue() — runs the pending actions
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

# ── Helpers ───────────────────────────────────────────────────────────────────

def _desc_hash(description: str) -> str:
    """Canonical key — delegates to cache_key_utils (แก้ที่นั่นที่เดียว)"""
    from cache_key_utils import make_cache_key
    return make_cache_key(description)

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _evidence_hash(data: dict) -> str:
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()

async def _get_pool():
    from db_adapter import get_pool, USE_POSTGRES
    if not USE_POSTGRES:
        return None
    return await get_pool()

# ── Cache Lookup ──────────────────────────────────────────────────────────────

async def cache_lookup(db, description: str) -> Optional[dict]:
    """
    ค้นหาจาก cache ก่อน Claude
    db: ไม่ได้ใช้แล้ว (backward compat) — ดึง pool จาก db_adapter เอง
    คืน dict หรือ None
    """
    h = _desc_hash(description)
    pool = await _get_pool()
    if not pool:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT hs_code, hs_code_11, hs_description, hs_description_th,
                          confidence_score, source, hit_count
                   FROM hs_classification_cache
                   WHERE cache_key = $1
                     AND (expires_at IS NULL OR expires_at > NOW())""",
                h,
            )
            if row:
                await conn.execute(
                    """UPDATE hs_classification_cache
                       SET hit_count = hit_count + 1, last_hit_at = NOW()
                       WHERE cache_key = $1""",
                    h,
                )
                return dict(row)
    except Exception:
        pass
    return None


# ── Save to Cache ─────────────────────────────────────────────────────────────

async def cache_save(db, description: str, best_candidate: dict, source: str = "CLAUDE"):
    """
    บันทึก best candidate เข้า cache
    db: backward compat — ไม่ได้ใช้
    """
    h = _desc_hash(description)
    data = {**best_candidate, "cache_key": h, "source": source}
    pool = await _get_pool()
    if not pool:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO hs_classification_cache
                   (cache_key, description_sample, hs_code, hs_code_11,
                    hs_description, hs_description_th, confidence_score, source, evidence_hash)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                   ON CONFLICT (cache_key) DO UPDATE SET
                     hs_code          = EXCLUDED.hs_code,
                     hs_code_11       = EXCLUDED.hs_code_11,
                     confidence_score = EXCLUDED.confidence_score,
                     source = CASE
                       WHEN EXCLUDED.source IN ('CONFIRMED','CHAIRMAN_OVERRIDE')
                       THEN EXCLUDED.source
                       ELSE hs_classification_cache.source
                     END,
                     last_hit_at      = NOW(),
                     hit_count        = hs_classification_cache.hit_count + 1,
                     evidence_hash    = EXCLUDED.evidence_hash""",
                h,
                description[:200],
                best_candidate.get("hs_code"),
                best_candidate.get("hs_code_11"),
                best_candidate.get("hs_description"),
                best_candidate.get("hs_description_th"),
                float(best_candidate.get("confidence_score", 0)),
                source,
                _evidence_hash(data),
            )
    except Exception:
        pass


# ── Save Candidates Log ───────────────────────────────────────────────────────

async def log_candidates(db, session_id: str, session_type: str,
                         description: str, candidates: list) -> list:
    """
    บันทึก candidates ลง classification_candidates_log
    คืน list of log_id
    """
    pool = await _get_pool()
    if not pool:
        return []
    log_ids = []
    try:
        async with pool.acquire() as conn:
            for c in candidates:
                log_id = uuid.uuid4().hex
                data = {
                    "session_id": session_id,
                    "hs_code": c.get("hs_code"),
                    "rank": c.get("rank", 0),
                }
                try:
                    await conn.execute(
                        """INSERT INTO classification_candidates_log
                           (id, session_id, session_type, description, candidate_rank,
                            hs_code, hs_code_11, hs_description, confidence_score,
                            source_reference, was_selected, evidence_hash)
                           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                           ON CONFLICT (id) DO NOTHING""",
                        log_id,
                        session_id,
                        session_type,
                        description[:500],
                        int(c.get("rank", 0)),
                        c.get("hs_code"),
                        c.get("hs_code_11"),
                        c.get("hs_description"),
                        float(c.get("confidence_score", 0)),
                        c.get("source_reference", ""),
                        1 if c.get("rank") == 1 else 0,
                        _evidence_hash(data),
                    )
                    log_ids.append(log_id)
                except Exception:
                    pass
    except Exception:
        pass
    return log_ids


# ── Feedback ──────────────────────────────────────────────────────────────────

async def submit_feedback(db, log_id: str, status: str,
                          amended_hs: Optional[str], feedback_by: str) -> bool:
    """
    รับ feedback จาก client / Chairman
    status: CONFIRMED | REJECTED | AMENDED
    แล้วเขียน queue → process_feedback_queue() จะจัดการต่อ
    """
    if status not in ("CONFIRMED", "REJECTED", "AMENDED"):
        return False
    pool = await _get_pool()
    if not pool:
        return False
    try:
        async with pool.acquire() as conn:
            # ต้องมี log_id จริง
            row = await conn.fetchrow(
                "SELECT id FROM classification_candidates_log WHERE id = $1", log_id
            )
            if not row:
                return False

            await conn.execute(
                """UPDATE classification_candidates_log
                   SET feedback_status  = $1,
                       amended_hs_code  = $2,
                       feedback_by      = $3,
                       feedback_at      = NOW(),
                       learning_triggered = 1
                   WHERE id = $4""",
                status, amended_hs, feedback_by, log_id,
            )
            action = (
                "PROMOTE_TO_CACHE"  if status == "CONFIRMED"
                else "DEMOTE_FROM_CACHE" if status == "REJECTED"
                else "CREATE_LESSON"
            )
            await conn.execute(
                """INSERT INTO cache_feedback_queue (id, candidate_log_id, action)
                   VALUES ($1, $2, $3)""",
                uuid.uuid4().hex, log_id, action,
            )

        # Process immediately (non-blocking on error)
        try:
            await process_feedback_queue()
        except Exception:
            pass

        return True
    except Exception:
        return False


# ── Feedback Queue Processor ──────────────────────────────────────────────────

async def process_feedback_queue(batch: int = 50) -> int:
    """
    ประมวลผล PENDING items ใน cache_feedback_queue
    - PROMOTE_TO_CACHE  → insert/update cache, confidence +0.05 → CONFIRMED
    - DEMOTE_FROM_CACHE → confidence -0.10 (min 0), source → REJECTED (ไม่ลบ)
    - CREATE_LESSON     → upsert cache ด้วย amended_hs_code, source → CONFIRMED
    คืนจำนวน items ที่ประมวลผลสำเร็จ
    """
    pool = await _get_pool()
    if not pool:
        return 0

    processed = 0
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT q.id AS qid, q.action,
                          l.description, l.hs_code, l.hs_code_11,
                          l.hs_description, l.confidence_score,
                          l.amended_hs_code, l.feedback_by
                   FROM cache_feedback_queue q
                   JOIN classification_candidates_log l ON l.id = q.candidate_log_id
                   WHERE q.status = 'PENDING'
                   ORDER BY q.created_at
                   LIMIT $1
                   FOR UPDATE OF q SKIP LOCKED""",
                batch,
            )

            for r in rows:
                try:
                    await _apply_feedback_action(conn, r)
                    await conn.execute(
                        "UPDATE cache_feedback_queue SET status='DONE', processed_at=NOW() WHERE id=$1",
                        r["qid"],
                    )
                    processed += 1
                except Exception as e:
                    await conn.execute(
                        "UPDATE cache_feedback_queue SET status='FAILED', error_msg=$1 WHERE id=$2",
                        str(e)[:200], r["qid"],
                    )
    except Exception:
        pass
    return processed


async def _apply_feedback_action(conn, r):
    """ดำเนินการแต่ละ action บน cache"""
    action      = r["action"]
    description = r["description"] or ""
    h = _desc_hash(description)

    if action == "PROMOTE_TO_CACHE":
        # Boost confidence, mark CONFIRMED
        data = {"cache_key": h, "hs_code": r["hs_code"], "source": "CONFIRMED"}
        await conn.execute(
            """INSERT INTO hs_classification_cache
               (cache_key, description_sample, hs_code, hs_code_11,
                hs_description, confidence_score, source, evidence_hash)
               VALUES ($1,$2,$3,$4,$5,$6,'CONFIRMED',$7)
               ON CONFLICT (cache_key) DO UPDATE SET
                 confidence_score = LEAST(hs_classification_cache.confidence_score + 0.05, 0.98),
                 source           = 'CONFIRMED',
                 last_hit_at      = NOW(),
                 hit_count        = hs_classification_cache.hit_count + 1,
                 evidence_hash    = EXCLUDED.evidence_hash""",
            h,
            description[:200],
            r["hs_code"],
            r["hs_code_11"],
            r["hs_description"],
            min(float(r["confidence_score"] or 0) + 0.05, 0.98),
            _evidence_hash(data),
        )

    elif action == "DEMOTE_FROM_CACHE":
        # ลด confidence แต่ไม่ลบ — ยังคงไว้ใช้เป็น negative signal
        await conn.execute(
            """UPDATE hs_classification_cache
               SET confidence_score = GREATEST(confidence_score - 0.10, 0.0),
                   source           = 'REJECTED',
                   last_hit_at      = NOW()
               WHERE cache_key = $1""",
            h,
        )

    elif action == "CREATE_LESSON":
        # AMENDED → บันทึก hs_code ที่ถูกต้องจาก amended_hs_code
        final_hs = r["amended_hs_code"] or r["hs_code"]
        data = {"cache_key": h, "hs_code": final_hs, "source": "CONFIRMED"}
        await conn.execute(
            """INSERT INTO hs_classification_cache
               (cache_key, description_sample, hs_code, confidence_score,
                source, evidence_hash)
               VALUES ($1,$2,$3, 0.92,'CONFIRMED',$4)
               ON CONFLICT (cache_key) DO UPDATE SET
                 hs_code          = EXCLUDED.hs_code,
                 confidence_score = 0.92,
                 source           = 'CONFIRMED',
                 last_hit_at      = NOW(),
                 evidence_hash    = EXCLUDED.evidence_hash""",
            h,
            description[:200],
            final_hs,
            _evidence_hash(data),
        )


# ── Cache Stats ────────────────────────────────────────────────────────────────

async def cache_stats(db=None) -> dict:
    """สรุปสถานะ cache สำหรับ Chairman dashboard"""
    pool = await _get_pool()
    if not pool:
        return {"total_cached": 0, "confirmed": 0, "pending_feedback_queue": 0, "top_hits": []}
    try:
        async with pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM hs_classification_cache"
            )
            confirmed = await conn.fetchval(
                "SELECT COUNT(*) FROM hs_classification_cache WHERE source='CONFIRMED'"
            )
            pending_q = await conn.fetchval(
                "SELECT COUNT(*) FROM cache_feedback_queue WHERE status='PENDING'"
            )
            top_hits = await conn.fetch(
                """SELECT hs_code, description_sample, hit_count, source
                   FROM hs_classification_cache
                   ORDER BY hit_count DESC LIMIT 10"""
            )
            return {
                "total_cached":          int(total or 0),
                "confirmed":             int(confirmed or 0),
                "pending_feedback_queue": int(pending_q or 0),
                "top_hits": [dict(r) for r in top_hits],
            }
    except Exception as e:
        return {"total_cached": 0, "confirmed": 0, "pending_feedback_queue": 0,
                "top_hits": [], "error": str(e)}
