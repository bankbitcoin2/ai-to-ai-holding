"""
cache_key_utils.py — Single source of truth สำหรับ cache key generation

ใช้ที่นี่ที่เดียว — ทั้ง cache_service.py และ cache_classification.py import จากที่นี่
อยากเปลี่ยน hash logic ในอนาคต → แก้ที่ไฟล์นี้ไฟล์เดียว ระบบทั้งหมดจะตาม

กฎสำคัญ:
- HS Code ไม่ขึ้นกับ origin_country → key ใช้แค่ description
- ผ่าน normalize() ก่อนเสมอ → จีน/ญี่ปุ่น/ไทย ที่พิมพ์สินค้าเดียวกัน = key เดียวกัน
"""
import hashlib


def make_cache_key(description: str) -> str:
    """
    Canonical HS classification cache key
    = sha256(normalize(description))

    ตัวอย่าง:
        make_cache_key("笔记本电脑") == make_cache_key("ノートパソコン")
        make_cache_key("แล็ปท็อป")  == make_cache_key("laptop")
        → ทุก query ที่หมายถึง laptop → key เดียวกัน → hit cache เดียวกัน
    """
    try:
        from normalize_description import normalize
        norm = normalize(description)
    except Exception:
        norm = description.lower().strip()
    if not norm:
        norm = description.lower().strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()
