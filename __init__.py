"""
agents/__init__.py
Agent Router — เลือก Mock หรือ Real ตาม MOCK_MODE
ทุกที่ในโค้ดที่ import classify_item จะได้ตัวที่ถูกต้องอัตโนมัติ
ไม่ต้องแก้ไขไฟล์อื่นใด
"""
from holding_config import MOCK_MODE

if MOCK_MODE:
    from mock_classification_agent import classify_item, ClassificationResult
else:
    from classification_agent import classify_item, ClassificationResult

__all__ = ["classify_item", "ClassificationResult"]
