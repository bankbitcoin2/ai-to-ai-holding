"""
apply_schema.py — Apply schema_learning_v2_pg.sql to Railway PostgreSQL
Usage: set DATABASE_URL env var then run: python apply_schema.py
"""
import os, sys

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    DATABASE_URL = input("Paste DATABASE_URL from Railway: ").strip()

SQL_FILE = os.path.join(os.path.dirname(__file__), "schema_learning_v2_pg.sql")

try:
    import psycopg2
except ImportError:
    print("Installing psycopg2-binary...")
    os.system(f"{sys.executable} -m pip install psycopg2-binary -q")
    import psycopg2

with open(SQL_FILE, "r", encoding="utf-8") as f:
    sql = f.read()

print(f"Connecting to Railway PostgreSQL...")
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cur = conn.cursor()

# split by semicolon, skip comments
statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]
ok = 0
for stmt in statements:
    if not stmt:
        continue
    try:
        cur.execute(stmt)
        print(f"  ✅ {stmt[:60].splitlines()[0]}...")
        ok += 1
    except Exception as e:
        print(f"  ⚠️  {stmt[:60].splitlines()[0]}...\n     → {e}")

cur.close()
conn.close()
print(f"\nDone — {ok}/{len(statements)} statements applied.")
