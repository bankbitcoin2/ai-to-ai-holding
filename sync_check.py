"""
sync_check.py
รันบนเครื่องท่านประธาน — ไม่ต้องการ internet ไม่ต้องการ API key
ตรวจสอบไฟล์ครบไหม + บอกคำสั่งรันทุกอย่างพร้อมใช้
"""
import os
import sys
import hashlib
from pathlib import Path

REQUIRED_FILES = [
    "schema/schema_v1.sql",
    "schema/schema_comms_v1.sql",
    "schema/schema_learning_v1.sql",
    "app/main.py",
    "app/core/database.py",
    "app/core/audit.py",
    "app/core/config.py",
    "app/agents/__init__.py",
    "app/agents/classification_agent.py",
    "app/agents/mock_classification_agent.py",
    "app/agents/ceo_agent.py",
    "app/agents/office_heads.py",
    "app/services/customs_service.py",
    "app/services/treasury_service.py",
    "app/api/customs.py",
    "app/api/sandbox.py",
    "app/api/treasury.py",
    "app/api/ceo.py",
    ".env.example",
    ".gitignore",
    "README.md",
    "GITHUB_SETUP.md",
    "app/requirements.txt",
]

def line(char="═", n=52):
    print("  " + char * n)

def check(base_dir="."):
    base = Path(base_dir)
    present, missing = [], []

    for rel in REQUIRED_FILES:
        f = base / rel
        if f.exists():
            present.append((rel, f.stat().st_size))
        else:
            missing.append(rel)

    print()
    line("╔"); print("  ║  AI TO AI HOLDING — System Check & Run Guide  ║"); line("╚")
    print(f"  📁 โฟลเดอร์: {base.resolve()}")
    print()

    # ── ไฟล์ที่มี ──
    print(f"  ✅ ไฟล์ที่มีแล้ว ({len(present)}/{len(REQUIRED_FILES)})")
    print()
    for rel, size in present:
        print(f"     ✓  {rel:<48} {size:>7} bytes")

    # ── ไฟล์ที่หาย ──
    if missing:
        print()
        print(f"  ❌ ไฟล์ที่หายไป ({len(missing)} ไฟล์)")
        print()
        for rel in missing:
            print(f"     ✗  {rel}")

    print()
    line()

    # ── .env check ──
    env = base / ".env"
    env_ok = env.exists()
    print(f"  {'✅' if env_ok else '⚠️ '} .env file: {'พบแล้ว' if env_ok else 'ยังไม่มี'}")
    if not env_ok:
        print()
        print("  สร้าง .env ก่อนรัน:")
        print()
        print("    Windows:  copy .env.example .env")
        print("    Mac/Linux: cp .env.example .env")

    print()
    line()
    print()

    if missing:
        # ── ยังขาดไฟล์ ──
        print("  🟡 สถานะ: ขาดไฟล์ — ยังรันไม่ได้")
        print()
        print("  วิธีแก้:")
        print("    1. เปิดแชท Claude แนบ SKILL.md")
        print("    2. พิมพ์: 'ขอไฟล์ที่หายไป'")
        print("    3. download และวางในโฟลเดอร์ที่ถูกต้อง")
        print("    4. รัน: python sync_check.py")
    else:
        # ── ครบ — แสดงคำสั่งทั้งหมด ──
        print("  🟢 สถานะ: ครบทุกไฟล์")
        print()
        line("─")
        print("  📦 ขั้นตอนที่ 1 — ติดตั้ง (ทำครั้งเดียว)")
        line("─")
        print()
        print("    pip install -r app/requirements.txt")
        print()
        line("─")
        print("  ⚙️  ขั้นตอนที่ 2 — ตั้งค่า .env (ถ้ายังไม่ได้ทำ)")
        line("─")
        print()
        print("    Windows:   copy .env.example .env")
        print("    Mac/Linux: cp .env.example .env")
        print()
        print("    เปิดไฟล์ .env แล้วตรวจสอบ:")
        print("      MOCK_MODE=true   ← ใช้ตอนทดสอบ (ไม่เสีย token)")
        print("      DB_PATH=holding.db")
        print()
        line("─")
        print("  🚀 ขั้นตอนที่ 3 — รันระบบ")
        line("─")
        print()
        print("    python app/main.py")
        print()
        print("    จะเห็นหน้าต่างนี้:")
        print("    ╔══════════════════════════════════════════╗")
        print("    ║  Mode: 🟡 MOCK (no API calls)            ║")
        print("    ╚══════════════════════════════════════════╝")
        print()
        line("─")
        print("  🌐 ขั้นตอนที่ 4 — เปิด Browser")
        line("─")
        print()
        print("    http://localhost:8000/docs      ← API ทั้งหมด")
        print("    http://localhost:8000/          ← สถานะระบบ")
        print("    http://localhost:8000/health    ← health check")
        print()
        line("─")
        print("  🧪 ทดสอบ Sandbox (ฟรี ไม่เสีย token)")
        line("─")
        print()
        print("    เปิด http://localhost:8000/docs")
        print("    กด POST /v1/sandbox/classify → Try it out")
        print("    ใส่ข้อมูลนี้แล้วกด Execute:")
        print()
        print('    {')
        print('      "client_id": "test-agent-001",')
        print('      "destination_country": "TH",')
        print('      "items": [')
        print('        {')
        print('          "description": "Portable laptop computer",')
        print('          "origin_country": "CN",')
        print('          "unit_price": 800,')
        print('          "quantity": 5')
        print('        }')
        print('      ]')
        print('    }')
        print()
        line("─")
        print("  📊 ดูสถานะองค์กรจาก AI CEO")
        line("─")
        print()
        print("    GET  http://localhost:8000/v1/ceo/briefing")
        print("    GET  http://localhost:8000/v1/ceo/org-chart")
        print()
        print("    หรือส่งคำสั่งภาษาไทยให้ AI CEO:")
        print("    POST http://localhost:8000/v1/ceo/command")
        print('    { "command": "สรุปสถานะทั้งหมด" }')
        print()
        line("─")
        print("  🔄 เมื่อต้องการ Real Mode (เสีย token)")
        line("─")
        print()
        print("    เปิดไฟล์ .env แก้บรรทัดนี้:")
        print("      MOCK_MODE=false")
        print("      ANTHROPIC_API_KEY=sk-ant-xxxxxxx")
        print()
        print("    แล้วรันใหม่:")
        print("      python app/main.py")
        print()

    line()
    print()
    return len(missing) == 0


if __name__ == "__main__":
    base = sys.argv[1] if len(sys.argv) > 1 else "."
    ok = check(base)
    sys.exit(0 if ok else 1)
