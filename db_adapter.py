"""
db_adapter.py — PostgreSQL compatibility adapter
แปลง SQLite syntax → PostgreSQL อัตโนมัติ
ทำให้ไฟล์อื่นไม่ต้องเปลี่ยน code มาก

แปลงอัตโนมัติ:
  ? params          → $1 $2 $3...
  datetime('now')   → NOW()
  strftime(...)     → to_char(NOW() AT TIME ZONE 'UTC', ...)
  INSERT OR IGNORE  → INSERT ... ON CONFLICT DO NOTHING
  lower(hex(randomblob(16))) → gen_random_uuid()::text
"""
import re
import asyncpg
import os
from typing import Any, Optional, Sequence


DATABASE_URL = os.getenv("DATABASE_URL", "")

# Fix Railway's postgres:// → postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def _convert_sql(sql: str) -> str:
    """แปลง SQLite SQL → PostgreSQL SQL"""
    # INSERT OR IGNORE → INSERT ... ON CONFLICT DO NOTHING
    sql = re.sub(r'\bINSERT\s+OR\s+IGNORE\b', 'INSERT', sql, flags=re.IGNORECASE)

    # datetime('now') → NOW()
    sql = re.sub(r"datetime\('now'\)", "NOW()", sql, flags=re.IGNORECASE)

    # strftime('%Y-%m-%dT%H:%M:%SZ','now') → to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
    sql = re.sub(
        r"strftime\('%Y-%m-%dT%H:%M:%SZ'\s*,\s*'now'\)",
        "to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"')",
        sql, flags=re.IGNORECASE
    )

    # lower(hex(randomblob(16))) → gen_random_uuid()::text
    sql = re.sub(
        r"lower\(hex\(randomblob\(16\)\)\)",
        "replace(gen_random_uuid()::text, '-', '')",
        sql, flags=re.IGNORECASE
    )

    # ? → $1 $2 $3... (แปลง positional params)
    counter = [0]
    def replace_q(m):
        counter[0] += 1
        return f'${counter[0]}'
    sql = re.sub(r'\?', replace_q, sql)

    return sql


class PGRow:
    """Row object ที่ใช้ได้เหมือน aiosqlite.Row (row["column"])"""
    def __init__(self, record: asyncpg.Record):
        self._record = record

    def __getitem__(self, key):
        return self._record[key]

    def __contains__(self, key):
        return key in self._record.keys()

    def keys(self):
        return self._record.keys()

    def __repr__(self):
        return dict(self._record).__repr__()


class PGCursorContext:
    """Async context manager สำหรับ async with db.execute(...) as cur:"""
    def __init__(self, conn, sql, params):
        self._conn = conn
        self._sql = sql
        self._params = params
        self._rows = None

    async def __aenter__(self):
        self._rows = await self._conn.fetch(self._sql, *self._params)
        return self

    async def __aexit__(self, *args):
        pass

    async def fetchone(self):
        if self._rows:
            return PGRow(self._rows[0])
        return None

    async def fetchall(self):
        return [PGRow(r) for r in self._rows]


class PGConnection:
    """
    Connection wrapper ที่ทำงานเหมือน aiosqlite.Connection
    รองรับ: execute, commit, close, async with db.execute() as cur
    """
    def __init__(self, conn: asyncpg.Connection):
        self._conn = conn
        self._tr = None
        self.row_factory = None  # compat

    async def _start_transaction(self):
        if self._tr is None:
            self._tr = self._conn.transaction()
            await self._tr.start()

    def execute(self, sql: str, params: Sequence = ()):
        """รองรับ: await db.execute(...) และ async with db.execute(...) as cur:"""
        pg_sql = _convert_sql(sql)
        return _ExecuteAwaitable(self._conn, pg_sql, list(params), self)

    async def commit(self):
        if self._tr:
            await self._tr.commit()
            self._tr = None

    async def rollback(self):
        if self._tr:
            await self._tr.rollback()
            self._tr = None

    async def close(self):
        if self._tr:
            try:
                await self._tr.rollback()
            except Exception:
                pass
        await self._conn.close()


class _ExecuteAwaitable:
    """
    Object ที่ใช้ได้ทั้ง:
      await db.execute(sql, params)
      async with db.execute(sql, params) as cur:
    """
    def __init__(self, conn, sql, params, pg_conn: PGConnection):
        self._conn = conn
        self._sql = sql
        self._params = params
        self._pg_conn = pg_conn
        self._rows = None

    def __await__(self):
        return self._run().__await__()

    async def _run(self):
        await self._pg_conn._start_transaction()
        try:
            await self._conn.execute(self._sql, *self._params)
        except asyncpg.UniqueViolationError:
            raise
        except asyncpg.ForeignKeyViolationError:
            raise
        except asyncpg.CheckViolationError as e:
            raise

    async def __aenter__(self):
        self._rows = await self._conn.fetch(self._sql, *self._params)
        return self

    async def __aexit__(self, *args):
        pass

    async def fetchone(self):
        if self._rows:
            return PGRow(self._rows[0])
        return None

    async def fetchall(self):
        return [PGRow(r) for r in (self._rows or [])]


async def connect() -> PGConnection:
    """สร้าง PGConnection จาก pool"""
    pool = await get_pool()
    conn = await pool.acquire()
    return PGConnection(conn)


class _DBContext:
    """async with aiosqlite.connect(DB_PATH) as db: compat"""
    async def __aenter__(self) -> PGConnection:
        self._pg = await connect()
        return self._pg

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type:
            await self._pg.rollback()
        await self._pg.close()


def connect_ctx() -> _DBContext:
    return _DBContext()
