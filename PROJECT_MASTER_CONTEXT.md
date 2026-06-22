# PROJECT MASTER CONTEXT — AI TO AI HOLDING
> ถอดแม่แบบโปรเจคทั้งหมด | สกัดจากงานจริง 68 Tasks | อัปเดต: มิถุนายน 2026

---

## 1. สิ่งที่เราสร้าง

**AI TO AI HOLDING** คือ AI-Native Corporation — ไม่ใช่ SaaS, ไม่ใช่ chatbot, ไม่ใช่ automation script

องค์กรดิจิทัลที่มีโครงสร้างบริหาร, ระบบการเงิน, knowledge management, audit trail และ revenue generation เหมือนบริษัทจริง — โดย AI คือแรงงาน, Chairman คือมนุษย์ผู้ควบคุมสูงสุด

**Revenue Division แรก:** Customs Intelligence Division — HS Code classification, duty estimation, OGA screening, halal/FTA compliance

---

## 2. สถานะ Production (ณ มิถุนายน 2026)

| Component | สถานะ |
|-----------|-------|
| Platform | Railway.app |
| Database | PostgreSQL (asyncpg pool) |
| URL | web-production-c9da4.up.railway.app |
| HS Code Master | 12,247 rows |
| FTA Eligibility | 202,438 rows |
| Commit ล่าสุด | 77cf44f |
| API Price | $0.50 / query |

---

## 3. Architecture Stack (Production)

```
FastAPI + Uvicorn
    └── asyncpg → PostgreSQL (Railway)
    └── Middleware: KillSwitch → Security → CORS
    └── Routers: sandbox, customs, billing, chairman, agents, kill_switch, treasury_wallet
    └── Engines (bundled, no external file):
        ├── halal_engine.py       — halal countries + cert requirements
        ├── oga_engine.py         — OGA controlled goods rules
        ├── tax_engine_bundled.py — duty rates 4/6-digit + FTA
        ├── fta_eligibility_bundled.py — FTA country eligibility
        └── hs_descriptions_bundled.py — HS code descriptions
    └── Knowledge Layer:
        ├── normalize_description.py  — TH+ZH+JA→EN (485 lines, 199 rules)
        ├── cache_key_utils.py        — single source: sha256(normalize(desc))
        ├── cache_classification.py   — asyncpg cache lookup/save/feedback
        └── knowledge_service.py      — DB-first → bundled fallback
```

---

## 4. Constitutional Principles (ห้ามแก้ไข)

| Code | หลักการ |
|------|---------|
| P-01 | Chairman Supremacy — มนุษย์เป็น authority สูงสุด AI ไม่มีสิทธิ์ override |
| P-02 | Kill Switch Always On — Chairman หยุดระบบได้ทันที ไม่มี delay |
| P-03 | Revenue Split — 60% Corporate Reserve / 40% CHAIRMAN_PRIVATE_WALLET (AI ไม่มี access) |
| P-04 | Cryptographic Auditability — ทุก decision ต้องถูก log ด้วย hash |
| P-05 | No Hallucination — ทุก output ต้องมี source จริง + Confidence Score |
| P-06 | Unified Knowledge Base — ไม่มี data silo ระหว่าง Offices |

**Security Rules (ห้ามทำ):**
- ห้าม hardcode API key — Railway Variables เท่านั้น
- ห้ามแก้ไข/ลบ audit log / evidence chain
- Blockchain/On-chain — ตัดออกถาวร
- CHAIRMAN_PRIVATE_WALLET — No AI read/write/approve
- ห้ามสร้าง Database แยกสำหรับ module ใดๆ
- Production ใช้ PostgreSQL เท่านั้น ห้าม SQLite

---

## 5. งานทั้งหมดที่เสร็จแล้ว (68 Tasks)

### Phase 1 — Foundation & PostgreSQL Migration
- แก้ db_adapter.py: INSERT OR IGNORE → ON CONFLICT DO NOTHING
- แก้ middleware order: KillSwitch เป็น outermost
- แก้ audit.py + treasury_service.py: asyncpg compatible
- แก้ billing.py: Stripe webhook + idempotency
- แก้ chairman_router.py: auth + connection cleanup
- แก้ knowledge_service.py: ลบ hardcode path E:\ส่วนตัว2
- เพิ่ม audit trail สำหรับ financial transactions
- เพิ่ม /v1/chairman/topups endpoint

### Phase 2 — Engines (Bundled, No External Files)
- `oga_engine.py` — OGA controlled goods rules (bundled)
- `tax_engine_bundled.py` — duty rates 4/6-digit + FTA
- `halal_engine.py` — halal countries + cert requirements
- `normalize_description.py` — TH+ZH+JA rules (485 lines)
- Wire ทั้งหมดเข้า knowledge_service.py + sandbox.py

### Phase 3 — API & UI
- GET /v1/halal-countries
- POST /v1/recover-key
- GET/POST /v1/agents/status, /config
- FTA lookup: multi-length 10→9→8→7→6
- HS Description: prefix 8→6→4
- dashboard.html: halal + FTA saving + OGA risk
- index.html: destination_country + sandbox form

### Phase 4 — Learning & Cache
- cache_feedback_queue table
- PROMOTE_TO_CACHE / DEMOTE_FROM_CACHE / CREATE_LESSON actions
- cache_key_utils.py: single source of truth
- Cross-language cache: ZH/JA/TH → normalize → sha256 เดียวกัน
- schema_learning_v2_pg.sql: classification_candidates_log + cache_feedback_queue
- _migrate_cache_schema(): auto-run ทุก startup

### Phase 5 — Market Discovery
- MCP Registry submission package
- GPT Actions manifest
- RapidAPI listing
- LangChain Hub tool wrapper

---

## 6. ไฟล์สำคัญและหน้าที่

| ไฟล์ | หน้าที่ |
|------|---------|
| `main.py` | FastAPI app, lifespan, middleware, router wiring |
| `database.py` | init_db, schema files list |
| `db_adapter.py` | asyncpg pool, SQL dialect conversion |
| `sandbox.py` | Public classification endpoint |
| `customs.py` + `customs_service.py` | Core classification logic |
| `cache_key_utils.py` | make_cache_key() — single source |
| `cache_classification.py` | asyncpg cache CRUD + learning loop |
| `cache_service.py` | Cache wrapper (delegates to cache_key_utils) |
| `knowledge_service.py` | DB-first lookup → bundled fallback |
| `normalize_description.py` | TH+ZH+JA → EN normalization |
| `halal_engine.py` | Halal countries + cert rules |
| `oga_engine.py` | OGA controlled goods |
| `tax_engine_bundled.py` | Duty rates + FTA |
| `agents_router.py` | /v1/agents/status + /config |
| `billing.py` | Stripe webhook + credit accounting |
| `audit.py` | Evidence chain + cryptographic logging |
| `treasury_service.py` | Revenue split 60/40 |
| `kill_switch_engine.py` | Kill switch state |
| `security.py` | API Key auth + rate limiting + Chairman IP |

---

## 7. Pattern การแก้ Bug ที่พบบ่อย

### asyncpg pattern
```python
pool = await get_pool()
async with pool.acquire() as conn:
    await conn.execute(sql)
    rows = await conn.fetch(sql, param1, param2)
```

### Schema migration pattern (safe)
```python
"ALTER TABLE t ADD COLUMN IF NOT EXISTS col TEXT"
"CREATE INDEX IF NOT EXISTS idx_name ON t(col)"
```

### Cache key (single source)
```python
from cache_key_utils import make_cache_key
key = make_cache_key(description)  # sha256(normalize(desc))
```

### normalize cross-language
```python
# ยางรถยนต์ → car tyre
# 轮胎 → car tyre
# タイヤ → car tyre
# → sha256 เดียวกัน → cache hit เดียวกัน
```

---

## 8. Warning ที่ยังมี (non-fatal)

| Warning | สาเหตุ | ผลกระทบ |
|---------|--------|---------|
| `cannot import name 'USE_POSTGRES' from 'db_adapter'` | _fix_audit_fk + _migrate_cache_schema import ชื่อที่ไม่ export | migration skip — ไม่ crash |
| `column "description_hash" does not exist` | schema_learning_v2_pg.sql reference column เก่า | index skip — ไม่ crash |

**Fix ที่ยังค้างอยู่:**
```python
# เปลี่ยนใน _fix_audit_fk และ _migrate_cache_schema
from db_adapter import get_pool
USE_POSTGRES = True  # Railway always PostgreSQL
```

---

## 9. งานที่เลื่อนไว้ (Deferred)

| งาน | เหตุผล |
|-----|--------|
| CEO Real Mode (`_real_process()`) | Chairman ยังไม่สั่ง |
| command_queue / comms endpoints | รอ CEO mode |
| Kill Switch push | Chairman ยังไม่พร้อม |

---

## 10. Org Structure (ปัจจุบัน)

```
[Chairman — Human — Supreme Authority]
                │
            [AI CEO]  ← _real_process() ยัง NotImplementedError
                │
    ┌───────────┴───────────┐
[Offices]              [Divisions]
├─ Knowledge Office     └─ Customs Intelligence ✅ Live
├─ Audit Office
├─ Treasury Office
└─ Kill Switch
```

---

*อัปเดตครั้งล่าสุด: มิถุนายน 2026 | งานเสร็จ 68 tasks | Production: Online ✅*
