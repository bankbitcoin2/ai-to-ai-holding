"""
migrate_v1_to_v2.py
เพิ่ม columns ที่ขาดใน DB (รันครั้งเดียว)

วางที่: e:\ส่วนตัว2\Ai_to_Ai_CEO\AI_TO_AI_HOLDING\migrate_v1_to_v2.py

วิธีรัน:
    cd e:\ส่วนตัว2\Ai_to_Ai_CEO\AI_TO_AI_HOLDING
    py migrate_v1_to_v2.py
"""
import sqlite3
import sys
import os

DB_PATH = os.getenv("DB_PATH", "holding.db")

MIGRATIONS = [
    # compliance_notes ใช้เก็บ halal + glossary hint แทนการสร้าง column ใหม่
    # (schema เดิมมี compliance_notes แล้ว — ไม่ต้องเพิ่ม)
    # เพิ่ม evidence_hash ถ้ายังไม่มี
    "ALTER TABLE customs_invoice_items ADD COLUMN evidence_hash TEXT",
]

def migrate(db_path: str):
    print(f"\n🔧 AI TO AI HOLDING — Schema Migration")
    print(f"   DB: {db_path}\n")

    if not os.path.exists(db_path):
        print(f"   ⚠️  ไม่พบ {db_path}")
        print("   รัน py main.py ก่อนเพื่อสร้าง DB แล้วค่อยรัน migrate อีกครั้ง")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    passed = skipped = failed = 0

    for sql in MIGRATIONS:
        col = sql.split("ADD COLUMN")[1].strip().split()[0]
        try:
            conn.execute(sql)
            conn.commit()
            print(f"   ✅ เพิ่ม column: {col}")
            passed += 1
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e):
                print(f"   ⏭️  {col} มีอยู่แล้ว")
                skipped += 1
            else:
                print(f"   ❌ ERROR: {e}")
                failed += 1

    conn.close()
    print(f"\n   สรุป: เพิ่ม {passed} | ข้าม {skipped} | error {failed}")
    print("   ✅ พร้อมใช้งาน\n" if not failed else "   ❌ มี error\n")

if __name__ == "__main__":
    migrate(sys.argv[1] if len(sys.argv) > 1 else DB_PATH)
