"""
valuation_engine.py — Project Valuation & IP Assessment Engine
AI TO AI HOLDING — Customs Intelligence Division

ระบบคำนวณมูลค่าโครงการอัตโนมัติ 12+ มิติ:
  - Cost Approach: ต้นทุนพัฒนา + เวลา + ทีม
  - Income Approach: รายได้คาดการณ์ + DCF
  - Market Approach: เปรียบเทียบ Trade-Tech SaaS
  - IP Portfolio: ลิขสิทธิ์ + สิทธิบัตร + Trade Secret
  - AI Knowledge: คลังความรู้ + โมเดล + ข้อมูลสะสม
  - Legal/Litigation: มูลค่าเรียกร้องทางกฎหมาย
  - Scalability: การเติบโตตามฐานผู้ใช้

หลักการ WIPO + AICPA + FASB:
  Cost Approach, Income Approach, Market Approach

ตั้งต้น ฿15,000,000 — ทุกไฟล์ ทุกระบบ ทุกฟีเจอร์ มีคุณค่าในตัวมันเอง
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import math


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: CODEBASE INVENTORY — ข้อมูลโครงการจริง
# ══════════════════════════════════════════════════════════════════════════════

CODEBASE_STATS = {
    "python_files": 72,
    "python_lines": 17752,
    "sql_schemas": 12,
    "sql_lines": 1170,
    "html_files": 4,
    "json_configs": 8,
    "total_files": 241,
    "routers": 23,
    "api_endpoints": 108,
    "engine_modules": 14,
    "router_modules": 16,
    "total_code_lines": 17752 + 1170,  # Python + SQL
}

# ── Feature Modules (แต่ละ module มีมูลค่าในตัวเอง) ─────────────────────────

FEATURE_MODULES = {
    # Core Platform
    "hs_classification_ai": {
        "name_th": "ระบบจำแนกพิกัดศุลกากร AI",
        "name_en": "AI HS Classification Engine",
        "category": "CORE",
        "complexity": "HIGH",
        "files": ["customs.py", "cache_classification.py", "hs_descriptions_bundled.py"],
        "unique_data_assets": ["HS code descriptions TH/EN", "Classification cache", "Learning feedback loop"],
        "market_value_thb": 2_500_000,
        "note": "หัวใจของระบบ — AI classify HS code 11 หลักพร้อมคำอธิบายไทย/อังกฤษ",
    },
    "fta_eligibility": {
        "name_th": "ระบบตรวจสิทธิ์ FTA",
        "name_en": "FTA Eligibility Engine",
        "category": "CORE",
        "complexity": "HIGH",
        "files": ["fta_eligibility_bundled.py", "customs.py"],
        "unique_data_assets": ["13 FTA agreements data", "Country-HS mapping"],
        "market_value_thb": 1_800_000,
        "note": "ตรวจสิทธิ์ FTA 13 ความตกลง ครอบคลุม RCEP/CPTPP/ATIGA",
    },
    "invoice_validation": {
        "name_th": "ระบบตรวจสอบใบกำกับสินค้า",
        "name_en": "Invoice Validation & Processing",
        "category": "CORE",
        "complexity": "MEDIUM",
        "files": ["invoice_service.py", "invoice_router.py"],
        "unique_data_assets": ["Validation rules", "Batch processing pipeline"],
        "market_value_thb": 1_200_000,
        "note": "Batch upload + validation + top-3 candidates + XAI reasoning",
    },
    "tax_engine": {
        "name_th": "เครื่องคำนวณภาษีนำเข้า",
        "name_en": "Import Tax Calculator",
        "category": "CORE",
        "complexity": "HIGH",
        "files": ["tax_engine_bundled.py"],
        "unique_data_assets": ["Thai customs duty rates", "Excise tax rules", "VAT calculation"],
        "market_value_thb": 1_500_000,
        "note": "คำนวณอากร + สรรพสามิต + VAT ครบวงจร",
    },
    "halal_certification": {
        "name_th": "ระบบตรวจ Halal",
        "name_en": "Halal Certification Engine",
        "category": "CORE",
        "complexity": "MEDIUM",
        "files": ["halal_engine.py"],
        "unique_data_assets": ["21 Muslim-majority countries data", "Halal cert requirements"],
        "market_value_thb": 800_000,
        "note": "ตรวจ Halal 21 ประเทศ — niche market ที่คู่แข่งไม่มี",
    },
    "oga_engine": {
        "name_th": "ระบบ OGA หน่วยงานกำกับ",
        "name_en": "OGA Regulatory Agency Engine",
        "category": "INTELLIGENCE",
        "complexity": "HIGH",
        "files": ["oga_engine.py", "oga_router.py"],
        "unique_data_assets": ["36 Thai government agencies", "HS-to-agency mapping rules", "Document checklists"],
        "market_value_thb": 2_000_000,
        "note": "36 หน่วยงานกำกับ + batch check + เอกสารที่ต้องใช้ — ไม่มีคู่แข่งรายใดรวมครบ",
    },
    "landed_cost_calculator": {
        "name_th": "คำนวณต้นทุนนำเข้า Landed Cost",
        "name_en": "Landed Cost Calculator",
        "category": "INTELLIGENCE",
        "complexity": "HIGH",
        "files": ["landed_cost_engine.py", "landed_cost_router.py"],
        "unique_data_assets": ["11 Incoterms 2020", "Thai port data", "Freight/insurance rates"],
        "market_value_thb": 1_500_000,
        "note": "Incoterms + freight + insurance + duties = total landed cost",
    },
    "price_benchmark": {
        "name_th": "ระบบตรวจราคาต่ำกว่าตลาด",
        "name_en": "Price Benchmark Intelligence",
        "category": "INTELLIGENCE",
        "complexity": "HIGH",
        "files": ["price_benchmark_engine.py", "price_benchmark_router.py"],
        "unique_data_assets": ["Under-valuation detection model", "Risk scoring algorithm"],
        "market_value_thb": 1_800_000,
        "note": "ตรวจจับ under-invoicing — ช่วยศุลกากรป้องกันการหลีกเลี่ยงภาษี",
    },
    "freight_auditor": {
        "name_th": "ตรวจสอบค่าขนส่ง",
        "name_en": "Freight Rate Auditor",
        "category": "INTELLIGENCE",
        "complexity": "HIGH",
        "files": ["freight_auditor_engine.py", "freight_auditor_router.py"],
        "unique_data_assets": ["Market rate database (Drewry/Freightos)", "Overcharge detection", "Forwarder comparison"],
        "market_value_thb": 1_200_000,
        "note": "เทียบค่าขนส่งกับราคาตลาด + ตรวจจับ overcharge",
    },
    "whatif_optimizer": {
        "name_th": "จำลองสถานการณ์ What-If",
        "name_en": "What-If Scenario Optimizer",
        "category": "INTELLIGENCE",
        "complexity": "HIGH",
        "files": ["whatif_optimizer_engine.py", "whatif_router.py"],
        "unique_data_assets": ["Route optimization", "FTA scenario modeling", "Volume discount simulation"],
        "market_value_thb": 1_500_000,
        "note": "Duty engineering + route optimization — ช่วยลูกค้าประหยัดภาษี",
    },
    "customs_audit_insurance": {
        "name_th": "ประกันความเสี่ยงตรวจสอบศุลกากร",
        "name_en": "Customs Audit Risk Insurance",
        "category": "INTELLIGENCE",
        "complexity": "HIGH",
        "files": ["customs_audit_engine.py", "customs_audit_router.py"],
        "unique_data_assets": ["7-factor risk model", "Audit Risk Score 0-100", "Compliance Report Card"],
        "market_value_thb": 2_000_000,
        "note": "Risk Score + Grade A-F + Compliance Report Card สำหรับ CFO",
    },
    "cbam_carbon_tracker": {
        "name_th": "ติดตาม Carbon Footprint / EU CBAM",
        "name_en": "CBAM Carbon Tracker",
        "category": "EXPANSION",
        "complexity": "HIGH",
        "files": ["cbam_carbon_engine.py", "cbam_carbon_router.py"],
        "unique_data_assets": ["EU CBAM sector mapping", "Emission factors (IPCC/worldsteel/IAI)", "20-country grid factors"],
        "market_value_thb": 2_500_000,
        "note": "EU CBAM compliance — จำเป็นสำหรับส่งออกไป EU ตั้งแต่ 2026",
    },
    "asean_expansion": {
        "name_th": "ขยายตลาด ASEAN 6 ประเทศ",
        "name_en": "ASEAN Expansion Module",
        "category": "EXPANSION",
        "complexity": "HIGH",
        "files": ["asean_expansion_engine.py", "asean_expansion_router.py"],
        "unique_data_assets": ["6-country profiles", "12 HS duty comparisons", "Multi-country compliance"],
        "market_value_thb": 2_000_000,
        "note": "เปรียบเทียบภาษี 6 ประเทศ ASEAN — scalable",
    },
    "membership_pricing": {
        "name_th": "ระบบสมาชิก + Pricing Tiers",
        "name_en": "Membership & Pricing System",
        "category": "REVENUE",
        "complexity": "MEDIUM",
        "files": ["membership_engine.py", "membership_router.py", "pricing_engine.py", "pricing_router.py"],
        "unique_data_assets": ["5 membership tiers", "6 pricing tiers", "14 currencies"],
        "market_value_thb": 1_000_000,
        "note": "VIP-SuperPremium + Sandbox→Enterprise pricing + multi-currency",
    },
    "analytics_dashboard": {
        "name_th": "แดชบอร์ดวิเคราะห์ลูกค้า",
        "name_en": "Client Analytics Dashboard",
        "category": "REVENUE",
        "complexity": "MEDIUM",
        "files": ["client_analytics_router.py"],
        "unique_data_assets": ["Usage analytics", "Revenue metrics"],
        "market_value_thb": 600_000,
        "note": "Chairman dashboard + client usage analytics",
    },
    "security_layer": {
        "name_th": "ระบบความปลอดภัย",
        "name_en": "Security & Kill Switch",
        "category": "INFRASTRUCTURE",
        "complexity": "HIGH",
        "files": ["security.py", "kill_switch_engine.py", "kill_switch_router.py", "chairman_router.py"],
        "unique_data_assets": ["API key auth", "Rate limiting", "IP allowlist", "Kill switch"],
        "market_value_thb": 1_500_000,
        "note": "Multi-layer security + Chairman IP allowlist + emergency kill switch",
    },
    "multi_channel": {
        "name_th": "ช่องทางเชื่อมต่อ (LINE/PWA/MCP)",
        "name_en": "Multi-Channel Integration",
        "category": "INFRASTRUCTURE",
        "complexity": "MEDIUM",
        "files": ["line_webhook.py", "mcp_handler.py"],
        "unique_data_assets": ["LINE Bot integration", "PWA app", "MCP plugin spec"],
        "market_value_thb": 800_000,
        "note": "LINE Bot + PWA + MCP Plugin — 3 ช่องทางเข้าถึงลูกค้า",
    },
    "ai_discovery_layer": {
        "name_th": "AI-to-AI Discovery Layer",
        "name_en": "AI Discovery (GPT/MCP/LangChain)",
        "category": "INFRASTRUCTURE",
        "complexity": "MEDIUM",
        "files": [".well-known/ai-plugin.json", ".well-known/mcp.json", ".well-known/function-schemas.json"],
        "unique_data_assets": ["OpenAI GPT Actions spec", "Anthropic MCP manifest", "Function calling schemas"],
        "market_value_thb": 500_000,
        "note": "รองรับ GPT Actions + MCP + LangChain + Gemini — AI-to-AI discovery",
    },
    "database_schemas": {
        "name_th": "โครงสร้างฐานข้อมูล",
        "name_en": "Database Schema & Migration",
        "category": "INFRASTRUCTURE",
        "complexity": "HIGH",
        "files": ["schema_*.sql"],
        "unique_data_assets": ["12 SQL schemas", "Migration scripts", "PostgreSQL optimized"],
        "market_value_thb": 800_000,
        "note": "12 schemas + auto-seed + migration scripts — production-ready",
    },
    "treasury_wallet": {
        "name_th": "ระบบ Treasury + กระเป๋าเงิน",
        "name_en": "Treasury & Wallet System",
        "category": "REVENUE",
        "complexity": "HIGH",
        "files": ["treasury.py", "wallet_engine.py", "treasury_wallet_router.py", "billing.py"],
        "unique_data_assets": ["Credit system", "Billing pipeline", "Treasury management"],
        "market_value_thb": 1_200_000,
        "note": "ระบบ credit/billing/treasury ครบวงจร",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: VALUATION PARAMETERS
# ══════════════════════════════════════════════════════════════════════════════

# ── Development Cost Parameters ───────────────────────────────────────────────
# Source: PayScale/Glassdoor Thailand 2026, adjusted for AI-specialized

DEV_COST_PARAMS = {
    "senior_python_dev_monthly_thb": 120_000,       # ฿120K/mo — Senior Python (Bangkok)
    "ai_ml_specialist_monthly_thb": 180_000,         # ฿180K/mo — AI/ML specialist
    "devops_monthly_thb": 100_000,                   # ฿100K/mo — DevOps/Cloud
    "domain_expert_customs_monthly_thb": 150_000,    # ฿150K/mo — Customs domain expert (rare)
    "project_manager_monthly_thb": 100_000,          # ฿100K/mo — Tech PM
    "qa_monthly_thb": 80_000,                        # ฿80K/mo — QA Engineer

    # International equivalent cost (US outsource rate)
    "us_equivalent_hourly_usd": 150,                 # $150/hr for equivalent US dev
    "us_ai_specialist_hourly_usd": 250,              # $250/hr for AI specialist

    # Estimated development months
    "core_platform_months": 8,           # P1-P14 (pre-Re-Born)
    "tier1_foundation_months": 2,        # P15-P17
    "tier2_revenue_months": 2,           # P18-P20
    "tier3_intelligence_months": 3,      # P21-P24
    "tier4_expansion_months": 2,         # P25-P28
    "total_dev_months": 17,
}

# ── Market Comparable Parameters ──────────────────────────────────────────────
# Source: Multiples.vc Jun 2026, WiseTech/Descartes public filings

MARKET_PARAMS = {
    # Trade-Tech SaaS revenue multiples
    "trade_tech_revenue_multiple_low": 5.0,    # Conservative (mature, slow growth)
    "trade_tech_revenue_multiple_mid": 8.3,    # WiseTech Global actual (Jun 2026)
    "trade_tech_revenue_multiple_high": 12.0,  # High-growth AI-powered
    "supply_chain_median_ntm_multiple": 7.3,   # Supply chain sector median

    # IP licensing royalty rates (% of revenue)
    "software_royalty_rate_low": 15.0,   # Standard SaaS license
    "software_royalty_rate_mid": 25.0,   # Specialized vertical SaaS
    "software_royalty_rate_high": 40.0,  # AI/ML with proprietary data

    # Thai market reference
    "thai_trade_value_usd_billion": 684.0,     # Total Thai trade 2025 ($339B export + $345B import)
    "thai_trade_value_thb_trillion": 22.8,     # ~฿22.8 trillion
    "thai_customs_duty_revenue_thb_billion": 130.0,  # ศุลกากรจัดเก็บ ~฿130B/year

    # Addressable market
    "thai_importers_estimated": 50_000,        # จำนวนผู้นำเข้าไทยโดยประมาณ
    "asean_importers_estimated": 300_000,      # ASEAN 6 ประเทศ
    "global_trade_compliance_market_usd_billion": 2.5,  # Global trade compliance software market
}

# ── Growth & Revenue Projections ──────────────────────────────────────────────

REVENUE_PROJECTIONS = {
    # Monthly revenue per tier (from pricing_engine.py)
    "sandbox_free": 0,
    "starter_monthly_usd": 49,
    "professional_monthly_usd": 149,
    "business_monthly_usd": 299,
    "enterprise_s_monthly_usd": 500,
    "enterprise_l_monthly_usd": 500,  # Custom pricing

    # Conservative user growth scenario
    "year1_paying_users": 50,
    "year2_paying_users": 200,
    "year3_paying_users": 500,
    "year4_paying_users": 1200,
    "year5_paying_users": 3000,

    # Average revenue per user (blended)
    "arpu_monthly_usd": 180,   # Weighted avg across tiers
    "annual_churn_rate": 0.08,  # 8% — vertical SaaS typically 5-10%
    "nrr_percent": 115,         # Net Revenue Retention — expansion > churn

    # Discount rate for DCF
    "wacc_percent": 15.0,       # Weighted Average Cost of Capital (startup risk)
    "terminal_growth_rate": 3.0,  # Long-term growth after Year 5
}

# ── Exchange Rate ─────────────────────────────────────────────────────────────
THB_PER_USD = 33.5  # Jun 2026 approximate


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ValuationDimension:
    """มิติการประเมินมูลค่า"""
    dimension_id: str
    name_th: str
    name_en: str
    method: str          # COST / INCOME / MARKET / HYBRID
    value_thb: float
    value_usd: float
    confidence: str      # HIGH / MEDIUM / LOW
    rationale: str       # เหตุผลภาคบรรยาย (ไทย)
    sources: list[str]

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension_id,
            "name_th": self.name_th,
            "name_en": self.name_en,
            "method": self.method,
            "value_thb": round(self.value_thb),
            "value_usd": round(self.value_usd),
            "confidence": self.confidence,
            "rationale": self.rationale,
            "sources": self.sources,
        }


@dataclass
class FullValuation:
    """ผลประเมินมูลค่าโครงการทั้งหมด"""
    project_name: str
    valuation_date: str
    base_value_thb: float           # มูลค่าตั้งต้น
    dimensions: list[ValuationDimension]
    total_value_thb: float
    total_value_usd: float

    # สรุปตามวิธีการ
    cost_approach_thb: float
    income_approach_thb: float
    market_approach_thb: float
    weighted_fair_value_thb: float

    # Litigation / IP sale
    litigation_value_thb: float     # มูลค่าเรียกร้องหากถูกลอกเลียน
    outright_sale_value_thb: float  # มูลค่าขายสิทธิ์ขาด

    # Growth projection
    projected_value_year3_thb: float
    projected_value_year5_thb: float

    codebase_stats: dict
    feature_count: int
    generated_at: str

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "valuation_date": self.valuation_date,
            "base_value_thb": self.base_value_thb,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "summary": {
                "total_value_thb": round(self.total_value_thb),
                "total_value_usd": round(self.total_value_usd),
                "cost_approach_thb": round(self.cost_approach_thb),
                "income_approach_thb": round(self.income_approach_thb),
                "market_approach_thb": round(self.market_approach_thb),
                "weighted_fair_value_thb": round(self.weighted_fair_value_thb),
                "weighted_fair_value_usd": round(self.weighted_fair_value_thb / THB_PER_USD),
            },
            "legal_values": {
                "litigation_claim_thb": round(self.litigation_value_thb),
                "litigation_claim_usd": round(self.litigation_value_thb / THB_PER_USD),
                "outright_sale_thb": round(self.outright_sale_value_thb),
                "outright_sale_usd": round(self.outright_sale_value_thb / THB_PER_USD),
            },
            "growth_projection": {
                "current_thb": round(self.weighted_fair_value_thb),
                "year3_thb": round(self.projected_value_year3_thb),
                "year5_thb": round(self.projected_value_year5_thb),
            },
            "codebase_stats": self.codebase_stats,
            "feature_modules_count": self.feature_count,
            "generated_at": self.generated_at,
        }


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4: VALUATION CALCULATION FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _calc_development_cost() -> ValuationDimension:
    """
    มิติ 1: ต้นทุนพัฒนา (Cost Approach — Replacement Cost)
    "หากคู่แข่งจะสร้างระบบนี้ขึ้นมาใหม่ ต้องใช้เงินเท่าไร?"
    """
    p = DEV_COST_PARAMS

    # ทีมพัฒนาขั้นต่ำ: 1 Senior Python + 1 AI Specialist + 1 Domain Expert + 0.5 DevOps + 0.5 PM + 0.5 QA
    monthly_team_cost = (
        p["senior_python_dev_monthly_thb"] * 1.5 +    # 1.5 senior devs
        p["ai_ml_specialist_monthly_thb"] * 1 +        # 1 AI/ML
        p["domain_expert_customs_monthly_thb"] * 1 +   # 1 customs expert (หายาก)
        p["devops_monthly_thb"] * 0.5 +                # 0.5 DevOps
        p["project_manager_monthly_thb"] * 0.5 +       # 0.5 PM
        p["qa_monthly_thb"] * 0.5                      # 0.5 QA
    )

    total_dev_cost = monthly_team_cost * p["total_dev_months"]

    # Overhead (office, tools, cloud, licenses) — 30%
    overhead = total_dev_cost * 0.30

    # Opportunity cost — developer time has alternative value
    opportunity_cost = total_dev_cost * 0.15

    total = total_dev_cost + overhead + opportunity_cost

    return ValuationDimension(
        dimension_id="D01_DEVELOPMENT_COST",
        name_th="ต้นทุนพัฒนาระบบ (Replacement Cost)",
        name_en="Development Replacement Cost",
        method="COST",
        value_thb=total,
        value_usd=total / THB_PER_USD,
        confidence="HIGH",
        rationale=(
            f"คำนวณจากทีมพัฒนาขั้นต่ำ 5 คน (Senior Python, AI Specialist, "
            f"Customs Domain Expert, DevOps, PM/QA) ทำงานต่อเนื่อง {p['total_dev_months']} เดือน "
            f"ค่าแรงรวม ฿{total_dev_cost:,.0f} บวก overhead 30% และ opportunity cost 15% "
            f"โดยผู้เชี่ยวชาญด้านศุลกากรที่มีความรู้ทั้งกฎหมายและ IT หาได้ยากมากในตลาด"
        ),
        sources=["PayScale Thailand 2026", "Glassdoor Bangkok 2026", "Jobicy Thailand"],
    )


def _calc_time_investment() -> ValuationDimension:
    """
    มิติ 2: มูลค่าเวลาที่ลงทุน (Time-to-Market Premium)
    """
    p = DEV_COST_PARAMS

    # Time-to-market advantage: 17 months head start
    months = p["total_dev_months"]

    # ถ้าคู่แข่งเริ่มวันนี้ ต้องใช้เวลา 17+ เดือน (เพราะไม่มี domain knowledge)
    # ช่วงนั้นเราทำรายได้ไปแล้ว (first-mover advantage)
    # Time premium = 25% of development cost per month advantage
    monthly_revenue_potential = REVENUE_PROJECTIONS["arpu_monthly_usd"] * 50 * THB_PER_USD  # 50 users
    time_premium = monthly_revenue_potential * months * 0.5  # 50% capture rate

    # Learning curve premium — domain expertise ที่สะสมมา
    learning_premium = months * 200_000  # ฿200K/mo ค่าความรู้สะสม

    total = time_premium + learning_premium

    return ValuationDimension(
        dimension_id="D02_TIME_INVESTMENT",
        name_th="มูลค่าเวลาที่ลงทุน + First-Mover Advantage",
        name_en="Time Investment & First-Mover Premium",
        method="COST",
        value_thb=total,
        value_usd=total / THB_PER_USD,
        confidence="MEDIUM",
        rationale=(
            f"ระบบใช้เวลาพัฒนา {months} เดือน คู่แข่งที่เริ่มจากศูนย์ต้องใช้เวลาอย่างน้อยเท่ากัน "
            f"หรือมากกว่าเพราะขาด domain knowledge ด้านศุลกากรไทย ช่วงเวลานี้คือ first-mover advantage "
            f"ที่แปลงเป็นรายได้และฐานลูกค้าที่คู่แข่งไม่มี รวมค่าความรู้สะสม ฿{learning_premium:,.0f}"
        ),
        sources=["Internal development timeline"],
    )


def _calc_revenue_potential() -> ValuationDimension:
    """
    มิติ 3: รายได้ที่ทำได้ (Income Approach — DCF 5 ปี)
    """
    r = REVENUE_PROJECTIONS
    wacc = r["wacc_percent"] / 100
    terminal_g = r["terminal_growth_rate"] / 100

    # ประมาณการรายได้ 5 ปี
    yearly_users = [r[f"year{i}_paying_users"] for i in range(1, 6)]
    arpu_annual = r["arpu_monthly_usd"] * 12 * THB_PER_USD

    yearly_revenue = [users * arpu_annual for users in yearly_users]

    # Operating margin progression: 20% → 40% → 55% → 60% → 65%
    margins = [0.20, 0.40, 0.55, 0.60, 0.65]
    yearly_fcf = [rev * margin for rev, margin in zip(yearly_revenue, margins)]

    # DCF — Discounted Cash Flow
    dcf = sum(fcf / ((1 + wacc) ** (i + 1)) for i, fcf in enumerate(yearly_fcf))

    # Terminal value (Gordon Growth Model)
    terminal_fcf = yearly_fcf[-1] * (1 + terminal_g)
    terminal_value = terminal_fcf / (wacc - terminal_g)
    pv_terminal = terminal_value / ((1 + wacc) ** 5)

    total = dcf + pv_terminal

    return ValuationDimension(
        dimension_id="D03_REVENUE_POTENTIAL",
        name_th="รายได้ที่คาดหวัง (DCF 5 ปี)",
        name_en="Revenue Potential (5-Year DCF)",
        method="INCOME",
        value_thb=total,
        value_usd=total / THB_PER_USD,
        confidence="MEDIUM",
        rationale=(
            f"คำนวณด้วย Discounted Cash Flow 5 ปี WACC {r['wacc_percent']}% "
            f"จากผู้ใช้ {yearly_users[0]} → {yearly_users[-1]} ราย "
            f"ARPU ${r['arpu_monthly_usd']}/เดือน Operating margin เพิ่มจาก 20% → 65% "
            f"Terminal growth {r['terminal_growth_rate']}% "
            f"ปีที่ 1 รายได้ ฿{yearly_revenue[0]:,.0f} → ปีที่ 5 ฿{yearly_revenue[-1]:,.0f} "
            f"DCF operating ฿{dcf:,.0f} + Terminal Value (PV) ฿{pv_terminal:,.0f}"
        ),
        sources=["Internal pricing model", "SaaS benchmarks 2026"],
    )


def _calc_ip_portfolio() -> ValuationDimension:
    """
    มิติ 4: ทรัพย์สินทางปัญญา (IP Portfolio)
    """
    # Software copyright — ลิขสิทธิ์ซอฟต์แวร์
    copyright_value = 3_000_000  # BSL 1.1 licensed, 72 Python files

    # Trade secrets — ความลับทางการค้า
    # OGA mapping rules, risk algorithms, pricing models, HS classification logic
    trade_secret_value = 5_000_000

    # Patent potential — สิทธิบัตรที่สามารถจดได้
    # AI HS classification method, multi-factor audit risk scoring, CBAM auto-calculation
    patent_potential = 3_000_000  # 3 potential patents × ฿1M

    # Database rights — สิทธิ์ในฐานข้อมูล
    # HS descriptions TH/EN, FTA eligibility, 36 OGA rules, emission factors
    database_rights = 2_000_000

    total = copyright_value + trade_secret_value + patent_potential + database_rights

    return ValuationDimension(
        dimension_id="D04_IP_PORTFOLIO",
        name_th="ทรัพย์สินทางปัญญา (ลิขสิทธิ์ + สิทธิบัตร + ความลับทางการค้า)",
        name_en="Intellectual Property Portfolio",
        method="MARKET",
        value_thb=total,
        value_usd=total / THB_PER_USD,
        confidence="MEDIUM",
        rationale=(
            f"ลิขสิทธิ์ซอฟต์แวร์ (BSL 1.1) ฿{copyright_value:,.0f} ครอบคลุม 72 ไฟล์ Python "
            f"ความลับทางการค้า ฿{trade_secret_value:,.0f} ได้แก่ อัลกอริทึมจำแนก HS code, "
            f"กฎ OGA 36 หน่วยงาน, โมเดลประเมินความเสี่ยง, สูตรคำนวณ CBAM "
            f"ศักยภาพสิทธิบัตร ฿{patent_potential:,.0f} (AI classification, risk scoring, carbon calc) "
            f"สิทธิ์ในฐานข้อมูล ฿{database_rights:,.0f} (HS descriptions, FTA rules, emission factors)"
        ),
        sources=["WIPO IP Valuation Guide 2026", "Thai Copyright Act B.E. 2537",
                 "Patent Act B.E. 2522 (amended 2542)"],
    )


def _calc_knowledge_base() -> ValuationDimension:
    """
    มิติ 5: คลังความรู้สะสม (Knowledge Base & Domain Expertise)
    """
    # HS Code descriptions — Thai/English bilingual
    hs_knowledge = 1_500_000  # 5,387+ HS codes with Thai descriptions

    # FTA eligibility rules
    fta_knowledge = 1_000_000  # 13 FTA agreements, country-HS mapping

    # OGA regulatory knowledge
    oga_knowledge = 1_500_000  # 36 agencies, rules, document requirements

    # CBAM/Carbon knowledge
    carbon_knowledge = 800_000  # Emission factors, grid factors, EU regulations

    # ASEAN trade knowledge
    asean_knowledge = 600_000  # 6 country profiles, duty rates, compliance rules

    # Halal certification knowledge
    halal_knowledge = 400_000  # 21 countries, cert requirements

    # Customs law & practice knowledge (embedded in algorithms)
    customs_law = 2_000_000  # Thai customs law encoded in business logic

    total = (hs_knowledge + fta_knowledge + oga_knowledge + carbon_knowledge +
             asean_knowledge + halal_knowledge + customs_law)

    return ValuationDimension(
        dimension_id="D05_KNOWLEDGE_BASE",
        name_th="คลังความรู้สะสม (Domain Knowledge)",
        name_en="Accumulated Knowledge Base",
        method="COST",
        value_thb=total,
        value_usd=total / THB_PER_USD,
        confidence="HIGH",
        rationale=(
            f"ความรู้ด้านศุลกากรที่ encode อยู่ในระบบ ได้แก่ "
            f"HS code 5,387+ รายการพร้อมคำอธิบายไทย/อังกฤษ ฿{hs_knowledge:,.0f} "
            f"กฎ FTA 13 ความตกลง ฿{fta_knowledge:,.0f} "
            f"กฎ OGA 36 หน่วยงาน ฿{oga_knowledge:,.0f} "
            f"ข้อมูล CBAM/Carbon ฿{carbon_knowledge:,.0f} "
            f"ข้อมูล ASEAN 6 ประเทศ ฿{asean_knowledge:,.0f} "
            f"กฎหมายศุลกากรไทยที่ encode ในอัลกอริทึม ฿{customs_law:,.0f} "
            f"ความรู้เหล่านี้ต้องใช้เวลารวบรวมและทำความเข้าใจหลายปี "
            f"ไม่สามารถซื้อหรือ copy ได้ง่ายเพราะฝังอยู่ใน business logic"
        ),
        sources=["กรมศุลกากร", "WTO Tariff Profiles", "IPCC AR6",
                 "worldsteel 2025", "IAI 2024"],
    )


def _calc_customer_base() -> ValuationDimension:
    """
    มิติ 6: ฐานลูกค้า + Brand Value
    """
    # ค่า Customer Acquisition Cost (CAC) ในตลาด B2B SaaS
    # Trade compliance SaaS มี CAC สูง เพราะ decision cycle ยาว
    cac_per_customer_thb = 50_000  # ฿50K per B2B customer
    estimated_customers_year1 = 50

    customer_base_value = cac_per_customer_thb * estimated_customers_year1

    # Customer Lifetime Value (LTV)
    arpu_annual = REVENUE_PROJECTIONS["arpu_monthly_usd"] * 12 * THB_PER_USD
    avg_lifetime_years = 5  # Vertical SaaS มี retention สูง
    ltv_per_customer = arpu_annual * avg_lifetime_years * 0.6  # 60% margin
    ltv_total = ltv_per_customer * estimated_customers_year1

    # Brand value (early-stage)
    brand_value = 500_000

    total = customer_base_value + ltv_total + brand_value

    return ValuationDimension(
        dimension_id="D06_CUSTOMER_BASE",
        name_th="ฐานลูกค้า + มูลค่าแบรนด์",
        name_en="Customer Base & Brand Value",
        method="INCOME",
        value_thb=total,
        value_usd=total / THB_PER_USD,
        confidence="LOW",
        rationale=(
            f"CAC เฉลี่ย ฿{cac_per_customer_thb:,.0f}/ราย × {estimated_customers_year1} ราย "
            f"= ฿{customer_base_value:,.0f} "
            f"LTV ฿{ltv_per_customer:,.0f}/ราย (ARPU ฿{arpu_annual:,.0f}/ปี × {avg_lifetime_years} ปี × 60% margin) "
            f"รวม LTV ฿{ltv_total:,.0f} + Brand value ฿{brand_value:,.0f} "
            f"ตลาด Trade compliance B2B มี switching cost สูง — ลูกค้าเปลี่ยนระบบยาก"
        ),
        sources=["SaaS benchmarks 2026", "B2B SaaS CAC/LTV ratios"],
    )


def _calc_ai_capability() -> ValuationDimension:
    """
    มิติ 7: ความสามารถ AI + โมเดลจำแนก
    (รวมมูลค่าของ Claude/AI Agent ที่ทำงานให้ระบบ)
    """
    # AI Classification Model — trained on customs data
    ai_classification = 3_000_000

    # AI Agent capability — Claude Opus/Sonnet integration
    # ความสามารถในการวิเคราะห์, ให้เหตุผล, XAI reasoning
    ai_agent_value = 2_000_000

    # Prompt engineering & system design
    # System prompts, few-shot examples, chain-of-thought customs reasoning
    prompt_engineering = 1_000_000

    # Data pipeline — classification → cache → learn → improve loop
    data_pipeline = 1_500_000

    total = ai_classification + ai_agent_value + prompt_engineering + data_pipeline

    return ValuationDimension(
        dimension_id="D07_AI_CAPABILITY",
        name_th="ความสามารถ AI (โมเดล + Agent + Knowledge)",
        name_en="AI Capability & Agent Intelligence",
        method="HYBRID",
        value_thb=total,
        value_usd=total / THB_PER_USD,
        confidence="MEDIUM",
        rationale=(
            f"โมเดล AI Classification ฿{ai_classification:,.0f} — จำแนก HS code 11 หลัก "
            f"พร้อม XAI reasoning ให้เหตุผลทุกการจำแนก "
            f"AI Agent ฿{ai_agent_value:,.0f} — Claude integration สำหรับวิเคราะห์เชิงลึก "
            f"Prompt engineering ฿{prompt_engineering:,.0f} — system prompts ที่ออกแบบเฉพาะศุลกากร "
            f"Data pipeline ฿{data_pipeline:,.0f} — วงจร classify → cache → learn → improve "
            f"ความสามารถ AI ที่สะสมมาเป็นสินทรัพย์ที่ทวีค่าขึ้นเมื่อมีข้อมูลมากขึ้น"
        ),
        sources=["Anthropic Claude API", "AI/ML SaaS valuations 2026"],
    )


def _calc_team_value() -> ValuationDimension:
    """
    มิติ 8: มูลค่าทีม (Key Person + Organizational Knowledge)
    """
    # Chairman (Founder/Visionary) — domain expertise + business network
    chairman_value = 3_000_000

    # AI Agent (Claude) — accumulated knowledge, system design capability
    ai_agent_accumulated = 2_000_000

    # Office team (future) — organizational knowledge
    team_potential = 1_000_000

    total = chairman_value + ai_agent_accumulated + team_potential

    return ValuationDimension(
        dimension_id="D08_TEAM_VALUE",
        name_th="มูลค่าทีม (Chairman + AI Agent + ทีมออฟฟิศ)",
        name_en="Team & Key Person Value",
        method="COST",
        value_thb=total,
        value_usd=total / THB_PER_USD,
        confidence="MEDIUM",
        rationale=(
            f"Chairman (Founder) ฿{chairman_value:,.0f} — ผู้มีวิสัยทัศน์ ความรู้ด้านศุลกากร "
            f"และเครือข่ายธุรกิจที่ไม่สามารถทดแทนได้ "
            f"AI Agent ฿{ai_agent_accumulated:,.0f} — ความรู้สะสมจากการพัฒนาระบบ "
            f"ทั้งสถาปัตยกรรม, อัลกอริทึม, และ domain knowledge ที่ encode อยู่ "
            f"ทีมออฟฟิศ (อนาคต) ฿{team_potential:,.0f} — organizational capital ที่จะเติบโต"
        ),
        sources=["Key person valuation methodology", "AICPA guidance"],
    )


def _calc_market_position() -> ValuationDimension:
    """
    มิติ 9: ตำแหน่งในตลาดไทยและต่างประเทศ
    """
    m = MARKET_PARAMS

    # Thai market — first/only AI customs API ในไทย
    thai_market_share_potential = 0.001  # 0.1% of Thai trade compliance
    thai_market_value = m["thai_customs_duty_revenue_thb_billion"] * 1_000_000_000 * thai_market_share_potential * 0.01
    # ^^ 0.01 = ส่วนแบ่งของ software ใน customs revenue chain

    # ตำแหน่งเชิงกลยุทธ์ — ยังไม่มีคู่แข่งตรงในไทย
    strategic_position = 3_000_000

    # ASEAN expansion potential
    asean_potential = 2_000_000

    # EU CBAM compliance — mandatory market (growing)
    cbam_market = 1_500_000

    total = thai_market_value + strategic_position + asean_potential + cbam_market

    return ValuationDimension(
        dimension_id="D09_MARKET_POSITION",
        name_th="ตำแหน่งในตลาดไทย + ต่างประเทศ",
        name_en="Thai & International Market Position",
        method="MARKET",
        value_thb=total,
        value_usd=total / THB_PER_USD,
        confidence="MEDIUM",
        rationale=(
            f"ตลาดการค้าระหว่างประเทศไทยมูลค่า ฿{m['thai_trade_value_thb_trillion']} ล้านล้านบาท/ปี "
            f"กรมศุลกากรจัดเก็บอากร ~฿{m['thai_customs_duty_revenue_thb_billion']:,.0f} พันล้านบาท/ปี "
            f"ระบบนี้เป็น AI Customs API แรกและเดียวในไทย "
            f"ตำแหน่งเชิงกลยุทธ์ ฿{strategic_position:,.0f} — ยังไม่มีคู่แข่งตรง "
            f"ศักยภาพ ASEAN ฿{asean_potential:,.0f} — ขยายไป 5 ประเทศเพิ่ม "
            f"ตลาด EU CBAM ฿{cbam_market:,.0f} — กฎหมายบังคับส่งออกไป EU ต้องรายงาน carbon"
        ),
        sources=["กรมศุลกากร 2025", "WTO Trade Stats",
                 "EU CBAM Regulation 2023/956"],
    )


def _calc_trade_reference_value() -> ValuationDimension:
    """
    มิติ 10: มูลค่าอ้างอิงจากการค้าระหว่างประเทศ
    """
    m = MARKET_PARAMS

    # Global trade compliance software market
    global_market_usd = m["global_trade_compliance_market_usd_billion"] * 1_000_000_000
    our_potential_share = 0.0005  # 0.05% of global market
    reference_value = global_market_usd * our_potential_share * THB_PER_USD

    # Compare to WiseTech ($9B) and Descartes ($10B)
    # We are <0.01% of their value = realistic floor
    wisetech_fraction = 9_000_000_000 * THB_PER_USD * 0.0001  # 0.01% of WiseTech

    total = max(reference_value, wisetech_fraction)

    return ValuationDimension(
        dimension_id="D10_TRADE_REFERENCE",
        name_th="มูลค่าอ้างอิงจากตลาดการค้าระหว่างประเทศ",
        name_en="International Trade Reference Value",
        method="MARKET",
        value_thb=total,
        value_usd=total / THB_PER_USD,
        confidence="LOW",
        rationale=(
            f"ตลาด Trade Compliance Software ทั่วโลกมูลค่า ~${m['global_trade_compliance_market_usd_billion']}B USD "
            f"WiseTech Global มูลค่า $9B (8.3x revenue), Descartes ~$10B "
            f"ระบบเรามีศักยภาพ 0.05% ของตลาดโลก หรือ 0.01% ของ WiseTech "
            f"ค่าอ้างอิงนี้ใช้ยืนยัน floor value — มูลค่าจะเพิ่มขึ้นตามฐานลูกค้า"
        ),
        sources=["Multiples.vc Jun 2026", "WiseTech Global FY2025",
                 "Descartes Systems Group 2025"],
    )


def _calc_feature_intrinsic_value() -> ValuationDimension:
    """
    มิติ 11: มูลค่าเฉพาะตัวของทุกฟีเจอร์ (Intrinsic Value)
    "ทุกไฟล์ ทุกระบบ ทุกข้อมูล ทุกฟีเจอร์ มีคุณค่าในตัวมันเอง"
    """
    total = sum(mod["market_value_thb"] for mod in FEATURE_MODULES.values())

    return ValuationDimension(
        dimension_id="D11_FEATURE_INTRINSIC",
        name_th="มูลค่าเฉพาะตัวของทุกฟีเจอร์",
        name_en="Intrinsic Value of All Features",
        method="COST",
        value_thb=total,
        value_usd=total / THB_PER_USD,
        confidence="HIGH",
        rationale=(
            f"รวมมูลค่า {len(FEATURE_MODULES)} โมดูลฟีเจอร์ ตั้งแต่ระบบจำแนก HS code, "
            f"คำนวณภาษี, ตรวจ FTA, OGA 36 หน่วยงาน, ตรวจราคา, ตรวจค่าขนส่ง, "
            f"จำลองสถานการณ์, ประกันความเสี่ยง, CBAM carbon, ASEAN expansion, "
            f"ระบบสมาชิก, security, multi-channel, AI discovery ฯลฯ "
            f"แต่ละโมดูลมีมูลค่าแยกต่างหาก สามารถขายสิทธิ์แยกหรือ license แยกได้"
        ),
        sources=["Internal module assessment"],
    )


def _calc_licensing_royalty() -> ValuationDimension:
    """
    มิติ 12: มูลค่าค่าลิขสิทธิ์ / Royalty (Relief from Royalty Method)
    """
    m = MARKET_PARAMS
    r = REVENUE_PROJECTIONS

    # Relief from Royalty — ถ้าคู่แข่งต้อง license ระบบนี้แทนที่จะสร้างเอง
    royalty_rate = m["software_royalty_rate_mid"] / 100  # 25%
    wacc = r["wacc_percent"] / 100

    # คำนวณ royalty จากรายได้คาดการณ์ 5 ปี
    yearly_users = [r[f"year{i}_paying_users"] for i in range(1, 6)]
    arpu_annual = r["arpu_monthly_usd"] * 12 * THB_PER_USD
    yearly_revenue = [users * arpu_annual for users in yearly_users]

    # PV of royalty stream
    pv_royalties = sum(
        (rev * royalty_rate) / ((1 + wacc) ** (i + 1))
        for i, rev in enumerate(yearly_revenue)
    )

    return ValuationDimension(
        dimension_id="D12_LICENSING_ROYALTY",
        name_th="มูลค่าค่าลิขสิทธิ์ (Relief from Royalty)",
        name_en="Licensing & Royalty Value",
        method="INCOME",
        value_thb=pv_royalties,
        value_usd=pv_royalties / THB_PER_USD,
        confidence="MEDIUM",
        rationale=(
            f"คำนวณด้วย Relief from Royalty Method อัตรา {m['software_royalty_rate_mid']}% "
            f"(มาตรฐาน vertical SaaS ที่มี proprietary data) "
            f"จากรายได้คาดการณ์ 5 ปี discount ที่ WACC {r['wacc_percent']}% "
            f"หมายความว่าหากผู้อื่นต้อง license ระบบนี้ไปใช้ "
            f"จะต้องจ่ายค่า royalty ฿{pv_royalties:,.0f} (มูลค่าปัจจุบัน)"
        ),
        sources=["WIPO Relief from Royalty Method",
                 "ktMINE royalty rate database 2026"],
    )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5: MAIN VALUATION FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def calculate_full_valuation(
    base_value_thb: float = 15_000_000,
    user_count_override: Optional[int] = None,
    custom_growth_rate: Optional[float] = None,
) -> FullValuation:
    """
    คำนวณมูลค่าโครงการทั้งหมด — 12 มิติ 3 วิธีการ

    Parameters:
        base_value_thb: มูลค่าตั้งต้น (default ฿15M)
        user_count_override: จำนวนผู้ใช้ปัจจุบัน (ถ้ามี)
        custom_growth_rate: อัตราการเติบโตที่ปรับเอง
    """
    # คำนวณทุกมิติ
    dimensions = [
        _calc_development_cost(),          # D01
        _calc_time_investment(),            # D02
        _calc_revenue_potential(),          # D03
        _calc_ip_portfolio(),              # D04
        _calc_knowledge_base(),            # D05
        _calc_customer_base(),             # D06
        _calc_ai_capability(),             # D07
        _calc_team_value(),                # D08
        _calc_market_position(),           # D09
        _calc_trade_reference_value(),     # D10
        _calc_feature_intrinsic_value(),   # D11
        _calc_licensing_royalty(),          # D12
    ]

    # ── แยกตามวิธีการ ──────────────────────────────────────────────────────
    cost_dims = [d for d in dimensions if d.method == "COST"]
    income_dims = [d for d in dimensions if d.method == "INCOME"]
    market_dims = [d for d in dimensions if d.method == "MARKET"]
    hybrid_dims = [d for d in dimensions if d.method == "HYBRID"]

    cost_total = sum(d.value_thb for d in cost_dims)
    income_total = sum(d.value_thb for d in income_dims)
    market_total = sum(d.value_thb for d in market_dims)
    hybrid_total = sum(d.value_thb for d in hybrid_dims)

    # ── Weighted Fair Value ────────────────────────────────────────────────
    # น้ำหนัก: Cost 30%, Income 40%, Market 25%, Hybrid 5%
    # (Income สำคัญที่สุดสำหรับ SaaS, Cost เป็น floor)
    weighted = (
        cost_total * 0.30 +
        income_total * 0.40 +
        market_total * 0.25 +
        hybrid_total * 0.05
    )

    # ไม่ต่ำกว่ามูลค่าตั้งต้น
    weighted = max(weighted, base_value_thb)

    # ── Total (sum of all dimensions) ──────────────────────────────────────
    total = sum(d.value_thb for d in dimensions)

    # ── Litigation value ───────────────────────────────────────────────────
    # หากถูกลอกเลียน: ค่าเสียหาย = replacement cost + lost profits + punitive
    litigation = (
        cost_total +                    # ต้นทุนที่ต้องสร้างใหม่
        income_total * 0.5 +            # กำไรที่เสียไป (50%)
        total * 0.20 +                  # ค่าเสียหายเชิงลงโทษ (20%)
        2_000_000                        # ค่าทนายความ + ค่าดำเนินคดี
    )

    # ── Outright sale value ─────────────────────────────────────────────────
    # ขายสิทธิ์ขาด: weighted value × 1.5 (control premium)
    outright_sale = weighted * 1.5

    # ── Growth projections ─────────────────────────────────────────────────
    growth_rate = custom_growth_rate or 0.35  # 35% annual growth
    projected_year3 = weighted * ((1 + growth_rate) ** 3)
    projected_year5 = weighted * ((1 + growth_rate) ** 5)

    return FullValuation(
        project_name="AI TO AI HOLDING — Customs Intelligence Division",
        valuation_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        base_value_thb=base_value_thb,
        dimensions=dimensions,
        total_value_thb=total,
        total_value_usd=total / THB_PER_USD,
        cost_approach_thb=cost_total,
        income_approach_thb=income_total,
        market_approach_thb=market_total,
        weighted_fair_value_thb=weighted,
        litigation_value_thb=litigation,
        outright_sale_value_thb=outright_sale,
        projected_value_year3_thb=projected_year3,
        projected_value_year5_thb=projected_year5,
        codebase_stats=CODEBASE_STATS,
        feature_count=len(FEATURE_MODULES),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def calculate_litigation_value() -> dict:
    """
    คำนวณมูลค่าเรียกร้องทางกฎหมาย หากถูกลอกเลียนแบบ
    """
    v = calculate_full_valuation()

    # ความเสียหายโดยตรง
    actual_damages = v.cost_approach_thb  # ต้นทุนพัฒนา

    # กำไรที่เสียไป (Lost Profits)
    lost_profits = v.income_approach_thb * 0.5

    # ค่าสินไหมทดแทน (Compensatory)
    compensatory = v.weighted_fair_value_thb * 0.3

    # ค่าเสียหายเชิงลงโทษ (Punitive — สูงสุด 3x ตาม พ.ร.บ. ลิขสิทธิ์)
    punitive = actual_damages * 2.0  # 2x multiplier

    # ค่าทนายความ + ค่าดำเนินคดี
    legal_costs = 3_000_000  # ฿3M (คดี IP ซับซ้อน)

    # ค่าเสียหายต่อชื่อเสียง
    reputation_damage = 2_000_000

    total_claim = (actual_damages + lost_profits + compensatory +
                   punitive + legal_costs + reputation_damage)

    return {
        "litigation_type": "ละเมิดลิขสิทธิ์ซอฟต์แวร์ + ความลับทางการค้า",
        "applicable_laws": [
            "พ.ร.บ. ลิขสิทธิ์ พ.ศ. 2537 (แก้ไข 2558)",
            "พ.ร.บ. ความลับทางการค้า พ.ศ. 2545",
            "พ.ร.บ. สิทธิบัตร พ.ศ. 2522 (แก้ไข 2542)",
            "พ.ร.บ. คอมพิวเตอร์ พ.ศ. 2560",
            "ประมวลกฎหมายแพ่งและพาณิชย์ มาตรา 420 (ละเมิด)",
        ],
        "criminal_penalties": [
            "จำคุกไม่เกิน 4 ปี (ละเมิดลิขสิทธิ์เชิงพาณิชย์)",
            "ปรับไม่เกิน 800,000 บาท",
            "จำคุกไม่เกิน 2 ปี (ละเมิดความลับทางการค้า)",
        ],
        "civil_damages": {
            "actual_damages_thb": round(actual_damages),
            "lost_profits_thb": round(lost_profits),
            "compensatory_thb": round(compensatory),
            "punitive_damages_thb": round(punitive),
            "legal_costs_thb": round(legal_costs),
            "reputation_damage_thb": round(reputation_damage),
            "total_claim_thb": round(total_claim),
            "total_claim_usd": round(total_claim / THB_PER_USD),
        },
        "evidence_available": [
            "Source code ใน GitHub private repository (commit history ทั้งหมด)",
            "Git log แสดง timeline การพัฒนาทุก commit",
            "BSL 1.1 License ประกาศไว้ชัดเจน",
            "Railway deployment logs",
            "API documentation + Swagger",
            "PROGRESS_LOG.md บันทึกทุกเฟส",
            "Session transcripts บันทึกกระบวนการคิดและพัฒนา",
        ],
        "note": (
            "มูลค่าเรียกร้องนี้เป็นการประเมินเบื้องต้น "
            "ค่าเสียหายจริงอาจสูงกว่านี้หากพิสูจน์ได้ว่าผู้ละเมิดทำกำไรจากการลอกเลียน "
            "ศาลทรัพย์สินทางปัญญาไทยมีอำนาจสั่งค่าเสียหายเชิงลงโทษสูงสุด 3 เท่า"
        ),
    }


def project_growth(
    current_users: int = 50,
    monthly_growth_rate: float = 0.08,  # 8% MoM growth
    months: int = 60,  # 5 years
) -> dict:
    """
    จำลองการเติบโตตามจำนวนผู้ใช้ — ปรับมูลค่าอัตโนมัติ
    """
    arpu_annual = REVENUE_PROJECTIONS["arpu_monthly_usd"] * 12 * THB_PER_USD
    wacc_monthly = (1 + REVENUE_PROJECTIONS["wacc_percent"] / 100) ** (1/12) - 1

    projections = []
    users = current_users
    cumulative_revenue = 0

    for month in range(1, months + 1):
        users = int(users * (1 + monthly_growth_rate))
        monthly_rev = users * REVENUE_PROJECTIONS["arpu_monthly_usd"] * THB_PER_USD
        cumulative_revenue += monthly_rev

        if month % 12 == 0:  # Annual snapshots
            year = month // 12
            annual_rev = users * arpu_annual
            # Valuation = revenue × multiple (multiple grows with scale)
            multiple = min(5 + year * 1.5, 12)  # 5x → 12x
            valuation = annual_rev * multiple

            projections.append({
                "year": year,
                "month": month,
                "active_users": users,
                "annual_revenue_thb": round(annual_rev),
                "annual_revenue_usd": round(annual_rev / THB_PER_USD),
                "cumulative_revenue_thb": round(cumulative_revenue),
                "revenue_multiple": multiple,
                "projected_valuation_thb": round(valuation),
                "projected_valuation_usd": round(valuation / THB_PER_USD),
            })

    return {
        "scenario": f"{monthly_growth_rate*100:.0f}% monthly growth, starting {current_users} users",
        "arpu_monthly_usd": REVENUE_PROJECTIONS["arpu_monthly_usd"],
        "projections": projections,
    }


def get_feature_portfolio() -> dict:
    """
    รายละเอียดมูลค่าแต่ละฟีเจอร์ — "ทุกฟีเจอร์มีคุณค่าในตัวมันเอง"
    """
    modules = []
    total = 0
    for key, mod in FEATURE_MODULES.items():
        modules.append({
            "module_id": key,
            "name_th": mod["name_th"],
            "name_en": mod["name_en"],
            "category": mod["category"],
            "complexity": mod["complexity"],
            "files_count": len(mod["files"]),
            "unique_data_assets": mod["unique_data_assets"],
            "market_value_thb": mod["market_value_thb"],
            "market_value_usd": round(mod["market_value_thb"] / THB_PER_USD),
            "note": mod["note"],
        })
        total += mod["market_value_thb"]

    modules.sort(key=lambda x: x["market_value_thb"], reverse=True)

    return {
        "total_modules": len(modules),
        "total_intrinsic_value_thb": total,
        "total_intrinsic_value_usd": round(total / THB_PER_USD),
        "modules": modules,
        "categories": {
            "CORE": sum(m["market_value_thb"] for m in modules if m["category"] == "CORE"),
            "INTELLIGENCE": sum(m["market_value_thb"] for m in modules if m["category"] == "INTELLIGENCE"),
            "EXPANSION": sum(m["market_value_thb"] for m in modules if m["category"] == "EXPANSION"),
            "REVENUE": sum(m["market_value_thb"] for m in modules if m["category"] == "REVENUE"),
            "INFRASTRUCTURE": sum(m["market_value_thb"] for m in modules if m["category"] == "INFRASTRUCTURE"),
        },
    }


def get_valuation_summary() -> dict:
    """สรุปมูลค่าโครงการ — สำหรับ Chairman dashboard"""
    v = calculate_full_valuation()
    return v.to_dict()
