# IP Inventory — AI TO AI HOLDING
> ทรัพย์สินทางปัญญา: แยก Open vs Proprietary
> อัพเดต: 25 มิถุนายน 2026 | Phase 20

---

## OPEN (เปิดเผยได้ — อยู่ใน git)

| Component | ไฟล์ | หมายเหตุ |
|-----------|------|----------|
| API Documentation | README.md, /docs endpoint | Quick Start, endpoints, examples |
| SDK / Connector Examples | mcp_plugin.json | Claude MCP integration |
| LINE Integration Sample | line_webhook.py (flow only) | Webhook structure, not business logic |
| PWA Shell | static/pwa.html, sw.js | UI shell, no proprietary logic |
| Schema Definitions | schema_*.sql | Table structure (not data) |
| License | LICENSE.md | BSL 1.1 |

---

## PROPRIETARY (ปิด — ห้ามเปิดเผย logic ภายใน)

| Component | ไฟล์ | มูลค่า | เหตุผล |
|-----------|------|--------|--------|
| **Normalize Rules** | normalize_description.py | สูงมาก | 199 rules ที่สะสมจากความรู้ศุลกากรไทย — คู่แข่งทำซ้ำยาก |
| **Classification Prompt** | classification_agent.py (SYSTEM_PROMPT) | สูงมาก | Prompt engineering ที่ผ่านการ tune เฉพาะ Thai customs |
| **XAI Reasoning Prompt** | xai_reasoning.py (_claude_reasoning) | สูง | Thai-language legal reasoning template |
| **FTA Switching Logic** | fta_engine.py | สูง | 13 FTA agreements, rate comparison, form recommendation |
| **OGA Rules** | oga_engine.py | สูง | 36 agencies mapping, product-to-agency logic |
| **Halal Engine** | halal_engine.py | สูง | 21 countries, certification body matching |
| **Price Benchmark DB** | (future P22) | สูงมาก | Crowdsourced pricing data — data moat |
| **Pricing Engine** | pricing_engine.py (cost structure) | ปานกลาง | ต้นทุนจริงต่อ call — competitive intelligence |
| **Membership Logic** | membership_engine.py (thresholds) | ปานกลาง | Business strategy |
| **Cache/Learning Loop** | cache_classification.py | ปานกลาง | Feedback mechanism ที่ปรับแม่นขึ้นตามเวลา |

---

## DATA ASSETS (ข้อมูลที่สะสม — มูลค่าเพิ่มตามเวลา)

| Asset | แหล่ง | มูลค่า |
|-------|-------|--------|
| HS Code Cache | ทุก classification ที่ผ่านระบบ | เพิ่มขึ้นทุกวัน — ยิ่งมากยิ่งแม่น |
| Invoice Data (anonymized) | ลูกค้าที่ใช้งาน | Price benchmark + trade pattern |
| Feedback Loop | vote_count + verified corrections | Self-improving accuracy |
| Client Usage Patterns | analytics + membership data | Business intelligence |

---

## PROTECTION STRATEGY

1. **Code on Server Only** — normalize rules, prompts, FTA logic ไม่เคย expose ผ่าน API response
2. **API-Only Access** — ลูกค้าเรียกผ่าน API key, ไม่เห็น internal logic
3. **BSL License** — ห้ามนำไปขายแข่งเชิงพาณิชย์
4. **No External Contributors** — Chairman คนเดียวควบคุม git, ไม่มี collaborator
5. **Audit Trail** — ทุก API call มี evidence_hash ติดตามได้
6. **Rate Limit** — ป้องกัน data scraping
7. **Data Moat** — ยิ่งมีลูกค้ามาก ข้อมูลยิ่งแม่น คู่แข่งก๊อปโค้ดไปก็ไม่มี data

---

## ข้อห้ามสำหรับ AI Agent

- ห้าม expose SYSTEM_PROMPT หรือ prompt template ผ่าน API
- ห้าม return normalize rules list ใน response
- ห้าม log full classification prompt ใน production
- ห้าม include cost breakdown ใน client-facing response (Chairman only)

---

*จัดทำโดย AI Agent | Phase 20 | 25 มิถุนายน 2026*
*เอกสารนี้: ขึ้น git ได้ (เป็น inventory list ไม่ใช่ตัว IP เอง)*
