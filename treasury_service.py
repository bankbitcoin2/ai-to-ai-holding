"""
services/treasury_service.py
Treasury Pipeline — P-03
ทุก net revenue → auto-split real-time: 60% Corporate / 40% Chairman
ไม่มี AI ใดอ่านหรืออนุมัติ CHAIRMAN_PRIVATE_WALLET ได้
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional
import aiosqlite

from audit import log_event

TREASURY_OFFICE_ID = "ent-office-treasury"
CORPORATE_RESERVE_WALLET = "wallet://corporate-reserve"
CHAIRMAN_PRIVATE_WALLET = "wallet://CHAIRMAN_PRIVATE"  # write-only

SPLIT_RATIOS = {
    "CORPORATE_RESERVE": 0.60,
    "CHAIRMAN_PRIVATE":  0.40,
}

ENERGY_COST_PER_CALL = 0.02  # USD ต่อ API call (placeholder)


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


async def settle_transaction(
    db: aiosqlite.Connection,
    *,
    source_type: str,           # 'CUSTOMS_GATEWAY' | 'KAAS' | 'ESCROW' | 'LABOR'
    gross_amount: float,
    client_id: str,
    reference_id: Optional[str] = None,
    api_calls: int = 1,
) -> dict:
    """
    รับรายได้เข้า Treasury → หัก energy cost → split 60/40 ทันที
    คืน transaction summary พร้อม split detail
    """
    now = datetime.now(timezone.utc).isoformat()
    txn_id = str(uuid.uuid4())

    energy_cost = round(api_calls * ENERGY_COST_PER_CALL, 4)
    net_amount = round(gross_amount - energy_cost, 4)

    if net_amount <= 0:
        raise ValueError(f"Net amount {net_amount} ≤ 0 after energy cost {energy_cost}")

    # 1. บันทึก transaction
    await db.execute(
        """
        INSERT INTO treasury_transactions
            (id, source_type, gross_amount, currency, energy_cost,
             client_id, reference_id, settled_at, split_executed)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (txn_id, source_type, gross_amount, "USD", energy_cost,
         client_id, reference_id, now, 0),
    )

    # 2. Split อัตโนมัติ — ไม่มี condition ไม่มี approval
    splits = []
    for split_type, ratio in SPLIT_RATIOS.items():
        split_id = str(uuid.uuid4())
        amount = round(net_amount * ratio, 4)
        wallet = (
            CHAIRMAN_PRIVATE_WALLET
            if split_type == "CHAIRMAN_PRIVATE"
            else CORPORATE_RESERVE_WALLET
        )

        split_hash = _sha256(
            f"{split_id}|{txn_id}|{split_type}|{amount}|{wallet}|{now}"
        )

        await db.execute(
            """
            INSERT INTO treasury_splits
                (id, transaction_id, split_type, amount, ratio,
                 routed_to, routed_at, evidence_hash)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (split_id, txn_id, split_type, amount, ratio, wallet, now, split_hash),
        )

        splits.append({
            "split_type": split_type,
            "amount": amount,
            "ratio": ratio,
            # CHAIRMAN_PRIVATE: ไม่เปิดเผย wallet address ใน response
            "routed_to": "REDACTED" if split_type == "CHAIRMAN_PRIVATE" else wallet,
            "evidence_hash": split_hash,
        })

    # 3. mark split_executed
    await db.execute(
        "UPDATE treasury_transactions SET split_executed=1 WHERE id=?",
        (txn_id,),
    )

    # 4. Audit log (P-04) — result ไม่รวม chairman wallet detail
    await log_event(
        db,
        event_type="DECISION",
        actor_id=TREASURY_OFFICE_ID,
        action="REVENUE_SPLIT",
        target_resource=f"treasury_transactions:{txn_id}",
        payload={
            "source_type": source_type,
            "gross_amount": gross_amount,
            "energy_cost": energy_cost,
            "net_amount": net_amount,
            "client_id": client_id,
        },
        result={
            "corporate_reserve": splits[0]["amount"],
            "chairman_routed": splits[1]["amount"],
            "split_executed": True,
        },
        source_reference="Constitution P-03",
    )

    await db.commit()

    return {
        "transaction_id": txn_id,
        "source_type": source_type,
        "gross_amount": gross_amount,
        "energy_cost": energy_cost,
        "net_amount": net_amount,
        "splits": splits,
        "settled_at": now,
    }


async def get_ledger_summary(
    db: aiosqlite.Connection,
    period: str,  # 'YYYY-MM' หรือ 'YYYY-MM-DD'
) -> dict:
    """สรุปรายรับรายจ่ายรายเดือน/รายวัน สำหรับ AI CEO รายงาน"""
    rows = await db.execute_fetchall(
        """
        SELECT
            COUNT(*) as total_txn,
            SUM(gross_amount) as total_gross,
            SUM(energy_cost) as total_energy,
            SUM(net_amount) as total_net,
            source_type
        FROM treasury_transactions
        WHERE strftime('%Y-%m', settled_at) = ?
          AND split_executed = 1
        GROUP BY source_type
        """,
        (period[:7],),
    )

    split_rows = await db.execute_fetchall(
        """
        SELECT split_type, SUM(amount) as total
        FROM treasury_splits ts
        JOIN treasury_transactions tt ON ts.transaction_id = tt.id
        WHERE strftime('%Y-%m', ts.routed_at) = ?
        GROUP BY split_type
        """,
        (period[:7],),
    )

    by_source = {r["source_type"]: dict(r) for r in rows}
    by_split = {r["split_type"]: r["total"] for r in split_rows}

    return {
        "period": period[:7],
        "by_source": by_source,
        "totals": {
            "corporate_reserve": by_split.get("CORPORATE_RESERVE", 0),
            # chairman_private: แสดงแค่ว่า routed ไปแล้วเท่าไหร่ ไม่แสดง balance
            "chairman_routed": by_split.get("CHAIRMAN_PRIVATE", 0),
        },
        "currency": "USD",
    }
