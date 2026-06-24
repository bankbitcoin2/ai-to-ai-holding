"""
database.py — Database manager
รองรับ PostgreSQL (production) และ SQLite (dev fallback)
"""
import os
import re
import aiosqlite
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

DB_PATH = os.getenv("DB_PATH", "holding.db")
SCHEMA_DIR = Path(__file__).parent
USE_POSTGRES = bool(DATABASE_URL)


async def get_db():
    """FastAPI dependency (legacy — billing.py ใช้ _get_db() โดยตรง)"""
    if USE_POSTGRES:
        from db_adapter import connect
        db = await connect()
        try:
            yield db
        finally:
            await db.close()
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys = ON")
            yield db


async def init_db():
    if USE_POSTGRES:
        await _init_postgres()
    else:
        await _init_sqlite()


def _sqlite_to_postgres(sql: str) -> str:
    sql = re.sub(r'PRAGMA\s+\w+\s*=\s*\w+\s*;?', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r"datetime\('now'\)", "NOW()", sql, flags=re.IGNORECASE)
    sql = re.sub(r"strftime\('[^']+'\s*,\s*'now'\)", "NOW()", sql, flags=re.IGNORECASE)
    sql = re.sub(r"lower\(hex\(randomblob\(16\)\)\)",
                 "replace(gen_random_uuid()::text, '-', '')", sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bINSERT\s+OR\s+IGNORE\b', 'INSERT', sql, flags=re.IGNORECASE)
    return sql


def _split_statements(sql: str) -> list:
    stmts, current, depth = [], [], 0
    for line in sql.splitlines():
        s = line.strip()
        if s.startswith("--") or not s:
            continue
        current.append(line)
        if s.endswith(";"):
            stmts.append("\n".join(current))
            current = []
    return stmts


async def _init_postgres():
    import asyncpg
    from db_adapter import get_pool
    pool = await get_pool()
    schema_files = [
        "schema_v1.sql", "schema_comms_v1.sql", "schema_learning_v1.sql",
        "schema_registry_v1.sql", "schema_billing_v1.sql", "schema_learning_v2_pg.sql",
        "schema_invoice.sql",
    ]
    async with pool.acquire() as conn:
        # enable uuid extension
        try:
            await conn.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
        except Exception:
            pass
        for fname in schema_files:
            fpath = SCHEMA_DIR / fname
            if not fpath.exists():
                continue
            sql = _sqlite_to_postgres(fpath.read_text(encoding="utf-8"))
            for stmt in _split_statements(sql):
                stmt = stmt.strip()
                if not stmt:
                    continue
                try:
                    await conn.execute(stmt)
                except Exception as e:
                    msg = str(e).lower()
                    if any(x in msg for x in ["already exists", "duplicate", "unique"]):
                        pass
                    else:
                        print(f"[DB WARN] {fname}: {e} | {stmt[:80]}")
    print("[DB] PostgreSQL initialized")


async def _init_sqlite():
    schema_files = [
        "schema_v1.sql", "schema_comms_v1.sql", "schema_learning_v1.sql",
        "schema_registry_v1.sql", "schema_billing_v1.sql", "schema_learning_v2.sql",
    ]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        for fname in schema_files:
            fpath = SCHEMA_DIR / fname
            if not fpath.exists():
                continue
            sql = fpath.read_text(encoding="utf-8")
            for stmt in _split_statements(sql):
                stmt = stmt.strip()
                if not stmt:
                    continue
                try:
                    await db.execute(stmt)
                except Exception as e:
                    msg = str(e).lower()
                    if any(x in msg for x in ["already exists", "duplicate column"]):
                        pass
                    else:
                        print(f"[DB WARN] {fname}: {e} | {stmt[:80]}")
        await db.commit()
    print("[DB] SQLite initialized")