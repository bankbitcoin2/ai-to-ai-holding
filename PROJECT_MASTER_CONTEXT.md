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
| Commit ล่าสุด | 484f127 |
| API Price | $0.50 / query |

---

## 3. Architecture Stack (Production)

```
FastAPI + Uvicorn
    └── asyncpg → PostgreSQL (Railway)
    └── Middleware: KillSwitch → Security → CORS
    └── Routers: sandbox, customs, billing, chairman, agents, kill_switch, treasury_wallet, invoice
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

### Phase 8 & 8.1 — Invoice Intelligence Pipeline ✅ (commit 484f127)
- `schema_invoice.sql` — ตาราง invoice_submissions + invoice_items (PostgreSQL)
- `invoice_parser.py` — detect + parse: PDF_TEXT/PDF_SCAN/IMAGE/EXCEL/CSV ผ่าน pdfplumber/Claude Vision/pandas
  - approach: `_compile_excel_text` (cell → pipe-delimited) + `_parse_compiled_text` (direct parse, ไม่พึ่ง Claude)
  - fallback: Claude text extraction กรณี format แปลก
- `invoice_service.py` — classify ทุก item + duty_rate + FTA saving + OGA/Halal → save DB → summary
- `invoice_router.py` — POST /v1/invoice/upload | GET /v1/invoice/{id} | GET /v1/invoice/list/all
- `main.py` — include invoice_router
- `database.py` — เพิ่ม schema_invoice.sql ใน init list
- `dashboard.html` — Invoice Intelligence section: drag & drop, summary grid, per-item table + XAI, warnings

### Phase 11 — XAI Reasoning Block ✅ (commit 484f127)
- `xai_reasoning.py` — generate_reasoning(): ส่ง HS+confidence+origin+duty → Claude Haiku → Thai explanation
- Wire เข้า invoice_service.py: per-item XAI reasoning บันทึก DB + return ใน API response
- Wire เข้า customs_service.py + sandbox.py: แสดง reasoning ใน /v1/classify response
- dashboard.html: XAI block แสดงใต้แต่ละ item พร้อม evidence chips + GRI steps + rejection reasoning

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
| 8 | Invoice Intelligence Pipeline | ✅ Done |
| 8.1 | Invoice Upload Channel (รูปภาพ/PDF/Excel) | ✅ Done |
| 9 | Freight Intelligence & Logistics Expansion | 📋 Planned |
| 10 | Customs Software Integration (Pre-flight Check) | 📋 Planned |
| 11 | Explainable AI (XAI) Reasoning Block | ✅ Done |
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

---

## 19. ไฟล์ Invoice Pipeline (Phase 8.1 + 11)

| ไฟล์ | หน้าที่ |
|------|---------|
| `schema_invoice.sql` | invoice_submissions + invoice_items schema |
| `invoice_parser.py` | detect file type → compile Excel → parse text → structured dict |
| `invoice_service.py` | classify + duty_rate + FTA + OGA/Halal → save DB → summary |
| `invoice_router.py` | 3 endpoints: upload / get / list |
| `xai_reasoning.py` | generate_reasoning() → Claude Haiku → Thai XAI per item |
| `classification_agent.py` | classify_item() → ClassificationResult dataclass |
| `static/dashboard.html` | Invoice Intelligence: drag & drop + XAI block |

**Flow:** upload → parse (Excel: compile→parse, PDF_TEXT: pdfplumber, IMAGE: Claude Vision)
→ classify per item (classification_agent) → duty_rate (knowledge_service.lookup_tax_rate)
→ FTA (knowledge_service.get_fta_form) → OGA + Halal → XAI reasoning → save DB → summary

**ผลลัพธ์จริง (TEST_INVOICE_2026.xlsx — 8 items, CN→TH, CIF):**
- มูลค่ารวม $41,610 | ภาษีประมาณ $325 | FTA ประหยัด $4,071
- Cotton T-Shirt MFN 30% | Frozen Beef MFN 50% | PP Bag MFN 20%
- Electronics (Laptop/Headphone/Cable) = 0% MFN จริงตาม Thai Tariff

---

## 20. Bug Patterns ที่พบและแก้แล้ว (Invoice Pipeline)

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| ไม่พบรายการสินค้า | openpyxl ไม่ได้ติดตั้งบน Railway | เพิ่มใน requirements.txt |
| Excel items=[] | `_smart_parse_excel` header detection ล้มเหลวบน Railway | เปลี่ยนเป็น compile→parse approach |
| HS Code = "–" | เรียก `knowledge_service.classify_hs_code` ที่ไม่มี | ใช้ `classification_agent.classify_item` |
| ClassificationResult.get() error | classify_item คืน dataclass ไม่ใช่ dict | แปลง → plain dict ก่อน return |
| `destination_country` error | classify_item ไม่มี param นี้ | ลบออก |
| มูลค่ารวม $0.00 | to_float ไม่ strip `$`, AMOUNT_KW ไม่มี "total" | strip symbols + เพิ่ม "total" + fallback qty×price |
| ภาษี % = 0.0% | check_fta_eligibility ไม่มี, ไม่มี duty_rate lookup | `get_fta_form` + `lookup_tax_rate` |
| "upstream error" not valid JSON | Railway timeout — sequential 8×2 Claude calls ~80s | asyncio.gather + Semaphore(4) → ~20-25s |
| `asyncio.coroutine` DeprecationWarning | ใช้ coroutine ใน ternary fallback กรณี hs="" | เรียกฟังก์ชันตรง ทุกตัวมี try/except ใน |
| git index.lock | bash mount ใน shell session lock ซ้อน | user รัน `Remove-Item .git\index.lock` จาก PowerShell |

---

## 21. UI Fixes — Invoice Dashboard (commit 2e52a71)

### ปัญหา
- ตาราง 15 คอลัมน์ล้นขอบขวา ข้อมูลขาดหาย
- Drop zone ยังแสดงอยู่หลัง upload สำเร็จ → อัพซ้ำได้
- API Key แสดงเปิดเผยอยู่ใน section card แยก

### การแก้ไข

**Fix 1 — Table overflow**
- ลดจาก 15 → 10 คอลัมน์ในตารางหลัก
- คอลัมน์ที่ตัดออก (ย้ายไปใน Detail Panel): Qty, Unit Price, Declared HS
- รวม OGA / Halal / HS Mismatch → คอลัมน์ "Flags" เดียว (icon badge)
- ตาราง: `min-width:700px` + font `.77rem` + `-webkit-overflow-scrolling:touch`
- Description cell: `-webkit-line-clamp:2` ป้องกันข้อความยาวทำแถวสูง

**Fix 2 — Drop zone ซ่อนหลัง upload**
- `handleInvoiceFile`: หลัง `renderInvoiceResult` → `zone.style.display = 'none'`
- เพิ่มฟังก์ชัน `resetInvoiceUpload()`: คืน drop zone + ล้าง invResult
- `renderInvoiceResult`: แสดงปุ่ม "📤 อัพโหลดใบใหม่" ด้านบนสุดผลลัพธ์

**Fix 3 — API Key masked ใน credit card**
- ลบ section card `🔑 API Key ของคุณ` เดิมออก
- Key แสดงใน credit card: `filter:blur(4px)` → hover เพื่อดู
- ปุ่ม Copy อยู่ข้างๆ พร้อม blur mask

---

*อัปเดตครั้งล่าสุด: 23 มิถุนายน 2026 | Tasks: 95 | Production: Online ✅ | Commits: 10 | Phases: 14 (9/14 Done)*
