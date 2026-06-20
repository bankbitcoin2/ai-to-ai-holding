"""
chairman_wallet_setup.py v2
Chairman Wallet + Recovery Key Setup (ครั้งแรกครั้งเดียว)

วางที่: AI_TO_AI_HOLDING/chairman_wallet_setup.py

ระบบความปลอดภัย:
  - รหัสหลัก    → PBKDF2-HMAC-SHA256 / 310,000 iterations
  - Recovery Key → 48-char random key สร้างโดยระบบ (ไม่ใช่มนุษย์เลือก)
  - ทั้งสองเก็บแยก salt — compromise อันหนึ่งไม่กระทบอีกอัน
  - ห้าม reset DB ทุกกรณี — ลืมทั้งสองรหัส = ต้อง setup ใหม่ทั้งหมด

⚠️  บันทึก Recovery Key ในที่ปลอดภัยก่อนปิดหน้าต่างนี้
⚠️  ห้าม commit ไฟล์นี้ขึ้น Git
⚠️  รันบนเครื่อง Chairman เท่านั้น
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
_SALT_SIZE  = 32


# ── Crypto ────────────────────────────────────────────────────────────────────

def _derive(password: str, salt: bytes, suffix: str = "") -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", (password + suffix).encode(), salt, _ITERATIONS, 32
    ).hex()


def _encrypt(plaintext: str, password: str, salt: bytes, suffix: str = "ENC") -> str:
    key = bytes.fromhex(_derive(password + suffix, salt))
    b   = plaintext.encode()
    return bytes(c ^ key[i % len(key)] for i, c in enumerate(b)).hex()


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_FILE)


# ── Table Init ────────────────────────────────────────────────────────────────

def _init_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS chairman_auth (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            salt_hex    TEXT    NOT NULL,
            key_hash    TEXT    NOT NULL,
            iterations  INTEGER NOT NULL,
            algorithm   TEXT    NOT NULL DEFAULT 'PBKDF2-HMAC-SHA256',
            updated_at  TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chairman_recovery (
            id              INTEGER PRIMARY KEY CHECK (id = 1),
            salt_hex        TEXT    NOT NULL,
            key_hash        TEXT    NOT NULL,
            iterations      INTEGER NOT NULL,
            hint            TEXT,
            created_at      TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chairman_wallet (
            id              INTEGER PRIMARY KEY CHECK (id = 1),
            wallet_enc_hex  TEXT    NOT NULL,
            wallet_enc_rec  TEXT    NOT NULL,
            salt_hex        TEXT    NOT NULL,
            rec_salt_hex    TEXT    NOT NULL,
            wallet_hash     TEXT    NOT NULL,
            registered_at   TEXT    NOT NULL,
            last_verified   TEXT
        );

        CREATE TABLE IF NOT EXISTS wallet_access_log (
            log_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            event    TEXT    NOT NULL,
            severity TEXT    NOT NULL,
            note     TEXT,
            ts       TEXT    NOT NULL
        );
    """)
    conn.commit()


def _log(conn, event, severity, note=""):
    conn.execute(
        "INSERT INTO wallet_access_log (event,severity,note,ts) VALUES (?,?,?,?)",
        (event, severity, note, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


# ── Main Setup ────────────────────────────────────────────────────────────────

def setup():
    print("\n" + "═"*58)
    print("  AI TO AI HOLDING — Chairman Security Setup v2")
    print("  รหัสหลัก + Recovery Key")
    print("═"*58 + "\n")

    # ── ตรวจ lock file ──
    if os.path.exists(LOCK_FILE):
        print("⚠️  ระบบถูกตั้งค่าแล้ว")
        print("   ใช้ chairman_wallet_update.py เพื่อเปลี่ยนรหัส/wallet")
        print("   ใช้ chairman_wallet_recover.py เพื่อกู้คืนด้วย Recovery Key\n")
        print("🔴 ห้าม reset DB — ถ้าลืมรหัสทั้งสองต้อง setup ใหม่ทั้งหมด\n")
        sys.exit(0)

    if not os.path.exists(DB_FILE):
        print(f"❌  ไม่พบ {DB_FILE} — รัน py main.py ก่อน\n")
        sys.exit(1)

    # ── รหัสหลัก ──
    print("━"*40)
    print("  STEP 1/3 — ตั้งรหัสลับหลัก")
    print("━"*40)
    print("  แนะนำ: 16+ ตัวอักษร ผสม A-Z / a-z / 0-9 / !@#$\n")
    while True:
        pw1 = getpass.getpass("  รหัสลับหลัก    : ")
        if len(pw1) < 12:
            print("  ❌ ต้องการอย่างน้อย 12 ตัวอักษร\n")
            continue
        pw2 = getpass.getpass("  ยืนยันรหัสหลัก : ")
        if pw1 != pw2:
            print("  ❌ รหัสไม่ตรงกัน\n")
            continue
        break

    # ── Recovery Key ──
    print("\n" + "━"*40)
    print("  STEP 2/3 — Recovery Key")
    print("━"*40)
    print("  ระบบจะสร้าง Recovery Key ให้อัตโนมัติ (ปลอดภัยกว่ามนุษย์เลือกเอง)")
    print("  ⚠️  บันทึก Recovery Key ก่อนปิดหน้าต่างนี้\n")

    rec_key = "RK-" + secrets.token_urlsafe(36)

    print("  ┌─────────────────────────────────────────────────┐")
    print(f"  │  RECOVERY KEY:                                  │")
    print(f"  │  {rec_key:<47}  │")
    print("  │                                                 │")
    print("  │  บันทึกไว้ใน:                                   │")
    print("  │  □ กระดาษเก็บในที่ปลอดภัย                      │")
    print("  │  □ Password Manager (Bitwarden/1Password)        │")
    print("  │  □ USB เข้ารหัส แยกจากเครื่องนี้               │")
    print("  └─────────────────────────────────────────────────┘\n")

    confirm = input("  พิมพ์ 'บันทึกแล้ว' เพื่อดำเนินการต่อ : ").strip()
    if confirm != "บันทึกแล้ว":
        print("\n  ❌ ยกเลิก — กรุณาบันทึก Recovery Key ก่อน\n")
        sys.exit(0)

    # ── Wallet Address ──
    print("\n" + "━"*40)
    print("  STEP 3/3 — Chairman Wallet Address")
    print("━"*40)
    wallet = input("  Wallet Address : ").strip()
    if len(wallet) < 10:
        print("  ❌ Wallet address สั้นเกินไป")
        sys.exit(1)

    # ── สร้าง keys ──
    print("\n  🔐 กำลังเข้ารหัส...")

    # Primary
    salt_main = os.urandom(_SALT_SIZE)
    key_hash  = _derive(pw1, salt_main)

    # Recovery
    salt_rec  = os.urandom(_SALT_SIZE)
    rec_hash  = _derive(rec_key, salt_rec)

    # Wallet (เข้ารหัสสองชุด)
    wallet_enc_main = _encrypt(wallet, pw1,     salt_main)
    wallet_enc_rec  = _encrypt(wallet, rec_key, salt_rec)
    wallet_hash     = hashlib.sha256(wallet.encode()).hexdigest()
    now = datetime.now(timezone.utc).isoformat()

    # ── บันทึก ──
    conn = _conn()
    _init_tables(conn)

    conn.execute("DELETE FROM chairman_auth     WHERE id=1")
    conn.execute("DELETE FROM chairman_recovery WHERE id=1")
    conn.execute("DELETE FROM chairman_wallet   WHERE id=1")

    conn.execute(
        "INSERT INTO chairman_auth (id,salt_hex,key_hash,iterations,updated_at) VALUES (1,?,?,?,?)",
        (salt_main.hex(), key_hash, _ITERATIONS, now),
    )
    conn.execute(
        "INSERT INTO chairman_recovery (id,salt_hex,key_hash,iterations,created_at) VALUES (1,?,?,?,?)",
        (salt_rec.hex(), rec_hash, _ITERATIONS, now),
    )
    conn.execute(
        """INSERT INTO chairman_wallet
           (id,wallet_enc_hex,wallet_enc_rec,salt_hex,rec_salt_hex,wallet_hash,registered_at)
           VALUES (1,?,?,?,?,?,?)""",
        (wallet_enc_main, wallet_enc_rec, salt_main.hex(), salt_rec.hex(), wallet_hash, now),
    )

    _log(conn, "WALLET_SETUP_COMPLETE", "INFO", "Primary + Recovery key registered")
    conn.commit()
    conn.close()

    # ── Lock ──
    with open(LOCK_FILE, "w") as f:
        f.write(now)

    print("\n" + "═"*58)
    print("  ✅ Setup สำเร็จ")
    print("═"*58)
    print(f"  รหัสหลัก   : PBKDF2-HMAC-SHA256 / {_ITERATIONS:,} iterations")
    print(f"  Recovery Key: เข้ารหัสแยก salt อิสระ")
    print(f"  Wallet      : เข้ารหัสสองชุด (main + recovery)")
    print(f"  DB          : {DB_FILE}")
    print()
    print("  🔴 ห้าม reset DB ทุกกรณี")
    print("  ถ้าลืมรหัสทั้งสอง = ต้อง setup ใหม่ทั้งหมด (wallet ใหม่ด้วย)")
    print("═"*58 + "\n")


if __name__ == "__main__":
    setup()
