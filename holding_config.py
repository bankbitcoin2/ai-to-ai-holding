"""
core/config.py
Environment configuration
"""
import os
from pathlib import Path

# Mode
MOCK_MODE: bool = os.getenv("MOCK_MODE", "true").lower() == "true"

# Database - [FIX-7] absolute path
_THIS_DIR = Path(__file__).parent.resolve()
_DB_DEFAULT = str(_THIS_DIR / "holding.db")
DB_PATH: str = os.getenv("DB_PATH", _DB_DEFAULT)
if not os.path.isabs(DB_PATH):
    DB_PATH = str(Path(DB_PATH).resolve())

# Pricing
PRICE_PER_ITEM: float = float(os.getenv("PRICE_PER_ITEM", "0.15"))
ENERGY_COST_PER_CALL: float = float(os.getenv("ENERGY_COST_PER_CALL", "0.02"))

# Confidence threshold
LOW_CONFIDENCE_THRESHOLD: float = float(os.getenv("LOW_CONFIDENCE_THRESHOLD", "0.70"))
SANDBOX_ITEM_LIMIT: int = int(os.getenv("SANDBOX_ITEM_LIMIT", "3"))

# CORS - [FIX-3] no wildcard
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080")
ALLOWED_ORIGINS: list = [o.strip() for o in _raw_origins.split(",") if o.strip()]

# Security status
HAS_API_KEYS: bool = bool(os.getenv("API_KEYS", "").strip())
CHAIRMAN_IPS: str = os.getenv("CHAIRMAN_ALLOWED_IPS", "127.0.0.1,::1")


def print_config():
    mode_label = "MOCK (no API calls)" if MOCK_MODE else "REAL (Claude API)"
    api_key_label = "Set" if HAS_API_KEYS else "NOT SET (dev key active)"
    print(f"[CONFIG] Mode={mode_label} | DB={DB_PATH} | API_KEYS={api_key_label} | ChairmanIP={CHAIRMAN_IPS}")
