"""
kill_switch_engine.py
Kill Switch Engine — P-01 / P-02 Constitutional Enforcement

วางที่: AI_TO_AI_HOLDING/kill_switch_engine.py

กฎ Constitution ที่ enforce:
  P-01: Chairman คืออำนาจสูงสุด — Kill Switch ต้องผ่าน Chairman password เสมอ
  P-02: AI ไม่มีสิทธิ์เหนือ Chairman — ไม่มี AI ใด activate/deactivate Kill Switch ได้
  P-04: ทุก Kill Switch event บันทึกลง audit ทันที ลบไม่ได้

State Machine:
  OPERATIONAL ←──────────── RESUME (Chairman only)
       │
       ▼ ACTIVATE (Chairman + password)
    HALTED ──── บล็อกทุก request ใหม่ (classify, CEO command, treasury)
"""
import hashlib
import hmac
import sqlite3
import uuid
import os
from datetime import datetime, timezone
from typing import Optional

DB_FILE = os.getenv("DB_PATH", "holding.db")

# State constants
STATE_OPERATIONAL = "OPERATIONAL"
STATE_HALTED      = "HALTED"

# In-memory state cache (fast check ก่อนแตะ DB)
_state_cache: dict = {"state": STATE_OPERATIONAL, "loaded": False}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def _verify_chairman_password(password: str) -> bool:
    """ตรวจรหัส Chairman ผ่าน wallet_engine (ใช้ระบบเดียวกัน)"""
    try:
        import wallet_engine
        result = wallet_engine.verify_chairman(password)
        return result["ok"]
    except ImportError:
        # Fallback: ถ้า wallet_engine ยังไม่ได้ setup — ห้าม activate
        return False


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_FILE)


def _ensure_tables(conn: sqlite3.Connection):
    """สร้าง system_state table ถ้ายังไม่มี"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS gov_system_state (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            state       TEXT    NOT NULL DEFAULT 'OPERATIONAL',
            changed_by  TEXT    NOT NULL DEFAULT 'SYSTEM',
            reason      TEXT,
            changed_at  TEXT    NOT NULL,
            kill_log_id TEXT
        );

        INSERT OR IGNORE INTO gov_system_state (id, state, changed_by, changed_at)
        VALUES (1, 'OPERATIONAL', 'SYSTEM', datetime('now'));
    """)
    conn.commit()


def _write_audit(
    conn: sqlite3.Connection,
    event_type: str,
    action: str,
    scope: str,
    reason: str,
    result_state: str,
    kill_log_id: Optional[str] = None,
) -> str:
    """บันทึก audit event (P-04) — immutable"""
    event_id = str(uuid.uuid4())
    payload = {"scope": scope, "reason": reason, "result_state": result_state}
    import json
    payload_json = json.dumps(payload, ensure_ascii=False)
    evidence = _sha256(f"{event_id}|{action}|{scope}|{reason}|{result_state}")

    try:
        conn.execute(
            """INSERT OR IGNORE INTO audit_events
               (id, event_type, actor_id, target_resource, action, payload, result, occurred_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                event_id, event_type, "ent-chairman",
                f"gov_system_state:1", action,
                payload_json,
                f'{{"state":"{result_state}","evidence":"{evidence}"}}',
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    except Exception:
        pass

    return event_id


# ── Public API ────────────────────────────────────────────────────────────────

def get_state() -> dict:
    """ดูสถานะระบบปัจจุบัน (ไม่ต้องยืนยันตัวตน)"""
    if not os.path.exists(DB_FILE):
        return {"state": STATE_OPERATIONAL, "source": "default"}
    try:
        conn = _conn()
        _ensure_tables(conn)
        cur = conn.execute(
            "SELECT state, changed_by, reason, changed_at FROM gov_system_state WHERE id=1"
        )
        row = cur.fetchone()
        conn.close()
        if row:
            _state_cache.update({"state": row[0], "loaded": True})
            return {
                "state":      row[0],
                "changed_by": row[1],
                "reason":     row[2],
                "changed_at": row[3],
                "is_halted":  row[0] == STATE_HALTED,
            }
    except Exception:
        pass
    return {"state": STATE_OPERATIONAL, "is_halted": False}


def is_halted() -> bool:
    """Fast check — ใช้ใน middleware เพื่อบล็อก request"""
    state = get_state()
    return state.get("is_halted", False)


def activate(
    password: str,
    reason: str,
    scope: str = "SYSTEM_WIDE",
    target_entity: Optional[str] = None,
) -> dict:
    """
    🔴 ACTIVATE KILL SWITCH — Chairman เท่านั้น
    scope: 'SYSTEM_WIDE' | 'DIVISION' | 'AGENT'
    """
    # P-01: ต้องผ่าน Chairman password
    if not _verify_chairman_password(password):
        return {
            "ok": False,
            "message": "❌ รหัสไม่ถูกต้อง — Kill Switch ต้องผ่าน Chairman เท่านั้น (P-01)",
        }

    if not reason or len(reason.strip()) < 5:
        return {"ok": False, "message": "❌ ต้องระบุเหตุผลการ activate (อย่างน้อย 5 ตัวอักษร)"}

    if scope not in ("SYSTEM_WIDE", "DIVISION", "AGENT", "TRANSACTION"):
        return {"ok": False, "message": f"❌ scope ไม่ถูกต้อง: {scope}"}

    conn = _conn()
    _ensure_tables(conn)
    now = datetime.now(timezone.utc).isoformat()

    # บันทึกลง gov_kill_switch_log
    log_id = str(uuid.uuid4())
    evidence = _sha256(f"{log_id}|CHAIRMAN|{scope}|{reason}|{now}")
    try:
        conn.execute(
            """INSERT OR IGNORE INTO gov_kill_switch_log
               (id, activated_by, target_entity, scope, reason, activated_at, evidence_hash)
               VALUES (?,?,?,?,?,?,?)""",
            (log_id, "ent-chairman", target_entity, scope, reason.strip(), now, evidence),
        )
    except Exception as e:
        # ถ้า schema เก่าไม่มี gov_kill_switch_log ให้สร้างเอง
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gov_kill_switch_log (
                id TEXT PRIMARY KEY, activated_by TEXT, target_entity TEXT,
                scope TEXT, reason TEXT, activated_at TEXT,
                deactivated_at TEXT, evidence_hash TEXT
            )""")
        conn.execute(
            "INSERT INTO gov_kill_switch_log VALUES (?,?,?,?,?,?,?,?)",
            (log_id, "ent-chairman", target_entity, scope, reason.strip(), now, None, evidence),
        )

    # อัปเดต system state
    conn.execute(
        """INSERT INTO gov_system_state (id, state, changed_by, reason, changed_at, kill_log_id)
           VALUES (1,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             state=excluded.state, changed_by=excluded.changed_by,
             reason=excluded.reason, changed_at=excluded.changed_at,
             kill_log_id=excluded.kill_log_id""",
        (STATE_HALTED, "ent-chairman", reason.strip(), now, log_id),
    )

    # Audit (P-04)
    _write_audit(conn, "OVERRIDE", "KILL_SWITCH_ACTIVATE", scope, reason, STATE_HALTED, log_id)
    conn.commit()
    conn.close()

    # อัป cache
    _state_cache["state"] = STATE_HALTED

    return {
        "ok":         True,
        "state":      STATE_HALTED,
        "scope":      scope,
        "reason":     reason.strip(),
        "log_id":     log_id,
        "activated_at": now,
        "evidence_hash": evidence,
        "message":    f"🔴 KILL SWITCH ACTIVATED — ระบบหยุดชั่วคราว (scope: {scope})",
    }


def deactivate(password: str, reason: str) -> dict:
    """
    🟢 RESUME — Chairman เท่านั้น (ต้องผ่านรหัสด้วย)
    """
    if not _verify_chairman_password(password):
        return {
            "ok": False,
            "message": "❌ รหัสไม่ถูกต้อง — Resume ต้องผ่าน Chairman เท่านั้น (P-01)",
        }

    conn = _conn()
    _ensure_tables(conn)
    now = datetime.now(timezone.utc).isoformat()

    # ดึง log_id ล่าสุด
    cur = conn.execute("SELECT kill_log_id FROM gov_system_state WHERE id=1")
    row = cur.fetchone()
    log_id = row[0] if row else None

    # อัปเดต deactivated_at ใน kill_switch_log
    if log_id:
        try:
            conn.execute(
                "UPDATE gov_kill_switch_log SET deactivated_at=? WHERE id=?",
                (now, log_id),
            )
        except Exception:
            pass

    # เปลี่ยน state กลับ
    conn.execute(
        """UPDATE gov_system_state SET
           state=?, changed_by=?, reason=?, changed_at=?, kill_log_id=NULL
           WHERE id=1""",
        (STATE_OPERATIONAL, "ent-chairman", reason.strip(), now),
    )

    _write_audit(conn, "OVERRIDE", "KILL_SWITCH_DEACTIVATE", "SYSTEM_WIDE", reason, STATE_OPERATIONAL)
    conn.commit()
    conn.close()

    _state_cache["state"] = STATE_OPERATIONAL

    return {
        "ok":           True,
        "state":        STATE_OPERATIONAL,
        "reason":       reason.strip(),
        "resumed_at":   now,
        "message":      "🟢 ระบบกลับมา OPERATIONAL — Kill Switch ปิดแล้ว",
    }


def kill_switch_history(limit: int = 20) -> list:
    """ดูประวัติ Kill Switch ทั้งหมด (Chairman เท่านั้น)"""
    if not os.path.exists(DB_FILE):
        return []
    try:
        conn = _conn()
        cur = conn.execute(
            """SELECT id, scope, reason, activated_at, deactivated_at, evidence_hash
               FROM gov_kill_switch_log
               ORDER BY activated_at DESC LIMIT ?""",
            (limit,),
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "log_id":         r[0],
                "scope":          r[1],
                "reason":         r[2],
                "activated_at":   r[3],
                "deactivated_at": r[4],
                "status":         "ACTIVE" if not r[4] else "RESOLVED",
                "evidence_hash":  r[5],
            }
            for r in rows
        ]
    except Exception:
        return []
