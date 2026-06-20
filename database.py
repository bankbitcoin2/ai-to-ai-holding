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
    """รัน schema files ทั้งหมดตอน startup — execute ทีละ statement"""
    schema_files = [
        "schema_v1.sql",
        "schema_comms_v1.sql",
        "schema_learning_v1.sql",
        "schema_registry_v1.sql",
        "schema_billing_v1.sql",
    ]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        for fname in schema_files:
            fpath = SCHEMA_DIR / fname
            if not fpath.exists():
                continue
            sql = fpath.read_text(encoding="utf-8")
            # แยก statements ทีละบรรทัด ข้าม comments และ empty lines
            statements = []
            current = []
            for line in sql.splitlines():
                stripped = line.strip()
                if stripped.startswith("--") or not stripped:
                    continue
                current.append(line)
                if stripped.endswith(";"):
                    statements.append("\n".join(current))
                    current = []
            for stmt in statements:
                stmt = stmt.strip()
                if not stmt:
                    continue
                try:
                    await db.execute(stmt)
                except Exception as e:
                    # ข้าม error ที่ไม่ร้ายแรง เช่น column/table มีอยู่แล้ว
                    msg = str(e).lower()
                    if any(x in msg for x in ["already exists", "duplicate column"]):
                        pass
                    else:
                        print(f"[DB WARN] {fname}: {e} | stmt: {stmt[:60]}")
        await db.commit()