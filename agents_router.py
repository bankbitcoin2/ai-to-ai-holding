"""
agents_router.py
Agent Router — เลือก Mock หรือ Real ตาม MOCK_MODE
ทำหน้าที่แทน agents/__init__.py สำหรับ flat structure
"""
from holding_config import MOCK_MODE

if MOCK_MODE:
    from mock_classification_agent import classify_item, ClassificationResult
else:
    from classification_agent import classify_item, ClassificationResult

__all__ = ["classify_item", "ClassificationResult"]
