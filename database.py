"""
core/database.py
Single SQLite connection manager — P-06: หนึ่ง DB ไฟล์เดียวทั้งองค์กร
"""
import aiosqlite
import os
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "holding.db")
SCHEMA_DIR = Path(__file__).parent


async def get_db() -> aiosqlite.Connection:
    """FastAPI dependency — คืน connection ต่อ request"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        yield db


async def init_db():
    """รัน schema files ทั้งหมดตอน startup"""
    schema_files = [
        "schema_v1.sql",
        "schema_comms_v1.sql",
        "schema_learning_v1.sql",
    ]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        for fname in schema_files:
            fpath = SCHEMA_DIR / fname
            if fpath.exists():
                sql = fpath.read_text(encoding="utf-8")
                sql = sql.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ")
                sql = sql.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ")
                sql = sql.replace("CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX IF NOT EXISTS ")
                sql = sql.replace("INSERT INTO ", "INSERT OR IGNORE INTO ")
                await db.executescript(sql)
        await db.commit()