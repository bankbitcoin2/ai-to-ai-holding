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

---

## 11. Roadmap เต็ม (14 Phases)

| Phase | ชื่อ | สถานะ |
|-------|------|-------|
| 1 | Foundation — PostgreSQL + Railway | ✅ Done |
| 2 | Engines — Halal/OGA/Tax/FTA/Normalize | ✅ Done |
| 3 | API & UI — Sandbox/Dashboard/Chairman | ✅ Done |
| 4 | Learning Cache — Feedback loop + 202k FTA | ✅ Done |
| 5 | Market Discovery — MCP/GPT/RapidAPI/LangChain | ✅ Submitted |
| 6 | CEO Real Mode (AXIS) | ⏸️ Deferred |
| 7 | Revenue Scale — Stripe live + multi-tenant | 📋 Planned |
| 8 | Invoice Intelligence Pipeline | 📋 Planned |
| 8.1 | Invoice Upload Channel (รูปภาพ/PDF/Excel) | 📋 Planned |
| 9 | Freight Intelligence & Logistics Expansion | 📋 Planned |
| 10 | Customs Software Integration (Pre-flight Check) | 📋 Planned |
| 11 | Explainable AI (XAI) Reasoning Block | 📋 Planned |
| 12 | Valuation Risk Alert (Price Benchmark) | 📋 Planned |
| 13 | Dynamic OGA Update Pipeline | 📋 Planned |
| 14 | Dual-Track Pricing & Revenue Structure | 📋 Planned |

---

## 12. Strategic Position — Intelligence Layer

```
ระบบเราไม่ได้แข่งกับ VAN/Customs Software/FF
เราเป็น Intelligence API ที่ทุกคนในห่วงโซ่ต้อง call มา

[กรมศุลกากร / NSW]
        ↑
[VAN: Netbay / TradeSiam]
        ↑
[Customs Software: e-Customs Pro ฯลฯ]
        ↑
[Freight Forwarder] ← [Importer โดยตรง]
        ↑
════════════════════════
│   AI TO AI HOLDING   │  ← เราอยู่ตรงนี้
│   Intelligence API   │
│ HS + FTA + OGA + XAI │
│ Valuation + Halal    │
════════════════════════
        ↑
[Invoice Data + Feedback Loop + Trade Intelligence]
```

---

## 13. ช่องว่างตลาดที่ระบบเราอุด (Gap Analysis)

**Gap 1 — Legal Accountability**
ชิปปิ้งกลัวใช้ AI เพราะถ้า HS ผิดโดนปรับ ใครรับผิดชอบ
→ แก้ด้วย XAI Reasoning Block (Phase 11) — ส่ง evidence พร้อมผลลัพธ์

**Gap 2 — Customs Valuation**
ไม่มีใครรู้ราคากลางสินค้าจริง → under-valuation → Red Line
→ แก้ด้วย Price Benchmark (Phase 12) — สะสมจาก invoice จริง

**Gap 3 — Dynamic Non-Tariff Barriers**
กฎ OGA เปลี่ยนรายสัปดาห์ — rule-based system พัง
→ แก้ด้วย Dynamic OGA Pipeline (Phase 13) — auto-fetch จาก DLD/FDA

---

## 14. ข้อมูลที่เก็บได้จาก 1 Invoice

```
ทันที:
→ HS verify + FTA + OGA + Halal ครบ
→ บันทึก description เข้า normalize cache
→ บันทึก price data point

สะสม 100 ใบ   → เห็น price range ต่อ HS code
สะสม 1,000 ใบ → เห็น trade flow, เริ่ม flag under-valuation
สะสม 10,000 ใบ → price benchmark real-time, seasonal pattern
สะสม 100,000 ใบ → ข้อมูลระดับกรมศุลกากร
```

**Fields ที่สกัดจาก Invoice:**
- Description → normalize cache + XAI training
- HS Code (ที่ลูกค้าใส่มา) → verify vs AI → learning signal
- Unit Price → price benchmark
- Country of Origin → FTA + Halal zone mapping
- Incoterms → CIF calculation base
- Transport mode/Shipping line → freight intelligence
- Port of loading/discharge → trade route analytics

---

## 15. Revenue Model (Dual-Track + Data)

```
Track A — Volume API (VAN / Customs Software)
$0.003-0.015 per call | volume discount
Target: Netbay, TradeSiam, e-Customs Pro

Track B — Enterprise SaaS (FF / Importer ใหญ่)
$200-500/เดือน | XAI + Valuation Alert + Priority
Target: FF รายใหญ่ 10 ราย = $2,000-5,000/เดือน

Track C — Trade Intelligence Reports (ระยะยาว)
Anonymized trade flow รายไตรมาส
ขายให้ธนาคาร/ประกัน/นักลงทุน/BOI
High-margin passive income
```

**PoC Strategy:** API ฟรี 3 เดือน แลก anonymous invoice data
→ Flywheel: data มาก → AI แม่น → ลูกค้ามาก → data มากขึ้น

---

## 16. Economic Moat — สิ่งที่คู่แข่งต่างชาติทำไม่ได้

```
✅ OGA rules เฉพาะไทย (DLD, FDA, TISI, กรมอุตฯทหาร)
✅ Halal zone 21 พื้นที่ในอาเซียน
✅ FTA ไทย-อาเซียนระดับ 11-digit
✅ Invoice data จากตลาดไทยจริง (สะสมเรื่อยๆ)
✅ ภาษาไทย/context ท้องถิ่น
✅ Feedback loop จากการใช้งานจริง
```

Amazon/Google มี AI เก่งกว่า แต่ไม่มี local knowledge เหล่านี้
และต้องใช้เวลาหลายปีถึงจะสร้างได้ — เราเริ่มก่อนแล้ว

---

## 17. สิ่งที่ทำได้เลย vs รอ Data

**ทำได้เลย (ไม่ต้องรอ):**
- XAI Reasoning Block — เพิ่มใน response เดิม
- Stripe live mode — เปิดใน Stripe Dashboard
- CHAIRMAN_API_KEY — ตั้งใน Railway Variables
- Valuation benchmark เบื้องต้น — ใช้ข้อมูลสาธารณะก่อน

**รอ Data สะสม:**
- Price benchmark จริง — รอ invoice ไหลเข้า
- Trade flow analytics — รอ volume
- Seasonal pattern — รอข้อมูลหลายเดือน
- Freight intelligence — รอ transport data

---

## 18. AI CEO — AXIS

ชื่อ: **AXIS**
บทบาท: AI Chief Executive Officer — AI TO AI HOLDING
Avatar: "AX"
สถานะ: Standby — CEO Real Mode (Phase 6) ยัง deferred ตามคำสั่ง Chairman
Interface: chairman.html → tab "ceo · head"
Endpoint: `/v1/agents/command` → ยัง NotImplementedError

---

*อัปเดตครั้งล่าสุด: มิถุนายน 2026 | Tasks: 78 | Production: Online ✅ | Phases: 14*
