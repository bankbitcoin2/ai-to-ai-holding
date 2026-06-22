"""
cache_service.py — HS Classification Cache
schema: hs_classification_cache ใช้ cache_key (SHA256), description, origin_country
"""
import hashlib
import os
from typing import Optional

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
USE_POSTGRES = bool(DATABASE_URL)


def _make_key(description: str, origin_country: Optional[str]) -> str:
    try:
        from normalize_description import normalize
        norm = normalize(description)
    except Exception:
        norm = description.lower().strip()
    origin = (origin_country or "").upper().strip()
    return hashlib.sha256(f"{norm}|{origin}".encode("utf-8")).hexdigest()


async def cache_get(description: str, origin_country: Optional[str]) -> Optional[dict]:
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
                    "SELECT hs_code, hs_description, confidence_score, "
                    "source_reference, notes, model_used, hit_count "
                    "FROM hs_classification_cache WHERE cache_key = ?",
                    (key,),
                ) as cur:
                    row = await cur.fetchone()
                    if row:
                        await db.execute(
                            "UPDATE hs_classification_cache "
                            "SET hit_count = hit_count + 1, last_hit_at = datetime('now') "
                            "WHERE cache_key = ?", (key,))
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
    source_reference: str = "CLAUDE",
    notes: Optional[str] = None,
    model_used: str = "mock",
    hs_description_th: Optional[str] = None,
) -> None:
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
                    "INSERT OR IGNORE INTO hs_classification_cache "
                    "(cache_key, description, origin_country, hs_code, hs_description, "
                    "confidence_score, source_reference, notes, model_used) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (key, description, origin_country, hs_code, hs_description,
                     confidence_score, source_reference, notes, model_used),
                )
                await db.commit()
    except Exception as e:
        print(f"[CACHE] set error (non-fatal): {e}")


async def cache_stats() -> dict:
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
                return dict(row) if row else {"total_entries": 0, "total_hits": 0, "cache_saves": 0}
        else:
            import aiosqlite
            from database import DB_PATH
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT COUNT(*) as total_entries, "
                    "COALESCE(SUM(hit_count),0) as total_hits, "
                    "COALESCE(SUM(hit_count)-COUNT(*),0) as cache_saves "
                    "FROM hs_classification_cache"
                ) as cur:
                    row = await cur.fetchone()
                    return dict(row) if row else {}
    except Exception as e:
        print(f"[CACHE] stats error: {e}")
        return {"total_entries": 0, "total_hits": 0, "cache_saves": 0}
