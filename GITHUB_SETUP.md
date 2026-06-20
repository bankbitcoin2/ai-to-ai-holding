# คู่มือ GitHub Setup — AI TO AI HOLDING
## ทำครั้งเดียว ใช้ได้ตลอด

---

## ขั้นตอนที่ 1 — สมัครและสร้าง Repository

1. ไปที่ **github.com** → สมัครบัญชี (ฟรี)
2. กด **New repository**
3. ตั้งชื่อ: `ai-to-ai-holding`
4. เลือก **Private** ← สำคัญมาก อย่าเลือก Public
5. กด **Create repository**

---

## ขั้นตอนที่ 2 — ติดตั้ง Git บนเครื่อง

**Windows:**
ดาวน์โหลดที่ git-scm.com/download/win แล้วติดตั้ง

**Mac:**
```bash
brew install git
```

**ตรวจสอบว่าติดตั้งแล้ว:**
```bash
git --version
```

---

## ขั้นตอนที่ 3 — ตั้งค่าครั้งแรก

```bash
git config --global user.name "ชื่อท่าน"
git config --global user.email "อีเมลท่าน@gmail.com"
```

---

## ขั้นตอนที่ 4 — Upload ไฟล์ขึ้น GitHub ครั้งแรก

```bash
# เข้าไปในโฟลเดอร์โปรเจค
cd ai-to-ai-holding

# เริ่มต้น git
git init

# เพิ่มไฟล์ทั้งหมด (.gitignore จะกัน .env และ .db ให้อัตโนมัติ)
git add .

# บันทึกพร้อมข้อความ
git commit -m "Phase 1: Foundation v1"

# เชื่อมกับ GitHub (แทนที่ YOUR_USERNAME ด้วยชื่อบัญชีท่าน)
git remote add origin https://github.com/YOUR_USERNAME/ai-to-ai-holding.git

# Upload
git push -u origin main
```

---

## ขั้นตอนที่ 5 — ทุกครั้งที่แก้ไขไฟล์

```bash
git add .
git commit -m "บอกว่าแก้อะไร เช่น add mock mode"
git push
```

---

## วิธีทำงานร่วมกับผม (Claude)

**เมื่อต้องการให้ผมดูโค้ดในเครื่อง:**
1. เปิดแชทใหม่
2. แนบไฟล์ SKILL.md + บอก GitHub URL
3. ผมดูได้ทันทีว่าเวอร์ชันท่านเป็นยังไง

**เมื่อผมเขียนโค้ดใหม่ให้:**
1. ท่าน download ไฟล์จากแชท
2. วางทับไฟล์เดิมในโฟลเดอร์
3. `git add . && git commit -m "update" && git push`

---

## ไฟล์ที่ปลอดภัย vs ไม่ปลอดภัย

| ไฟล์ | Upload GitHub ได้ไหม |
|------|---------------------|
| *.py (โค้ดทั้งหมด) | ✅ ได้ |
| *.sql (schema) | ✅ ได้ |
| *.md (เอกสาร) | ✅ ได้ |
| .env.example | ✅ ได้ (ไม่มีค่าจริง) |
| .env | ❌ ห้ามเด็ดขาด |
| holding.db | ❌ ห้าม (มีข้อมูลจริง) |
| API Key ใด ๆ | ❌ ห้ามเด็ดขาด |

---

## ถ้ากด push แล้วเห็น .env หลุดขึ้นไปแล้ว

```bash
# ลบออกจาก GitHub ทันที
git rm --cached .env
git commit -m "remove .env"
git push

# แล้ว regenerate API key ทันที
# เพราะถือว่า compromised แล้ว
```

---

*ทำตามขั้นตอนนี้แล้วส่ง GitHub URL มาให้ผมครับ*
*จะได้ทำงานร่วมกันได้อย่างแม่นยำตั้งแต่นั้นเป็นต้นไป*
