# NEXT PHASE MASTER PLAN — AI TO AI HOLDING
> วิเคราะห์จาก Next_plan_Goal.txt | 25 มิถุนายน 2026
> จัดลำดับตาม dependency chain + business impact + technical readiness

---

## รับทราบ_เข้าใจเนื้อหาและแผนงานแล้ว

ผมอ่านและวิเคราะห์ทั้งหมดแล้ว สรุปเนื้อหา 3 แกนหลัก:

1. **แกนธุรกิจ**: Customer analytics, membership tiers, pricing model, project valuation, LINE/app channel, IP protection
2. **แกน Intelligence**: Landed Cost, Price Benchmark, Freight Auditor, What-If Optimizer, Duty Engineering
3. **แกน Expansion**: ASEAN localization, CBAM carbon, Customs Audit Insurance, Dynamic OGA

หลักการจัดลำดับ: ทำ **รากฐานข้อมูล** ก่อน (ถ้าไม่มี data → intelligence layer ทำไม่ได้) → **revenue model** (ถ้าเก็บเงินไม่ได้ → scale ไม่มีทุน) → **intelligence features** (ขายได้แพงขึ้น) → **expansion** (ขยายตลาด)

---

## TIER 1 — รากฐาน (ทำก่อน ไม่มี dependency)

### Phase 15: Invoice Validation + Backlog Cleanup
**เป้าหมาย**: ปิดจุดรั่วก่อนเปิดขายจริง
**งาน**:
- P1: `_validate_items()` — กรอง garbage ก่อนส่ง Claude (ประหยัดเงิน)
- P2: Top 3 Candidates — แสดง HS code ตัวเลือกสำรอง ($0 เพิ่ม)
- P3: Cache Reasoning — cache XAI reasoning (ประหยัด $0.12/invoice)
- P4: Learning Feedback Loop — vote_count + verified source
- P5: Queue + Rate Limit — ป้องกัน Claude overload

**ไฟล์ที่แก้**: invoice_service.py, classification_agent.py, dashboard.html
**Dependency**: ไม่มี — ทำได้ทันที
**ระยะเวลาประมาณ**: 2-3 sessions

---

### Phase 16: Customer Analytics Dashboard
**เป้าหมาย**: ลูกค้าเห็นข้อมูลการใช้งานของตัวเอง
**งาน**:
- เพิ่ม `client_id` tracking ใน invoice_submissions (ผูกกับ API key)
- Endpoint: GET /v1/client/analytics — ดึงข้อมูลรายเดือน/ปี
  - จำนวน invoice ที่ทำรายการ
  - มูลค่ารวม (line_value sum)
  - FTA savings รวม
  - Credit topup vs usage
  - จำนวน items classified
- Dashboard section: "สถิติการใช้งานของฉัน"
- Admin view: Chairman เห็นข้อมูลทุก client

**ไฟล์ใหม่**: client_analytics.py, client_analytics_router.py
**ไฟล์แก้**: schema_billing_v1.sql (เพิ่ม client analytics view), dashboard.html
**Dependency**: billing tables + invoice_items ที่มีอยู่แล้ว
**ระยะเวลาประมาณ**: 2 sessions

---

### Phase 17: API Pricing Model + Currency Exchange
**เป้าหมาย**: ตั้งราคาถูกต้อง + รองรับหลายสกุลเงิน
**งาน**:
- วิเคราะห์ต้นทุนจริงต่อ call:
  - Claude API: ~$0.003-0.02 ต่อ classification
  - XAI Reasoning: ~$0.001 ต่อ item
  - Infrastructure: Railway ~$5-20/mo
  - รวมต้นทุนต่อ invoice: ~$0.05-0.15 (8 items average)
- ตั้งเรท Tiered pricing:
  - Standard: $0.50/query (ปัจจุบัน)
  - Volume (VAN/Software): $0.003-0.015/call
  - Enterprise: $200-500/mo
- เพิ่ม exchange rate service:
  - ดึง THB/USD/CNY/JPY rate จาก API (exchangerate-api.com หรือ BOT)
  - แปลงอัตโนมัติตอนแสดงผลและตอนเรียกเก็บ
  - บันทึก exchange rate ณ เวลาทำรายการ

**ไฟล์ใหม่**: currency_service.py, pricing_engine.py
**Dependency**: P16 (usage data เพื่อประเมินต้นทุนจริง)
**ระยะเวลาประมาณ**: 1-2 sessions

---

## TIER 2 — Revenue & Growth

### Phase 18: Membership Tier System
**เป้าหมาย**: กลไกรักษาลูกค้า + upsell
**ระดับสมาชิก**:

| Level | เงื่อนไข | ส่วนลด API | สิทธิพิเศษ |
|-------|----------|-----------|-----------|
| VIP | สมัคร + เติม credit | - | Basic access |
| Gold | ใช้งาน ≥ 100 queries/mo หรือมูลค่า ≥ ฿100K | 5% | Priority queue |
| Platinum | ≥ 500 queries/mo หรือ ≥ ฿500K | 10% | Dedicated support + XAI detail |
| Diamond | ≥ 2,000 queries/mo หรือ ≥ ฿2M | 15% | Custom rules + API rate limit up |
| SuperPremium | ≥ 10,000 queries/mo หรือ ≥ ฿10M | 20% | White-label + Audit report |

**งาน**:
- Schema: membership_tiers + client_tier_history tables
- Engine: auto-calculate tier from usage data monthly
- UI: tier badge + progress bar ใน dashboard
- Billing integration: apply discount ตอนหัก credit

**Dependency**: P16 + P17
**ระยะเวลาประมาณ**: 2 sessions

---

### Phase 19: LINE / Mobile App / Field Plugin
**เป้าหมาย**: ช่องทางหน้างานสำหรับชิปปิ้ง/ตัวแทนออกของ
**แนวทาง**:
- **LINE OA + LIFF App** (ตลาดไทย — ทุกคนมี LINE)
  - ผู้ใช้ถ่ายรูป invoice → ส่งใน LINE → ได้ผล HS+FTA+OGA+XAI
  - ต้อง login ผ่าน LINE + มี credit เท่านั้น
  - Webhook: LINE → API /v1/invoice/upload → return result
- **Web PWA** (Progressive Web App)
  - ติดตั้งบนมือถือเหมือน app จริง
  - Camera API → ถ่ายรูป → upload ทันที
  - Offline: cache HS results ล่าสุด
- **Claude MCP Plugin** (สำหรับ developer/tech user)
  - ปลั๊กเข้า Claude Desktop / Claude Code
  - เรียก classify_hs / check_fta / analyze_invoice ผ่าน MCP

**Dependency**: P17 (billing) + P18 (membership)
**ระยะเวลาประมาณ**: 3-4 sessions

---

### Phase 20: IP Protection + Project Valuation
**เป้าหมาย**: ป้องกันทรัพย์สินทางปัญญา + ประเมินมูลค่า
**หลักการสำคัญ**:
- **ไม่มีทีมพัฒนาภายนอก** — การพัฒนาผ่าน Chairman คนเดียว
- **Open-Core Model**:
  - เปิด: SDK, API docs, connector examples, LINE integration sample
  - ปิด (Proprietary): AI classification logic, price benchmark DB, FTA switching engine, normalize rules 199 ข้อ, XAI reasoning prompt
- **License**: Business Source License (BSL) — ใช้ฟรีแต่ห้ามนำไปขายแข่งเชิงพาณิชย์
- **README.md** ใหม่: Quick Start 5 บรรทัด, demo endpoint, pricing

**Project Valuation Report** (ตั้งต้น ฿15M):
- ต้นทุนพัฒนา: เวลา + AI compute + infrastructure
- ภูมิปัญญา: 199 normalize rules, OGA/Halal/FTA logic เฉพาะไทย
- รายได้ศักยภาพ: projection 1-3 ปี
- Economic moat: local knowledge ที่ต่างชาติทำไม่ได้
- ส่งตรงรายงานให้ Chairman (ออฟฟิศส่วนตัว)

**Dependency**: ระบบ stable + revenue data จาก P16-P18
**ระยะเวลาประมาณ**: 2 sessions (valuation report + license setup)

---

## TIER 3 — Intelligence Layer (ขายได้แพงขึ้น)

### Phase 21: Landed Cost Calculator
**เป้าหมาย**: ลูกค้ารู้ต้นทุนรวมถึงหน้าโรงงานก่อนสั่งซื้อ
**Input เพิ่ม**: Incoterms (FOB/EXW/CIF), Freight rate, Insurance, Inland transport
**Output**: Total Landed Cost ต่อชิ้น = สินค้า + Freight + Insurance + Duty + VAT 7% + Local charges
**Data source**: เรทมาตรฐานตลาด (จากเอกสาร) + crowdsource จากบิลลูกค้า

**ไฟล์ใหม่**: landed_cost_engine.py, freight_rate_service.py
**Dependency**: freight rate data + tax engine ที่มีอยู่

---

### Phase 22: Price Benchmark + Valuation Alert (= Phase 12 เดิม ยกระดับ)
**เป้าหมาย**: ตรวจจับ under-valuation อัตโนมัติ
**Data sources**:
- invoice จริงที่ไหลเข้าระบบ (anonymized)
- คิดค้า.com — ดัชนีราคาสินค้ารายเดือน
- กรมศุลกากร — สถิติราคานำเข้า
**Logic**: unit price < benchmark median - 30% → Red Flag
**Output**: Valuation Risk Score per item

---

### Phase 23: Freight Rate Auditor
**เป้าหมาย**: ตรวจบิลค่าขนส่งว่าแพงเกินจริงไหม
**Flow**: อัพโหลดบิลชิปปิ้ง → AI แกะรายการ (THC, CFS, D/O, clearance fee) → เทียบเรทตลาด → เตือน
**ขายเป็น**: Premium feature สำหรับ Procurement/CFO

---

### Phase 24: What-If Scenario Optimizer + Duty Engineering
**เป้าหมาย**: จำลองเส้นทางและ FTA form ที่ประหยัดสุด
**Output**: 3 options เปรียบเทียบ (เร็วสุด / คุ้มสุด / ประหยัดสุดถ้า volume ถึง)
**ขายเป็น**: Strategic Sourcing Tool สำหรับองค์กรใหญ่

---

## TIER 4 — Expansion & Premium (ระยะยาว)

### Phase 25: Customs Audit Insurance (Risk Score)
ตรวจประวัติใบขนย้อนหลัง 5 ปี → Audit Risk Score → ขายให้ CFO บริษัทมหาชน

### Phase 26: Dynamic OGA + NSW Integration (= Phase 13 เดิม ยกระดับ)
ดึงกฎ OGA 36 หน่วยงานจาก NSW อัตโนมัติ ทุกสัปดาห์

### Phase 27: Green Customs / CBAM Carbon Tracker
คำนวณ Carbon Footprint → ออก Carbon Report สำหรับส่งออกไปยุโรป/อเมริกา

### Phase 28: ASEAN & Global Expansion
ขยายจากไทย → เวียดนาม/มาเลเซีย/อินโดนีเซีย — CEO AI (AXIS) สั่ง agent ระดับประเทศ

---

## Dependency Chain (ลำดับที่ต้องทำตาม)

```
P15 (Validation+Backlog) ─────────────────────────────────┐
    ↓                                                      │
P16 (Customer Analytics) ──→ P17 (Pricing+Currency) ───┐   │
                                                       ↓   │
                                P18 (Membership Tiers) ←───┘
                                    ↓
                                P19 (LINE/App) ──→ P20 (IP+Valuation)
                                    ↓
                    P21 (Landed Cost) ──→ P22 (Price Benchmark)
                                              ↓
                                    P23 (Freight Auditor)
                                              ↓
                                    P24 (What-If Optimizer)
                                              ↓
                    P25/P26/P27/P28 (Expansion — ทำเมื่อพร้อม)
```

---

## แหล่งข้อมูลภายนอกที่ต้องเชื่อมต่อ

| มิติ | แหล่ง | วิธีดึง | ใช้ใน Phase |
|------|-------|---------|------------|
| HS Code + อัตราภาษี | กรมศุลกากร (e-Service) | Web scraper / manual update | มีอยู่แล้ว |
| สถิติการค้า | กระทรวงพาณิชย์ | API / CSV download | P22 |
| OGA 36 หน่วยงาน | NSW Thailand | Mapping rules | P26 |
| ราคาตลาดกลาง | คิดค้า.com | Scraper / monthly update | P22 |
| Exchange rate | BOT / exchangerate-api | REST API | P17 |
| Freight rate (global) | Freightos (FBX) / Xeneta | API subscription | P21, P23 |
| Freight rate (local) | Crowdsource จากบิลลูกค้า | Anonymized extraction | P23 |
| Carbon factors | CBAM database (EU) | Official tables | P27 |

---

## หลักการป้องกันการขโมยข้อมูลทางธุรกิจ

1. **Core IP ปิดบนเซิร์ฟเวอร์เท่านั้น** — normalize_description.py (199 rules), classification prompt, FTA switching logic, price benchmark DB ไม่เปิดเผย
2. **API-only access** — ลูกค้าเรียกผ่าน API key เท่านั้น ไม่เห็น logic ภายใน
3. **BSL License** — ใช้ฟรีได้แต่ห้ามนำไปขายเชิงพาณิชย์โดยไม่ได้อนุญาต
4. **Data moat** — ยิ่งมีลูกค้ามาก ข้อมูล price benchmark ยิ่งแม่น คู่แข่งก๊อปโค้ดไปก็ไม่มี data
5. **Chairman คนเดียวควบคุม** — ไม่มี external contributor, ไม่มี collaborator access บน GitHub
6. **Audit trail** — ทุก API call มี evidence_hash ติดตามได้

---

## การเตรียมระบบก่อนปล่อยตัว (Readiness Checklist)

ก่อนเปิดแต่ละ version ตรวจ:
- [ ] Unit test ครอบคลุม critical path
- [ ] Rate limit + queue ทำงาน
- [ ] Billing เก็บเงินได้จริง (Stripe live ✅ ตั้งแล้ว)
- [ ] Error handling ไม่ leak internal info
- [ ] Kill Switch ทำงาน
- [ ] .gitignore ครบ ไม่มี sensitive files
- [ ] Railway env vars ครบ
- [ ] Dashboard แสดงผลถูกต้องทุก locale

---

*จัดทำโดย AI Agent | วิเคราะห์จาก Next_plan_Goal.txt | 25 มิถุนายน 2026*
*✅ อนุมัติโดย: Chairman Thanwa | 25 มิถุนายน 2026 | สถานะ: APPROVED*
