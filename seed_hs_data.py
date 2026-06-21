"""
seed_hs_data.py — One-time seeder: load HS descriptions + FTA eligibility into PostgreSQL
รัน: python seed_hs_data.py (ต้องมี DATABASE_URL ใน env หรือ .env)
Railway: Settings → Deploy → Run Command → python seed_hs_data.py
"""
import asyncio, os, sys, time
from pathlib import Path

# Load .env ถ้ามี
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    print("❌ DATABASE_URL not set"); sys.exit(1)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Add repo to path เพื่อ import bundled modules
sys.path.insert(0, str(Path(__file__).parent))

async def seed():
    import asyncpg

    print("Connecting to PostgreSQL...")
    conn = await asyncpg.connect(DATABASE_URL)

    # ── Apply schema ────────────────────────────────────────────────────
    schema = open(Path(__file__).parent / "schema_hs_master.sql").read()
    await conn.execute(schema)
    print("✅ Schema applied")

    # ── Seed hs_code_master ─────────────────────────────────────────────
    print("Loading hs_descriptions_bundled...")
    import hs_descriptions_bundled as _desc
    db = _desc._load()
    records = [(k.strip(), v["th"], v["en"]) for k, v in db.items()]
    print(f"  {len(records):,} records to insert...")

    t0 = time.time()
    await conn.executemany("""
        INSERT INTO hs_code_master (hs_code, desc_th, desc_en)
        VALUES ($1, $2, $3)
        ON CONFLICT (hs_code) DO UPDATE
            SET desc_th = EXCLUDED.desc_th,
                desc_en = EXCLUDED.desc_en,
                source  = 'AHTN2022'
    """, records)
    print(f"  ✅ hs_code_master: {len(records):,} rows ({time.time()-t0:.1f}s)")

    # ── Seed fta_eligibility ────────────────────────────────────────────
    print("Loading fta_eligibility_bundled...")
    import fta_eligibility_bundled as _fta
    fta_db = _fta._load()

    fta_records = []
    for cc, hs_map in fta_db.items():
        for hs, form in hs_map.items():
            fta_records.append((hs.strip(), cc, form))

    print(f"  {len(fta_records):,} records to insert...")
    t0 = time.time()

    # Batch insert (1000 at a time)
    batch = 1000
    for i in range(0, len(fta_records), batch):
        chunk = fta_records[i:i+batch]
        await conn.executemany("""
            INSERT INTO fta_eligibility (hs_code, country_code, fta_form)
            VALUES ($1, $2, $3)
            ON CONFLICT (hs_code, country_code) DO UPDATE
                SET fta_form = EXCLUDED.fta_form,
                    source   = 'ThaiCustoms2022'
        """, chunk)
        if (i // batch) % 20 == 0:
            print(f"  ... {i+len(chunk):,}/{len(fta_records):,}")

    print(f"  ✅ fta_eligibility: {len(fta_records):,} rows ({time.time()-t0:.1f}s)")

    # ── Verify ─────────────────────────────────────────────────────────
    hs_count  = await conn.fetchval("SELECT COUNT(*) FROM hs_code_master")
    fta_count = await conn.fetchval("SELECT COUNT(*) FROM fta_eligibility")
    sample    = await conn.fetchrow("SELECT * FROM hs_code_master WHERE hs_code LIKE '8517%' LIMIT 1")
    fta_sample = await conn.fetchrow(
        "SELECT * FROM fta_eligibility WHERE country_code='AU' LIMIT 1")

    print(f"\n✅ Done!")
    print(f"   hs_code_master : {hs_count:,} rows")
    print(f"   fta_eligibility: {fta_count:,} rows")
    print(f"   Sample HS 8517x: {dict(sample) if sample else 'not found'}")
    print(f"   Sample FTA AU  : {dict(fta_sample) if fta_sample else 'not found'}")

    await conn.close()

asyncio.run(seed())
