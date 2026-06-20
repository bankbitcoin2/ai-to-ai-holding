"""
wallet_engine.py
Chairman Wallet Authentication Engine

วางที่: AI_TO_AI_HOLDING/wallet_engine.py

หน้าที่:
  - ยืนยันตัวตน Chairman ก่อนทุกการเปลี่ยน wallet
  - คืน wallet address ให้ treasury_service เพื่อ route เงิน
  - บันทึกทุก access ลง audit log (P-04)
  - ไม่มี AI ใดเรียก verify_chairman() ได้โดยตรง — ผ่าน API endpoint เท่านั้น

ไม่มี:
  - hardcoded password
  - plaintext wallet
  - endpoint ที่เปิด wallet address ออก public
"""
import hashlib
import hmac
import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional


DB_FILE = os.getenv("DB_PATH", "holding.db")
_MAX_ATTEMPTS = 5          # ล็อกหลังผิดติดต่อกัน 5 ครั้ง
_LOCK_MINUTES = 30         # ล็อกนาน 30 นาที
_ITERATIONS   = 310_000


# ── Crypto ────────────────────────────────────────────────────────────────────

def _derive_key(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS, 32).hex()


def _constant_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def _decrypt_wallet(enc_hex: str, password: str, salt: bytes) -> str:
    key = bytes.fromhex(_derive_key(password + "WALLET_ENC", salt))
    enc = bytes.fromhex(enc_hex)
    return bytes(e ^ key[i % len(key)] for i, e in enumerate(enc)).decode()


# ── Audit Log ─────────────────────────────────────────────────────────────────

def _log(conn: sqlite3.Connection, event: str, severity: str, note: str = ""):
    try:
        conn.execute(
            "INSERT INTO wallet_access_log (event, severity, note, ts) VALUES (?,?,?,?)",
            (event, severity, note, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    except Exception:
        pass  # log ไม่ควรทำให้ระบบพัง


# ── Rate Limiting (in-process, SQLite-backed) ─────────────────────────────────

def _get_fail_count(conn: sqlite3.Connection) -> tuple[int, Optional[str]]:
    """คืน (fail_count_ภายใน_30_นาที, timestamp_ครั้งล่าสุด)"""
    try:
        cur = conn.execute(
            """SELECT COUNT(*), MAX(ts) FROM wallet_access_log
               WHERE event='AUTH_FAIL'
               AND ts > datetime('now', ?)""",
            (f"-{_LOCK_MINUTES} minutes",),
        )
        row = cur.fetchone()
        return (row[0] or 0, row[1])
    except Exception:
        return (0, None)


# ── Public API ────────────────────────────────────────────────────────────────

def is_initialized() -> bool:
    """ตรวจว่า Chairman ได้ setup wallet แล้วหรือยัง"""
    if not os.path.exists(DB_FILE):
        return False
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.execute("SELECT COUNT(*) FROM chairman_auth WHERE id=1")
        count = cur.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


def verify_chairman(password: str) -> dict:
    """
    ยืนยันตัวตน Chairman — คืน {ok, wallet, message}
    wallet จะถูก return เฉพาะเมื่อ ok=True เท่านั้น
    ไม่มี API endpoint ไหนเปิด wallet ออก public ได้
    """
    if not os.path.exists(DB_FILE):
        return {"ok": False, "wallet": None, "message": "DB not found"}

    conn = sqlite3.connect(DB_FILE)

    try:
        # ── ตรวจ rate limit ──
        fails, last_fail = _get_fail_count(conn)
        if fails >= _MAX_ATTEMPTS:
            _log(conn, "AUTH_LOCKED", "CRITICAL",
                 f"Too many failed attempts ({fails}). Locked {_LOCK_MINUTES} min.")
            return {
                "ok": False,
                "wallet": None,
                "message": f"🔒 ล็อกชั่วคราว — ผิดติดต่อกัน {fails} ครั้ง รอ {_LOCK_MINUTES} นาที",
            }

        # ── ดึง auth record ──
        cur = conn.execute(
            "SELECT salt_hex, key_hash, iterations FROM chairman_auth WHERE id=1"
        )
        auth = cur.fetchone()
        if not auth:
            return {"ok": False, "wallet": None, "message": "ยังไม่ได้ setup — รัน chairman_wallet_setup.py ก่อน"}

        salt_hex, stored_hash, iterations = auth
        salt = bytes.fromhex(salt_hex)

        # ── derive และ compare (timing-safe) ──
        input_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt, iterations, 32
        ).hex()

        if not _constant_compare(input_hash, stored_hash):
            _log(conn, "AUTH_FAIL", "HIGH",
                 f"Wrong password attempt ({fails+1}/{_MAX_ATTEMPTS})")
            remaining = _MAX_ATTEMPTS - fails - 1
            return {
                "ok": False,
                "wallet": None,
                "message": f"❌ รหัสไม่ถูกต้อง (เหลือ {remaining} ครั้งก่อนล็อก)",
            }

        # ── ผ่านแล้ว — ถอดรหัส wallet ──
        cur2 = conn.execute(
            "SELECT wallet_enc_hex, salt_hex FROM chairman_wallet WHERE id=1"
        )
        w = cur2.fetchone()
        if not w:
            return {"ok": False, "wallet": None, "message": "Wallet ยังไม่ได้ลงทะเบียน"}

        wallet = _decrypt_wallet(w[0], password, bytes.fromhex(w[1]))

        # ── update last_verified ──
        conn.execute(
            "UPDATE chairman_wallet SET last_verified=? WHERE id=1",
            (datetime.now(timezone.utc).isoformat(),),
        )
        _log(conn, "AUTH_SUCCESS", "INFO", "Chairman verified — wallet decrypted")

        return {"ok": True, "wallet": wallet, "message": "✅ ยืนยันตัวตนสำเร็จ"}

    except Exception as e:
        _log(conn, "AUTH_ERROR", "CRITICAL", str(e))
        return {"ok": False, "wallet": None, "message": f"System error: {e}"}
    finally:
        conn.close()


def update_wallet(password: str, new_wallet: str) -> dict:
    """
    เปลี่ยน Wallet Address — ต้องผ่าน verify_chairman ก่อนเสมอ
    Chairman เท่านั้นที่เรียกได้ผ่าน /v1/treasury/chairman/wallet endpoint
    """
    verify = verify_chairman(password)
    if not verify["ok"]:
        return verify

    if not os.path.exists(DB_FILE):
        return {"ok": False, "message": "DB not found"}

    conn = sqlite3.connect(DB_FILE)
    try:
        cur = conn.execute("SELECT salt_hex FROM chairman_auth WHERE id=1")
        row = cur.fetchone()
        salt = bytes.fromhex(row[0])

        # เข้ารหัส wallet ใหม่
        key = bytes.fromhex(_derive_key(password + "WALLET_ENC", salt))
        wallet_bytes = new_wallet.encode()
        enc = bytes(w ^ key[i % len(key)] for i, w in enumerate(wallet_bytes))
        enc_hex = enc.hex()
        wallet_hash = hashlib.sha256(new_wallet.encode()).hexdigest()
        now = datetime.now(timezone.utc).isoformat()

        conn.execute(
            "UPDATE chairman_wallet SET wallet_enc_hex=?, wallet_hash=?, registered_at=?, last_verified=? WHERE id=1",
            (enc_hex, wallet_hash, now, now),
        )
        _log(conn, "WALLET_UPDATED", "INFO", "Chairman wallet address updated")
        conn.commit()
        return {"ok": True, "message": "✅ อัปเดต Wallet สำเร็จ"}

    except Exception as e:
        _log(conn, "WALLET_UPDATE_ERROR", "CRITICAL", str(e))
        return {"ok": False, "message": str(e)}
    finally:
        conn.close()


def update_password(old_password: str, new_password: str) -> dict:
    """
    เปลี่ยนรหัสลับ Chairman — ต้องใส่รหัสเก่าถูกต้องก่อน
    """
    verify = verify_chairman(old_password)
    if not verify["ok"]:
        return verify

    if len(new_password) < 12:
        return {"ok": False, "message": "รหัสใหม่ต้องยาวอย่างน้อย 12 ตัวอักษร"}

    conn = sqlite3.connect(DB_FILE)
    try:
        # สร้าง salt ใหม่ + re-encrypt wallet ด้วยรหัสใหม่
        new_salt = os.urandom(32)
        new_salt_hex = new_salt.hex()
        new_key_hash = _derive_key(new_password, new_salt)

        cur = conn.execute("SELECT wallet_enc_hex, salt_hex FROM chairman_wallet WHERE id=1")
        w = cur.fetchone()
        old_salt = bytes.fromhex(w[1])
        wallet_plain = _decrypt_wallet(w[0], old_password, old_salt)

        new_key = bytes.fromhex(_derive_key(new_password + "WALLET_ENC", new_salt))
        wallet_bytes = wallet_plain.encode()
        new_enc = bytes(b ^ new_key[i % len(new_key)] for i, b in enumerate(wallet_bytes)).hex()
        now = datetime.now(timezone.utc).isoformat()

        conn.execute(
            "UPDATE chairman_auth SET salt_hex=?, key_hash=?, iterations=?, updated_at=? WHERE id=1",
            (new_salt_hex, new_key_hash, _ITERATIONS, now),
        )
        conn.execute(
            "UPDATE chairman_wallet SET wallet_enc_hex=?, salt_hex=?, registered_at=? WHERE id=1",
            (new_enc, new_salt_hex, now),
        )
        _log(conn, "PASSWORD_CHANGED", "INFO", "Chairman password updated")
        conn.commit()
        return {"ok": True, "message": "✅ เปลี่ยนรหัสสำเร็จ"}

    except Exception as e:
        return {"ok": False, "message": str(e)}
    finally:
        conn.close()



def verify_by_recovery_key(recovery_key: str) -> dict:
    """
    ยืนยันตัวตนด้วย Recovery Key (ใช้เมื่อลืมรหัสหลัก)
    คืน wallet เฉพาะเมื่อ ok=True — ไม่มี DB reset ทุกกรณี
    """
    if not os.path.exists(DB_FILE):
        return {"ok": False, "wallet": None, "message": "DB not found"}

    conn = sqlite3.connect(DB_FILE)
    try:
        cur = conn.execute(
            "SELECT salt_hex, key_hash, iterations FROM chairman_recovery WHERE id=1"
        )
        rec = cur.fetchone()
        if not rec:
            return {"ok": False, "wallet": None,
                    "message": "ไม่พบ Recovery record — setup ด้วย v2 ก่อน"}

        salt = bytes.fromhex(rec[0])
        input_hash = hashlib.pbkdf2_hmac(
            "sha256", recovery_key.encode(), salt, rec[2], 32
        ).hex()

        if not _constant_compare(input_hash, rec[1]):
            _log(conn, "RECOVERY_FAIL", "CRITICAL", "Wrong Recovery Key")
            return {"ok": False, "wallet": None,
                    "message": "❌ Recovery Key ไม่ถูกต้อง — ไม่มีการ reset DB ทุกกรณี"}

        cur2 = conn.execute(
            "SELECT wallet_enc_rec, rec_salt_hex FROM chairman_wallet WHERE id=1"
        )
        w = cur2.fetchone()
        if not w:
            return {"ok": False, "wallet": None, "message": "Wallet ยังไม่ได้ลงทะเบียน"}

        wallet = _decrypt_wallet(w[0], recovery_key, bytes.fromhex(w[1]))
        _log(conn, "RECOVERY_SUCCESS", "INFO", "Wallet accessed via Recovery Key")

        return {"ok": True, "wallet": wallet, "message": "✅ Recovery Key ถูกต้อง"}

    except Exception as e:
        return {"ok": False, "wallet": None, "message": str(e)}
    finally:
        conn.close()


def wallet_status() -> dict:
    """สถานะ wallet สำหรับ CEO briefing — ไม่เปิดเผย address"""
    if not is_initialized():
        return {"initialized": False, "status": "NOT_SETUP"}
    conn = sqlite3.connect(DB_FILE)
    try:
        cur = conn.execute(
            "SELECT registered_at, last_verified FROM chairman_wallet WHERE id=1"
        )
        row = cur.fetchone()
        fails, _ = _get_fail_count(conn)
        locked = fails >= _MAX_ATTEMPTS
        return {
            "initialized": True,
            "status": "LOCKED" if locked else "ACTIVE",
            "registered_at": row[0] if row else None,
            "last_verified": row[1] if row else None,
            "recent_fail_attempts": fails,
            "algorithm": "PBKDF2-HMAC-SHA256",
            "iterations": _ITERATIONS,
            "wallet_address": "REDACTED",
        }
    finally:
        conn.close()
