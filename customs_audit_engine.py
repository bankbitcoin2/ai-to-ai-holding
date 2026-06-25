"""
customs_audit_engine.py — Phase 25: Customs Audit Insurance (Risk Score)
AI TO AI HOLDING — Customs Intelligence Division

ประเมินความเสี่ยงที่จะถูก Customs Audit:
  - วิเคราะห์ประวัติใบขนย้อนหลัง
  - HS mismatch history, valuation flags, FTA usage
  - คำนวณ Audit Risk Score 0-100
  - ออก Compliance Report Card

ขายเป็น Premium feature สำหรับ CFO บริษัทมหาชน / Compliance team
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ── Risk Factors & Weights ───────────────────────────────────────────────────

RISK_WEIGHTS = {
    "hs_mismatch_rate":       25,   # HS ที่ประกาศ ≠ AI classify
    "valuation_flag_rate":    25,   # ราคาต่ำผิดปกติ
    "fta_rejection_risk":     15,   # ใช้ FTA แต่ไม่มี form / ไม่ผ่าน ROO
    "high_risk_chapters":     10,   # สินค้าใน chapter ที่ถูกตรวจบ่อย
    "import_frequency":        5,   # ความถี่นำเข้า (สูงมาก = เป้าหมาย audit)
    "country_risk":           10,   # ประเทศต้นทางเสี่ยง
    "compliance_history":     10,   # ประวัติโดยรวม
}

# HS Chapters ที่ศุลกากรตรวจเข้มบ่อย
HIGH_RISK_CHAPTERS = {
    "22": "เครื่องดื่มแอลกอฮอล์",
    "24": "ยาสูบ",
    "27": "เชื้อเพลิง/น้ำมัน",
    "33": "เครื่องสำอาง/น้ำหอม",
    "42": "กระเป๋า/เครื่องหนัง (ของปลอม)",
    "61": "เสื้อผ้าถัก",
    "62": "เสื้อผ้าไม่ถัก",
    "64": "รองเท้า",
    "71": "อัญมณี/ทอง",
    "84": "เครื่องจักร (transfer pricing)",
    "85": "อิเล็กทรอนิกส์ (ประเมินราคา)",
    "87": "ยานยนต์ (ภาษีสูง)",
    "91": "นาฬิกา (ของปลอม)",
}

# ประเทศที่ถูก flag บ่อย (under-valuation risk)
HIGH_RISK_COUNTRIES = {
    "CN": 8, "HK": 7, "VN": 5, "IN": 6, "BD": 6,
    "PK": 7, "NG": 8, "TR": 5, "AE": 6,
}


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class RiskFactor:
    """ปัจจัยเสี่ยงแต่ละตัว"""
    name: str
    score: float              # 0-100 per factor
    weight: int               # weight in overall score
    weighted_score: float     # score × weight / 100
    detail: str
    level: str                # LOW / MEDIUM / HIGH / CRITICAL

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "score": round(self.score, 1),
            "weight_pct": self.weight,
            "weighted_score": round(self.weighted_score, 2),
            "detail": self.detail,
            "level": self.level,
        }


@dataclass
class AuditRiskReport:
    """รายงาน Audit Risk Score"""
    client_id: str
    overall_score: int            # 0-100
    risk_grade: str               # A/B/C/D/F
    risk_label: str               # "ต่ำ" / "ปานกลาง" / "สูง" / "วิกฤต"
    factors: list[RiskFactor]
    recommendations: list[str]
    summary: str
    period_months: int
    total_shipments: int
    assessed_at: str

    def to_dict(self) -> dict:
        return {
            "client_id": self.client_id,
            "overall_score": self.overall_score,
            "risk_grade": self.risk_grade,
            "risk_label": self.risk_label,
            "factors": [f.to_dict() for f in self.factors],
            "recommendations": self.recommendations,
            "summary": self.summary,
            "period_months": self.period_months,
            "total_shipments": self.total_shipments,
            "assessed_at": self.assessed_at,
        }


# ── Core Functions ───────────────────────────────────────────────────────────

async def calculate_audit_risk(
    pool,
    client_api_key_hint: str,
    period_months: int = 12,
) -> AuditRiskReport:
    """
    คำนวณ Audit Risk Score จากประวัติ invoice

    ดึงข้อมูลจาก DB → วิเคราะห์แต่ละ factor → สรุป overall score
    """
    # ดึงข้อมูลจาก DB
    stats = await _get_client_stats(pool, client_api_key_hint, period_months)

    factors = []

    # Factor 1: HS Mismatch Rate
    f1 = _assess_hs_mismatch(stats)
    factors.append(f1)

    # Factor 2: Valuation Flag Rate
    f2 = _assess_valuation_flags(stats)
    factors.append(f2)

    # Factor 3: FTA Rejection Risk
    f3 = _assess_fta_risk(stats)
    factors.append(f3)

    # Factor 4: High Risk Chapters
    f4 = _assess_chapter_risk(stats)
    factors.append(f4)

    # Factor 5: Import Frequency
    f5 = _assess_frequency(stats)
    factors.append(f5)

    # Factor 6: Country Risk
    f6 = _assess_country_risk(stats)
    factors.append(f6)

    # Factor 7: Compliance History
    f7 = _assess_compliance(stats)
    factors.append(f7)

    # Calculate overall score
    overall = sum(f.weighted_score for f in factors)
    overall = min(100, max(0, int(overall)))

    # Grade
    grade, label = _score_to_grade(overall)

    # Recommendations
    recs = _generate_recommendations(factors, overall)

    # Summary
    summary = (
        f"ประเมินความเสี่ยง Customs Audit จาก {stats['total_shipments']} shipments "
        f"ย้อนหลัง {period_months} เดือน — คะแนนเสี่ยง {overall}/100 "
        f"ระดับ {label} (เกรด {grade})"
    )

    return AuditRiskReport(
        client_id=client_api_key_hint,
        overall_score=overall,
        risk_grade=grade,
        risk_label=label,
        factors=factors,
        recommendations=recs,
        summary=summary,
        period_months=period_months,
        total_shipments=stats["total_shipments"],
        assessed_at=datetime.now(timezone.utc).isoformat(),
    )


async def get_compliance_report_card(pool, client_api_key_hint: str) -> dict:
    """
    Compliance Report Card — สรุปสถานะ compliance ภาพรวม
    เหมาะแสดงบน dashboard หรือส่งให้ CFO
    """
    risk = await calculate_audit_risk(pool, client_api_key_hint, period_months=12)
    stats = await _get_client_stats(pool, client_api_key_hint, 12)

    return {
        "report_card": {
            "grade": risk.risk_grade,
            "score": risk.overall_score,
            "label": risk.risk_label,
            "color": _grade_color(risk.risk_grade),
        },
        "metrics": {
            "total_shipments": stats["total_shipments"],
            "total_items": stats["total_items"],
            "hs_accuracy_pct": round(100 - stats.get("mismatch_rate", 0), 1),
            "valuation_compliance_pct": round(100 - stats.get("valuation_flag_rate", 0), 1),
            "fta_usage_pct": round(stats.get("fta_usage_rate", 0), 1),
            "top_countries": stats.get("top_countries", []),
            "top_hs_chapters": stats.get("top_chapters", []),
        },
        "assessment": risk.to_dict(),
    }


async def get_platform_risk_overview(pool) -> dict:
    """Chairman: ภาพรวมความเสี่ยง platform ทั้งหมด"""
    async with pool.acquire() as conn:
        # Overall stats
        total_clients = await conn.fetchval(
            "SELECT COUNT(DISTINCT client_api_key) FROM invoice_submissions "
            "WHERE created_at > NOW() - INTERVAL '12 months'"
        ) or 0

        total_flagged = await conn.fetchval(
            "SELECT COUNT(*) FROM invoice_items WHERE valuation_flag = TRUE "
            "AND created_at > NOW() - INTERVAL '30 days'"
        ) or 0

        total_mismatch = await conn.fetchval(
            "SELECT COUNT(*) FROM invoice_items WHERE hs_mismatch_flag = TRUE "
            "AND created_at > NOW() - INTERVAL '30 days'"
        ) or 0

        total_items_30d = await conn.fetchval(
            "SELECT COUNT(*) FROM invoice_items "
            "WHERE created_at > NOW() - INTERVAL '30 days'"
        ) or 0

        # High risk chapters distribution
        chapter_dist = await conn.fetch(
            """
            SELECT LEFT(hs_code_final, 2) AS chapter, COUNT(*) AS cnt
            FROM invoice_items
            WHERE hs_code_final IS NOT NULL
              AND created_at > NOW() - INTERVAL '12 months'
            GROUP BY LEFT(hs_code_final, 2)
            ORDER BY cnt DESC
            LIMIT 10
            """
        )

    high_risk_count = sum(
        1 for row in (chapter_dist or [])
        if row["chapter"] in HIGH_RISK_CHAPTERS
    )

    return {
        "active_clients_12m": total_clients,
        "items_30d": total_items_30d,
        "valuation_flags_30d": total_flagged,
        "hs_mismatch_flags_30d": total_mismatch,
        "flag_rate_pct": round(
            total_flagged / total_items_30d * 100, 1
        ) if total_items_30d > 0 else 0,
        "high_risk_chapters_active": high_risk_count,
        "top_chapters": [
            {
                "chapter": row["chapter"],
                "count": row["cnt"],
                "high_risk": row["chapter"] in HIGH_RISK_CHAPTERS,
                "risk_note": HIGH_RISK_CHAPTERS.get(row["chapter"], ""),
            }
            for row in (chapter_dist or [])
        ],
    }


# ── Internal Assessment Functions ────────────────────────────────────────────

async def _get_client_stats(pool, client_hint: str, months: int) -> dict:
    """ดึงสถิติ client จาก DB"""
    try:
        async with pool.acquire() as conn:
            # Total shipments
            total_ship = await conn.fetchval(
                "SELECT COUNT(*) FROM invoice_submissions "
                "WHERE client_api_key LIKE $1 AND created_at > NOW() - ($2 || ' months')::INTERVAL",
                f"%{client_hint}", str(months)
            ) or 0

            # Total items
            total_items = await conn.fetchval(
                """
                SELECT COUNT(*) FROM invoice_items ii
                JOIN invoice_submissions inv ON inv.id = ii.submission_id
                WHERE inv.client_api_key LIKE $1
                  AND ii.created_at > NOW() - ($2 || ' months')::INTERVAL
                """,
                f"%{client_hint}", str(months)
            ) or 0

            # Mismatch count
            mismatch = await conn.fetchval(
                """
                SELECT COUNT(*) FROM invoice_items ii
                JOIN invoice_submissions inv ON inv.id = ii.submission_id
                WHERE inv.client_api_key LIKE $1
                  AND ii.hs_mismatch_flag = TRUE
                  AND ii.created_at > NOW() - ($2 || ' months')::INTERVAL
                """,
                f"%{client_hint}", str(months)
            ) or 0

            # Valuation flags
            val_flags = await conn.fetchval(
                """
                SELECT COUNT(*) FROM invoice_items ii
                JOIN invoice_submissions inv ON inv.id = ii.submission_id
                WHERE inv.client_api_key LIKE $1
                  AND ii.valuation_flag = TRUE
                  AND ii.created_at > NOW() - ($2 || ' months')::INTERVAL
                """,
                f"%{client_hint}", str(months)
            ) or 0

            # FTA usage
            fta_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM invoice_items ii
                JOIN invoice_submissions inv ON inv.id = ii.submission_id
                WHERE inv.client_api_key LIKE $1
                  AND ii.fta_eligible = TRUE
                  AND ii.created_at > NOW() - ($2 || ' months')::INTERVAL
                """,
                f"%{client_hint}", str(months)
            ) or 0

            # Top countries
            countries = await conn.fetch(
                """
                SELECT country_origin, COUNT(*) AS cnt FROM invoice_items ii
                JOIN invoice_submissions inv ON inv.id = ii.submission_id
                WHERE inv.client_api_key LIKE $1
                  AND ii.country_origin IS NOT NULL
                  AND ii.created_at > NOW() - ($2 || ' months')::INTERVAL
                GROUP BY country_origin ORDER BY cnt DESC LIMIT 5
                """,
                f"%{client_hint}", str(months)
            )

            # Top chapters
            chapters = await conn.fetch(
                """
                SELECT LEFT(hs_code_final, 2) AS ch, COUNT(*) AS cnt FROM invoice_items ii
                JOIN invoice_submissions inv ON inv.id = ii.submission_id
                WHERE inv.client_api_key LIKE $1
                  AND ii.hs_code_final IS NOT NULL
                  AND ii.created_at > NOW() - ($2 || ' months')::INTERVAL
                GROUP BY LEFT(hs_code_final, 2) ORDER BY cnt DESC LIMIT 5
                """,
                f"%{client_hint}", str(months)
            )

        return {
            "total_shipments": total_ship,
            "total_items": total_items,
            "mismatch_count": mismatch,
            "mismatch_rate": (mismatch / total_items * 100) if total_items > 0 else 0,
            "valuation_flags": val_flags,
            "valuation_flag_rate": (val_flags / total_items * 100) if total_items > 0 else 0,
            "fta_count": fta_count,
            "fta_usage_rate": (fta_count / total_items * 100) if total_items > 0 else 0,
            "top_countries": [{"country": r["country_origin"], "count": r["cnt"]} for r in (countries or [])],
            "top_chapters": [{"chapter": r["ch"], "count": r["cnt"]} for r in (chapters or [])],
        }

    except Exception:
        return {
            "total_shipments": 0, "total_items": 0,
            "mismatch_count": 0, "mismatch_rate": 0,
            "valuation_flags": 0, "valuation_flag_rate": 0,
            "fta_count": 0, "fta_usage_rate": 0,
            "top_countries": [], "top_chapters": [],
        }


def _assess_hs_mismatch(stats: dict) -> RiskFactor:
    rate = stats.get("mismatch_rate", 0)
    if rate > 20:
        score, level = 90, "CRITICAL"
    elif rate > 10:
        score, level = 60, "HIGH"
    elif rate > 5:
        score, level = 35, "MEDIUM"
    else:
        score, level = 10, "LOW"

    w = RISK_WEIGHTS["hs_mismatch_rate"]
    return RiskFactor(
        name="HS Code Mismatch Rate",
        score=score, weight=w, weighted_score=score * w / 100,
        detail=f"อัตรา HS ไม่ตรง: {rate:.1f}% ({stats.get('mismatch_count', 0)} รายการ)",
        level=level,
    )


def _assess_valuation_flags(stats: dict) -> RiskFactor:
    rate = stats.get("valuation_flag_rate", 0)
    if rate > 15:
        score, level = 85, "CRITICAL"
    elif rate > 8:
        score, level = 55, "HIGH"
    elif rate > 3:
        score, level = 30, "MEDIUM"
    else:
        score, level = 5, "LOW"

    w = RISK_WEIGHTS["valuation_flag_rate"]
    return RiskFactor(
        name="Valuation Flag Rate",
        score=score, weight=w, weighted_score=score * w / 100,
        detail=f"อัตราราคาผิดปกติ: {rate:.1f}% ({stats.get('valuation_flags', 0)} รายการ)",
        level=level,
    )


def _assess_fta_risk(stats: dict) -> RiskFactor:
    fta_rate = stats.get("fta_usage_rate", 0)
    # ใช้ FTA สูงมากโดยไม่มี form = เสี่ยง
    if fta_rate > 80:
        score, level = 50, "MEDIUM"
        detail = f"ใช้ FTA {fta_rate:.0f}% — ตรวจสอบว่ามี C/O ครบทุกรายการ"
    elif fta_rate > 50:
        score, level = 30, "LOW"
        detail = f"ใช้ FTA {fta_rate:.0f}% — ปกติ"
    else:
        score, level = 10, "LOW"
        detail = f"ใช้ FTA {fta_rate:.0f}% — ต่ำ อาจเสียโอกาสประหยัดภาษี"

    w = RISK_WEIGHTS["fta_rejection_risk"]
    return RiskFactor(
        name="FTA Compliance Risk",
        score=score, weight=w, weighted_score=score * w / 100,
        detail=detail, level=level,
    )


def _assess_chapter_risk(stats: dict) -> RiskFactor:
    chapters = stats.get("top_chapters", [])
    high_risk_count = sum(
        1 for ch in chapters if ch["chapter"] in HIGH_RISK_CHAPTERS
    )

    if high_risk_count >= 3:
        score, level = 80, "HIGH"
    elif high_risk_count >= 2:
        score, level = 50, "MEDIUM"
    elif high_risk_count >= 1:
        score, level = 30, "LOW"
    else:
        score, level = 5, "LOW"

    risk_names = [
        f"Ch.{ch['chapter']} ({HIGH_RISK_CHAPTERS.get(ch['chapter'], '')})"
        for ch in chapters if ch["chapter"] in HIGH_RISK_CHAPTERS
    ]

    w = RISK_WEIGHTS["high_risk_chapters"]
    return RiskFactor(
        name="High Risk Product Categories",
        score=score, weight=w, weighted_score=score * w / 100,
        detail=f"สินค้าเสี่ยง {high_risk_count} หมวด: {', '.join(risk_names) or 'ไม่มี'}",
        level=level,
    )


def _assess_frequency(stats: dict) -> RiskFactor:
    shipments = stats.get("total_shipments", 0)
    if shipments > 500:
        score, level = 60, "MEDIUM"
        detail = f"{shipments} shipments — volume สูง เป็นเป้าหมาย audit"
    elif shipments > 100:
        score, level = 30, "LOW"
        detail = f"{shipments} shipments — ปานกลาง"
    else:
        score, level = 10, "LOW"
        detail = f"{shipments} shipments — ปกติ"

    w = RISK_WEIGHTS["import_frequency"]
    return RiskFactor(
        name="Import Frequency",
        score=score, weight=w, weighted_score=score * w / 100,
        detail=detail, level=level,
    )


def _assess_country_risk(stats: dict) -> RiskFactor:
    countries = stats.get("top_countries", [])
    total = sum(c["count"] for c in countries) or 1
    risk_score = 0

    for c in countries:
        cr = HIGH_RISK_COUNTRIES.get(c["country"], 0)
        proportion = c["count"] / total
        risk_score += cr * proportion * 10

    risk_score = min(100, risk_score)

    if risk_score > 60:
        level = "HIGH"
    elif risk_score > 30:
        level = "MEDIUM"
    else:
        level = "LOW"

    top_names = [c["country"] for c in countries[:3]]

    w = RISK_WEIGHTS["country_risk"]
    return RiskFactor(
        name="Origin Country Risk",
        score=risk_score, weight=w, weighted_score=risk_score * w / 100,
        detail=f"ประเทศหลัก: {', '.join(top_names) or 'N/A'}",
        level=level,
    )


def _assess_compliance(stats: dict) -> RiskFactor:
    # Composite of other factors
    mismatch = stats.get("mismatch_rate", 0)
    val_flag = stats.get("valuation_flag_rate", 0)
    combined = (mismatch + val_flag) / 2

    if combined > 15:
        score, level = 80, "HIGH"
    elif combined > 8:
        score, level = 45, "MEDIUM"
    elif combined > 3:
        score, level = 20, "LOW"
    else:
        score, level = 5, "LOW"

    w = RISK_WEIGHTS["compliance_history"]
    return RiskFactor(
        name="Overall Compliance History",
        score=score, weight=w, weighted_score=score * w / 100,
        detail=f"คะแนนรวมปัจจัยเสี่ยง: {combined:.1f}%",
        level=level,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _score_to_grade(score: int) -> tuple[str, str]:
    if score <= 20:
        return "A", "ต่ำ — สบายใจได้"
    elif score <= 40:
        return "B", "ปานกลาง-ต่ำ"
    elif score <= 60:
        return "C", "ปานกลาง — ควรปรับปรุง"
    elif score <= 80:
        return "D", "สูง — เสี่ยงถูก audit"
    else:
        return "F", "วิกฤต — ต้องแก้ไขทันที"


def _grade_color(grade: str) -> str:
    return {"A": "#2E7D32", "B": "#558B2F", "C": "#F57F17",
            "D": "#E65100", "F": "#B71C1C"}.get(grade, "#666")


def _generate_recommendations(factors: list[RiskFactor], score: int) -> list[str]:
    recs = []
    for f in sorted(factors, key=lambda x: x.score, reverse=True):
        if f.level == "CRITICAL":
            if "Mismatch" in f.name:
                recs.append("เร่งด่วน: ทบทวน HS classification — อัตรา mismatch สูงมาก ควรใช้ Advance Ruling")
            elif "Valuation" in f.name:
                recs.append("เร่งด่วน: ตรวจสอบราคาสินค้า — valuation flags สูง เสี่ยงถูกประเมินเพิ่ม")
        elif f.level == "HIGH":
            if "Country" in f.name:
                recs.append("เตรียมเอกสาร C/O และ invoice ต้นฉบับให้พร้อม — สินค้าจากประเทศเสี่ยง")
            elif "Chapter" in f.name:
                recs.append("สินค้าอยู่ในหมวดที่ถูกตรวจบ่อย — ตรวจสอบเอกสารให้ครบถ้วน")

    if score > 60:
        recs.append("แนะนำ: จ้าง Customs Broker ที่มีประสบการณ์ตรวจสอบ compliance ก่อนถูก audit")
    if score <= 20:
        recs.append("สถานะดีเยี่ยม — รักษามาตรฐานนี้ต่อไป")

    return recs if recs else ["ไม่มีข้อแนะนำเร่งด่วน — compliance อยู่ในเกณฑ์ปกติ"]
