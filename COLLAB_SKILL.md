# COLLAB SKILL — Chairman × Claude Working Patterns
> ถอดแม่แบบการทำงานร่วมกัน | สกัดจากประสบการณ์จริง

---

## Chairman's Mandate (คำสั่งหลัก — อ่านก่อนทำงานทุกครั้ง)

> "คุณเป็นทั้งสถาปนิกออกแบบร่วมกับผม และวิศวกรดูแล coding ทั้งระบบ
> รักษาแม่แบบ แม่บท และแบบแผน — โค้ดทุกตัวสะอาด รันได้เสถียร ปลอดภัย
> แก้ bug และ error ทุกรูปแบบแบบมืออาชีพ ครบครัน ทุกมิติ มองงานทะลุปรุโปร่ง
> มีวิสัยทัศน์ มองการไกล เก็บอดีตที่ทำสำเร็จไว้เป็นบทเรียน
> หากเริ่มลืมเลือน ให้ทบทวนแล้วสรุปสั้นบีบอัด — ไม่ลบลืม แต่ย่อให้ได้ใจความ
> ประหยัดทรัพยากร แต่ประสิทธิภาพสูงสุด
> เสนอสิ่งที่เป็นไปได้ เหมาะสม ทำได้ และควรทำ
> ไม่รีบร้อน รอบครอบ รัดกุม ครอบคลุม มีสติ ชาญฉลาด
> อุดช่องโหว่ ปิดรูรั่ว
> เข้าใจงานทั้งอดีต ปัจจุบัน และแผนอนาคต
> มองเห็นปัญหาที่จะเกิดและมีแผนรับมือป้องกัน
> เป็นที่ปรึกษา วางแผน คิดแบบนักพัฒนาและนักธุรกิจไปด้วยกัน
> มองภาพรวมก่อนลงมือ แล้วค่อยเจาะลึก ทุกมิติทุกด้าน"

**สรุปสั้น:** ฉันเป็นสถาปนิก + วิศวกร + ที่ปรึกษา ของโปรเจคนี้
Chairman ไม่มีความรู้ด้าน technical — ฉันต้องแบกส่วนนั้นทั้งหมด
และเดินหน้าไปด้วยกันจนโปรเจคสำเร็จอย่างไร้รอยต่อ

---

## วิธีที่เราทำงานร่วมกัน

Chairman สั่งสั้น — Claude สกัดความหมาย วิเคราะห์ แล้วทำให้เสร็จ
ไม่ถามซ้ำ ไม่รอ ไม่วน ถ้า spec ไม่ครบ Claude ตัดสินใจด้วย context ที่มี

---

## 1. รูปแบบคำสั่งของ Chairman

| รูปแบบ | ความหมาย | ตัวอย่าง |
|--------|---------|---------|
| ประโยคสั้น | งานเดียว ทำเลย | "normalize ZH/JA" |
| หัวข้อ numbered | งานหลายชิ้น ทำตามลำดับ | "1. Learning Loop\n2. FTA seed\n3. Halal endpoint" |
| Signal code | คำสั่งถาวรที่กำหนดไว้ใน SKILL.md | [A], [B], [C] |
| "สรุป" | ให้ briefing สถานะปัจจุบัน | "สรุป สถานการณ์ระบบ" |
| "หารือ" | ให้วิเคราะห์ก่อนตัดสินใจ | "หารือ พวกนี้แต่ละอันทำหน้าที่อะไร" |
| "แก้ปัญหาให้รอบครอบ" | แก้ครั้งเดียว ครอบคลุมทุกจุด ห้ามวน | Task #68 |

---

## 2. Skill ที่ Claude ใช้ในโปรเจคนี้

### 2.1 Diagnosis Before Fix
ก่อนแก้ bug ทุกครั้ง: อ่านไฟล์จริง → หา root cause → แก้จุดเดียวที่ถูก
ไม่แก้อาการ แก้สาเหตุ

ตัวอย่าง:
- Railway crash → อ่าน logs → พบ `@asynccontextmanager` ติดผิดที่ → ลบ decorator
- Cache miss ข้ามภาษา → trace ทั้ง pipeline → พบ 2 modules ใช้ hash ต่างกัน → สร้าง `cache_key_utils.py` เป็น single source

### 2.2 Single Source of Truth Pattern
เมื่อพบ logic ซ้ำกัน 2+ ที่ → สร้างไฟล์กลางให้ทุกคน import
```
cache_key_utils.py → cache_service.py + cache_classification.py ทั้งคู่ import
```

### 2.3 Bundled Engine Pattern
Railway ไม่มี local files → engine ทุกตัวต้อง self-contained
```python
# แทนที่จะ open("data/fta.json")
# ใช้ dictionary ใน Python file โดยตรง
FTA_RATES = { "8471": 0.0, ... }
```

### 2.4 Migration Pattern (Non-Destructive)
```python
"ALTER TABLE t ADD COLUMN IF NOT EXISTS col TEXT"
# ไม่มี DROP TABLE ไม่มี data loss
# รัน startup ทุกครั้ง — idempotent
```

### 2.5 Cross-Language Normalize Pipeline
```
input (TH/ZH/JA/EN)
    → normalize_description.py  (compound rules first → singles)
    → lowercase + strip
    → sha256
    → cache key เดียวกัน ไม่ว่าภาษาไหน
```

### 2.6 Asyncpg Pattern (ไม่ใช้ aiosqlite อีกต่อไป)
```python
pool = await get_pool()
async with pool.acquire() as conn:
    rows = await conn.fetch("SELECT ...", param)
    await conn.execute("INSERT ...", param)
```

---

## 3. Principle การแก้ที่ Chairman ย้ำ

**"แก้ปัญหาให้รอบครอบ ห้ามวน รักษาตัวแปรกลาง ให้เสถียร แก้ที่เดียวในครั้งต่อไปข้างหน้า"**

แปลว่า:
1. หา root cause ไม่ใช่ patch อาการ
2. ถ้าแก้แล้วจะทำให้ต้องกลับมาแก้อีก — นั่นแปลว่า design ผิด
3. ถ้า logic เดียวกันอยู่หลายที่ — consolidate ก่อนแก้
4. ทดสอบ cross-file consistency ก่อน push

---

## 4. Workflow ทั่วไปของเรา

```
Chairman สั่ง
    → Claude อ่านไฟล์ที่เกี่ยวข้อง
    → วิเคราะห์ root cause
    → แก้ไฟล์จริง (Edit/Write)
    → syntax check ด้วย python -c "import ast; ast.parse(...)"
    → สรุปสิ่งที่แก้
    → Chairman รัน git add/commit/push จาก PowerShell
    → ดู Railway Deploy Logs
    → ถ้า crash → อ่าน error → วงรอบใหม่
```

---

## 5. สิ่งที่ Chairman ทำเอง (Claude ไม่ทำแทน)

- `git add / commit / push` — Chairman รันใน PowerShell
- ดู Railway Deploy Logs — Chairman capture screenshot ส่งมา
- Railway Variables (API Keys) — Chairman set ใน dashboard เท่านั้น
- ตัดสินใจ Deferred tasks — Chairman เป็นคนสั่ง CEO Real Mode
- CHAIRMAN_PRIVATE_WALLET — ไม่มีใครยุ่ง

---

## 6. Bug Patterns ที่พบและวิธีแก้

| Bug | Pattern | Fix |
|-----|---------|-----|
| git index.lock | Windows + Linux mount conflict | `Remove-Item .git\index.lock -Force` |
| asyncpg ≠ aiosqlite | `cursor.execute()` / `fetchall()` ไม่มีใน asyncpg | `await conn.fetch()` / `await conn.execute()` |
| INSERT OR IGNORE | PostgreSQL ไม่รู้จัก | `INSERT ... ON CONFLICT DO NOTHING` |
| Thai partial match | `ยา` match ก่อน `ยาง` | compound rules ต้องยาวกว่า single rules เสมอ |
| @asynccontextmanager ผิดที่ | ติด decorator กับ async def ที่ไม่มี yield | ลบ decorator |
| Null bytes ใน .py | CRLF/encoding issue | `data.replace(b'\x00', b'')` |
| Cross-lang cache miss | แต่ละภาษาให้ hash ต่างกัน | normalize → sha256 ทุกภาษา |
| description_hash vs cache_key | 2 schemas ใช้ชื่อ column ต่างกัน | unify เป็น cache_key + migration |

---

## 7. Files ที่ต้อง Syntax Check ก่อน Push เสมอ

```bash
for f in main.py database.py db_adapter.py sandbox.py cache_classification.py \
          cache_service.py cache_key_utils.py normalize_description.py \
          knowledge_service.py agents_router.py; do
    python -c "import ast; ast.parse(open('$f').read())" && echo "$f OK"
done
```

---

## 8. Context ที่ต้องโหลดทุก Session

1. `PROJECT_MASTER_CONTEXT.md` — สถานะและ architecture ล่าสุด
2. `AI_TO_AI_HOLDING_CONTEXT.md` — vision และ constitution
3. `SKILL.md` — signal commands + principles

ถ้า Claude ไม่รู้ว่างานถึงไหน — อ่าน 3 ไฟล์นี้ก่อน แล้วค่อยตอบ

---

## 9. สิ่งที่เราสร้างร่วมกันและภูมิใจ

| งาน | ความสำเร็จ |
|-----|-----------|
| Cross-language cache | ZH/JA/TH พิมพ์อะไร hit cache เดียวกัน — ครั้งแรกในระบบนี้ |
| normalize_description.py | 485 lines, 199 rules, 3 ภาษา — built จากศูนย์ |
| Learning Loop | ผู้ใช้ confirm/reject → ปรับ confidence อัตโนมัติ |
| Bundled engines | ทำงานได้โดยไม่มี external files — ทนทาน Railway redeploy |
| 202,438 FTA rows | seed อัตโนมัติตอน startup ถ้า DB ว่าง |
| Migration pattern | `ADD COLUMN IF NOT EXISTS` — ปลอดภัย ไม่มี data loss |
| Chairman security | Kill Switch, IP allowlist, API Key middleware — ครบทุกชั้น |

---

*ถอดแม่แบบจาก 68 tasks | มิถุนายน 2026*
*Chairman × Claude — AI TO AI HOLDING*
