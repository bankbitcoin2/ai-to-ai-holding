"""
chairman_wallet_recover.py
กู้คืนด้วย Recovery Key — ไม่มีการ reset DB ทุกกรณี

วางที่: AI_TO_AI_HOLDING/chairman_wallet_recover.py

ใช้เมื่อ: ลืมรหัสหลัก แต่มี Recovery Key
ทำได้:   ตั้งรหัสหลักใหม่ + เปลี่ยน wallet ได้ (optional)
ห้าม:    ไม่มีการลบ DB / ไม่มีการ bypass auth

วิธีรัน:
    cd e:\\ส่วนตัว2\\Ai_to_Ai_CEO\\AI_TO_AI_HOLDING
    py chairman_wallet_recover.py
"""
import hashlib
import hmac
import os
import secrets
import sqlite3
import getpass
import sys
from datetime import datetime, timezone

DB_FILE     = os.getenv("DB_PATH", "holding.db")
LOCK_FILE   = ".wallet_initialized"
_ITERATIONS = 310_000


def _derive(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, _ITERATIONS, 32
    ).hex()


def _constant_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def _encrypt(plaintext: str, password: str, salt: bytes, suffix: str = "ENC") -> str:
    key = bytes.fromhex(_derive(password + suffix, salt))
    b   = plaintext.encode()
    return bytes(c ^ key[i % len(key)] for i, c in enumerate(b)).hex()


def _decrypt(enc_hex: str, password: str, salt: bytes, suffix: str = "ENC") -> str:
    key = bytes.fromhex(_derive(password + suffix, salt))
    enc = bytes.fromhex(enc_hex)
    return bytes(e ^ key[i % len(key)] for i, e in enumerate(enc)).decode()


def _log(conn, event, severity, note=""):
    conn.execute(
        "INSERT INTO wallet_access_log (event,severity,note,ts) VALUES (?,?,?,?)",
        (event, severity, note, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def recover():
    print("\n" + "═"*55)
    print("  AI TO AI HOLDING — Chairman Recovery")
    print("  กู้คืนด้วย Recovery Key")
    print("═"*55 + "\n")
    print("  🔴 ห้าม reset DB ทุกกรณี")
    print("  ถ้าไม่มี Recovery Key — setup ใหม่ทั้งหมดเท่านั้น\n")

    if not os.path.exists(DB_FILE):
        print(f"❌  ไม่พบ {DB_FILE}\n")
        sys.exit(1)

    if not os.path.exists(LOCK_FILE):
        print("❌  ยังไม่มีการ setup — รัน chairman_wallet_setup.py ก่อน\n")
        sys.exit(1)

    conn = sqlite3.connect(DB_FILE)

    # ── ตรวจว่ามี recovery record ──
    try:
        cur = conn.execute("SELECT salt_hex, key_hash, iterations FROM chairman_recovery WHERE id=1")
        rec = cur.fetchone()
    except Exception:
        print("❌  ไม่พบ Recovery record ใน DB\n")
        print("   อาจเป็นเพราะ setup ด้วยระบบเก่า (v1) ที่ยังไม่มี Recovery Key")
        print("   วิธีแก้: รัน chairman_wallet_setup.py ใหม่ทั้งหมด\n")
        conn.close()
        sys.exit(1)

    if not rec:
        print("❌  ไม่พบ Recovery record\n")
        conn.close()
        sys.exit(1)

    # ── รับ Recovery Key ──
    print("━"*40)
    print("  STEP 1/2 — ใส่ Recovery Key")
    print("━"*40)
    rec_key = getpass.getpass("  Recovery Key (RK-...) : ").strip()

    salt_rec  = bytes.fromhex(rec[0])
    stored    = rec[1]
    input_hash = _derive(rec_key, salt_rec)

    if not _constant_compare(input_hash, stored):
        _log(conn, "RECOVERY_FAIL", "CRITICAL", "Wrong Recovery Key")
        print("\n  ❌ Recovery Key ไม่ถูกต้อง")
        print("  ถ้าลืม Recovery Key ด้วย — ต้อง setup ใหม่ทั้งหมด (wallet ใหม่)")
        print("  🔴 ไม่มีการ reset DB ทุกกรณี\n")
        conn.close()
        sys.exit(1)

    print("  ✅ Recovery Key ถูกต้อง\n")

    # ── อ่าน wallet เดิมด้วย recovery key ──
    cur2 = conn.execute(
        "SELECT wallet_enc_rec, rec_salt_hex FROM chairman_wallet WHERE id=1"
    )
    w = cur2.fetchone()
    if w:
        old_wallet = _decrypt(w[0], rec_key, bytes.fromhex(w[1]))
        print(f"  Wallet ปัจจุบัน: {old_wallet[:6]}...{old_wallet[-4:]}")
        change_wallet = input("  ต้องการเปลี่ยน Wallet Address ด้วยหรือไม่? (y/n) : ").strip().lower()
    else:
        change_wallet = "n"
        old_wallet = ""

    # ── ตั้งรหัสหลักใหม่ ──
    print("\n" + "━"*40)
    print("  STEP 2/2 — ตั้งรหัสหลักใหม่")
    print("━"*40)
    while True:
        pw1 = getpass.getpass("  รหัสหลักใหม่    : ")
        if len(pw1) < 12:
            print("  ❌ ต้องการอย่างน้อย 12 ตัวอักษร\n")
            continue
        pw2 = getpass.getpass("  ยืนยันรหัสหลัก : ")
        if pw1 != pw2:
            print("  ❌ รหัสไม่ตรงกัน\n")
            continue
        break

    # ── Wallet ใหม่ (ถ้าต้องการ) ──
    if change_wallet == "y":
        new_wallet = input("  Wallet Address ใหม่ : ").strip()
        if len(new_wallet) < 10:
            print("  ❌ Wallet address สั้นเกินไป")
            conn.close()
            sys.exit(1)
    else:
        new_wallet = old_wallet

    # ── Generate new Recovery Key ──
    print("\n  🔐 สร้าง Recovery Key ใหม่...")
    new_rec_key = "RK-" + secrets.token_urlsafe(36)

    print("\n  ┌─────────────────────────────────────────────────┐")
    print(f"  │  RECOVERY KEY ใหม่:                             │")
    print(f"  │  {new_rec_key:<47}  │")
    print("  │                                                 │")
    print("  │  ⚠️  บันทึกไว้ก่อนปิดหน้าต่างนี้               │")
    print("  └─────────────────────────────────────────────────┘\n")

    confirm = input("  พิมพ์ 'บันทึกแล้ว' เพื่อดำเนินการต่อ : ").strip()
    if confirm != "บันทึกแล้ว":
        print("\n  ❌ ยกเลิก — กรุณาบันทึก Recovery Key ก่อน\n")
        conn.close()
        sys.exit(0)

    # ── อัปเดต DB ──
    import os as _os
    new_salt_main = _os.urandom(32)
    new_salt_rec  = _os.urandom(32)
    now = datetime.now(timezone.utc).isoformat()

    new_key_hash  = _derive(pw1, new_salt_main)
    new_rec_hash  = _derive(new_rec_key, new_salt_rec)
    new_wallet_enc_main = _encrypt(new_wallet, pw1,          new_salt_main)
    new_wallet_enc_rec  = _encrypt(new_wallet, new_rec_key,  new_salt_rec)
    new_wallet_hash     = hashlib.sha256(new_wallet.encode()).hexdigest()

    conn.execute(
        "UPDATE chairman_auth SET salt_hex=?, key_hash=?, iterations=?, updated_at=? WHERE id=1",
        (new_salt_main.hex(), new_key_hash, _ITERATIONS, now),
    )
    conn.execute(
        "UPDATE chairman_recovery SET salt_hex=?, key_hash=?, iterations=?, created_at=? WHERE id=1",
        (new_salt_rec.hex(), new_rec_hash, _ITERATIONS, now),
    )
    conn.execute(
        """UPDATE chairman_wallet SET
           wallet_enc_hex=?, wallet_enc_rec=?, salt_hex=?, rec_salt_hex=?,
           wallet_hash=?, registered_at=? WHERE id=1""",
        (new_wallet_enc_main, new_wallet_enc_rec,
         new_salt_main.hex(), new_salt_rec.hex(),
         new_wallet_hash, now),
    )

    _log(conn, "RECOVERY_SUCCESS", "INFO", "Password reset via Recovery Key — new RK generated")
    conn.commit()
    conn.close()

    print("\n" + "═"*55)
    print("  ✅ กู้คืนสำเร็จ")
    print("═"*55)
    print("  รหัสหลักใหม่  : อัปเดตแล้ว")
    print("  Recovery Key  : สร้างใหม่แล้ว (Key เก่าใช้ไม่ได้อีก)")
    print(f"  Wallet        : {'อัปเดต' if change_wallet == 'y' else 'คงเดิม'}")
    print("  🔴 ห้าม reset DB ทุกกรณี\n")


if __name__ == "__main__":
    recover()
