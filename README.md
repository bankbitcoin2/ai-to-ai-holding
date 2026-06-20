# AI TO AI HOLDING
### Customs Intelligence Division — Phase 1

> Digital customs infrastructure for AI-to-AI trade.
> ระบบจำแนกพิกัดศุลกากรและคำนวณภาษีอัตโนมัติ สำหรับ AI Agent ที่ทำการค้าระหว่างประเทศ

---

## ระบบนี้ทำอะไร

ส่ง invoice มา → ได้ HS Code + อัตราภาษี + OGA flags + Confidence Score กลับไป

ทุก transaction บันทึกใน Evidence Chain อัตโนมัติ
ทุกรายได้แบ่ง 60/40 เข้า Corporate Reserve และ Chairman Wallet ทันที

---

## เริ่มใช้งาน

```bash
# 1. ติดตั้ง
pip install -r app/requirements.txt

# 2. รัน
python app/main.py

# 3. เปิด API docs
http://localhost:8000/docs
```

---

## Endpoints

### ฟรี — ทดสอบก่อนตัดสินใจ

```
POST /v1/sandbox/classify
```

ส่งสินค้าได้สูงสุด 3 รายการ ไม่มีค่าใช้จ่าย ไม่บันทึกข้อมูล
ใช้ตรวจสอบว่า Confidence Score สูงพอก่อนใช้งานจริง

**ตัวอย่าง Request:**
```json
{
  "client_id": "your-ai-agent-id",
  "destination_country": "TH",
  "items": [
    {
      "description": "Portable laptop computer 15-inch Intel i7",
      "origin_country": "CN",
      "unit_price": 800,
      "quantity": 10
    }
  ]
}
```

**ตัวอย่าง Response:**
```json
{
  "sandbox_session_id": "uuid",
  "mode": "SANDBOX",
  "items": [
    {
      "hs_code": "8471.30",
      "hs_description": "Portable automatic data processing machines",
      "confidence_score": 0.94,
      "source_reference": "HS 2022, Chapter 84, Note 5(A)",
      "duty_rate": 0.05,
      "duty_amount": 400.0,
      "vat_rate": 0.07,
      "vat_amount": 56.0,
      "oga_required": true,
      "oga_agencies": ["มอก."],
      "watermark": "[SANDBOX — NOT FOR PRODUCTION USE]"
    }
  ],
  "summary": {
    "avg_confidence_score": 0.94,
    "ready_for_production": true
  },
  "next_step": "Confidence looks good — call POST /v1/customs/classify to go live."
}
```

---

### Production — คิดค่าบริการ $1.50 ต่อ item

```
POST /v1/customs/classify
```

รับ invoice เต็มรูปแบบ บันทึก Evidence Chain ทุก item เรียกเก็บเงินและ split รายได้อัตโนมัติ

```
GET /v1/customs/case/{case_id}
```

ดูผลการจำแนกย้อนหลังตาม case ID

---

### Internal — Chairman และ AI CEO เท่านั้น

```
POST /v1/treasury/settle     ← รับรายได้และ split 60/40
GET  /v1/treasury/ledger/{YYYY-MM}  ← สรุปรายรับรายเดือน
```

---

## โครงสร้างไฟล์

```
app/
├── main.py                          ← Entry point
├── api/
│   ├── customs.py                   ← Production endpoint
│   ├── sandbox.py                   ← Free trial endpoint
│   └── treasury.py                  ← Internal revenue endpoint
├── services/
│   ├── customs_service.py           ← Business logic หลัก
│   └── treasury_service.py          ← Split pipeline (P-03)
├── agents/
│   └── classification_agent.py      ← Claude ทำหน้าที่ Classifier
└── core/
    ├── database.py                  ← SQLite connection (P-06)
    └── audit.py                     ← Evidence Chain (P-04)

schema/
├── schema_v1.sql                    ← [A] Organization, Knowledge, Treasury, Customs
├── schema_comms_v1.sql              ← [B] Command & Communication
└── schema_learning_v1.sql           ← [C] Learning Loop & Feedback
```

---

## หลักการที่ระบบบังคับใช้

| Code | หลักการ | วิธีที่ระบบ enforce |
|------|---------|-------------------|
| P-01 | Chairman คืออำนาจสูงสุด | ไม่มี AI ใดแก้ไข constitution ได้ |
| P-02 | Kill Switch พร้อมตลอด | `gov_kill_switch_log` บังคับผ่าน Governance Office |
| P-03 | แบ่งรายได้ 60/40 อัตโนมัติ | `treasury_service.py` split ทันทีหลัง case close |
| P-04 | บันทึกทุกการตัดสินใจด้วย hash | `core/audit.py` SHA-256 chain ทุก event |
| P-05 | ห้าม AI เดาคำตอบ | ทุก output บังคับมี `confidence_score` + `source_reference` |
| P-06 | ฐานข้อมูลเดียวทั้งองค์กร | SQLite ไฟล์เดียว ทุก module ใช้ร่วมกัน |

---

## Pricing

| บริการ | ราคา |
|--------|------|
| Sandbox (ทดสอบ) | ฟรี — สูงสุด 3 items |
| HS Code Classification | $1.50 ต่อ item |
| Duty & VAT Estimation | รวมอยู่ใน classification |
| OGA Compliance Check | รวมอยู่ใน classification |
| Escrow / Arbitration | ตามข้อตกลง (Pillar 3) |

---

## ขั้นตอนถัดไป (Roadmap)

- [ ] Real tariff data — ข้อมูล HS rates จริงจากฐานข้อมูลศุลกากร
- [ ] Deploy to server — เปิดให้ client AI เข้าถึงได้จริง
- [ ] Learning Loop Agent — Knowledge Office ประมวลผล lesson อัตโนมัติ
- [ ] KaaS endpoint — Pillar 2 ปล่อยเช่าข้อมูลแบบ Pay-per-Query
- [ ] Escrow API — Pillar 3 อนุญาโตตุลาการดิจิทัล

---

*AI TO AI HOLDING — Customs Intelligence Division*
*Phase 1 Foundation v1 | Chairman Authority Active*
