"""
core/config.py
Environment configuration
เปิด Mock Mode: MOCK_MODE=true python app/main.py
เปิด Real Mode: MOCK_MODE=false python app/main.py  (ต้องมี Anthropic API key)
"""
import os

# ── Mode ──────────────────────────────────────────────────────
MOCK_MODE: bool = os.getenv("MOCK_MODE", "true").lower() == "true"

# ── Database ──────────────────────────────────────────────────
DB_PATH: str = os.getenv("DB_PATH", "holding.db")

# ── Pricing ───────────────────────────────────────────────────
PRICE_PER_ITEM: float = float(os.getenv("PRICE_PER_ITEM", "1.50"))
ENERGY_COST_PER_CALL: float = float(os.getenv("ENERGY_COST_PER_CALL", "0.02"))

# ── Confidence threshold ──────────────────────────────────────
LOW_CONFIDENCE_THRESHOLD: float = float(os.getenv("LOW_CONFIDENCE_THRESHOLD", "0.70"))
SANDBOX_ITEM_LIMIT: int = int(os.getenv("SANDBOX_ITEM_LIMIT", "3"))


def print_config():
    mode_label = "🟡 MOCK (no API calls)" if MOCK_MODE else "🟢 REAL (Claude API)"
    print(f"""
╔══════════════════════════════════════════╗
║       AI TO AI HOLDING — Config          ║
╠══════════════════════════════════════════╣
║  Mode          : {mode_label:<24}║
║  DB Path       : {DB_PATH:<24}║
║  Price/item    : ${PRICE_PER_ITEM:<23}║
║  Energy/call   : ${ENERGY_COST_PER_CALL:<23}║
║  Low conf      : {LOW_CONFIDENCE_THRESHOLD:<24}║
╚══════════════════════════════════════════╝
""")
