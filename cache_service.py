"""
cache_service.py — HS Classification Cache
ลด Claude API cost โดย cache ผล classify ไว้ใน PostgreSQL/SQLite

Cache key = SHA256(normalized_description + "|" + origin_country)
Cache hit  = คืนผลทันที ไม่เรียก Claude = $0 ต้นทุน
Cache miss = เรียก Claude → เก็บผล → คืนผล
"""
import hashlib
import os
from typing import Optional

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
USE_POSTGRES = bool(DATABASE_URL)


def _make_key(description: str, origin_country: Optional[str]) -> str:
    """Normalize + hash เพื่อทำ cache key"""
    norm = description.lower().strip()
    origin = (origin_country or "").upper().strip()
    raw = f"{norm}|{origin}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def cache_get(description: str, origin_country: Optional[str]) -> Optional[dict]:
    """ดึง cache — คืน dict หรือ None ถ้า miss"""
    key = _make_key(description, origin_country)
    try:
        if USE_POSTGRES:
            from db_adapter import get_pool
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT hs_code, hs_description, confidence_score,
                              source_reference, notes, model_used, hit_count
                       FROM hs_classification_cache WHERE cache_key = $1""",
                    key,
                )
                if row:
                    # อัป hit_count + last_hit_at
                    await conn.execute(
                        """UPDATE hs_classification_cache
                           SET hit_count = hit_count + 1, last_hit_at = NOW()
                           WHERE cache_key = $1""",
                        key,
                    )
                    return dict(row)
        else:
            import aiosqlite
            from database import DB_PATH
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """SELECT hs_code, hs_description, confidence_score,
                              source_reference, notes, model_used, hit_count
                       FROM hs_classification_cache WHERE cache_key = ?""",
                    (key,),
                ) as cur:
                    row = await cur.fetchone()
                    if row:
                        await db.execute(
                            """UPDATE hs_classification_cache
                               SET hit_count = hit_count + 1,
                                   last_hit_at = datetime('now')
                               WHERE cache_key = ?""",
                            (key,),
                        )
                        await db.commit()
                        return dict(row)
    except Exception as e:
        print(f"[CACHE] get error (non-fatal): {e}")
    return None


async def cache_set(
    description: str,
    origin_country: Optional[str],
    hs_code: Optional[str],
    hs_description: Optional[str],
    confidence_score: float,
    source_reference: str,
    notes: Optional[str],
    model_used: str = "mock",
) -> None:
    """เก็บผล classify ลง cache"""
    key = _make_key(description, origin_country)
    try:
        if USE_POSTGRES:
            from db_adapter import get_pool
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO hs_classification_cache
                       (cache_key, description, origin_country, hs_code, hs_description,
                        confidence_score, source_reference, notes, model_used)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                       ON CONFLICT (cache_key) DO NOTHING""",
                    key, description, origin_country, hs_code, hs_description,
                    confidence_score, source_reference, notes, model_used,
                )
        else:
            import aiosqlite
            from database import DB_PATH
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    """INSERT OR IGNORE INTO hs_classification_cache
                       (cache_key, description, origin_country, hs_code, hs_description,
                        confidence_score, source_reference, notes, model_used)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (key, description, origin_country, hs_code, hs_description,
                     confidence_score, source_reference, notes, model_used),
                )
                await db.commit()
    except Exception as e:
        print(f"[CACHE] set error (non-fatal): {e}")


async def cache_stats() -> dict:
    """สถิติ cache — ใช้ใน Chairman dashboard"""
    try:
        if USE_POSTGRES:
            from db_adapter import get_pool
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT COUNT(*) as total_entries,
                              COALESCE(SUM(hit_count), 0) as total_hits,
                              COALESCE(SUM(hit_count) - COUNT(*), 0) as cache_saves
                       FROM hs_classification_cache"""
                )
                return dict(row) if row else {}
        else:
            import aiosqlite
            from database import DB_PATH
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """SELECT COUNT(*) as total_entries,
                              COALESCE(SUM(hit_count), 0) as total_hits,
                              COALESCE(SUM(hit_count) - COUNT(*), 0) as cache_saves
                       FROM hs_classification_cache"""
                ) as cur:
                    row = await cur.fetchone()
                    return dict(row) if row else {}
    except Exception as e:
        print(f"[CACHE] stats error: {e}")
        return {"total_entries": 0, "total_hits": 0, "cache_saves": 0}
