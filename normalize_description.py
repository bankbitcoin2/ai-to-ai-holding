# -*- coding: utf-8 -*-
"""
normalize_description.py — Product Description Normalizer
แปลงคำไทยทับศัพท์ / ชื่อแบรนด์ → canonical English form
"""
import re
from functools import lru_cache

# Compound phrases (longest first)
_COMPOUNDS = [
    ("\u0e41\u0e21\u0e04\u0e1a\u0e38\u0e4a\u0e04 \u0e41\u0e2d\u0e23\u0e4c", "macbook air"),
    ("\u0e41\u0e21\u0e04\u0e1a\u0e38\u0e49\u0e04 \u0e41\u0e2d\u0e23\u0e4c", "macbook air"),
    ("\u0e23\u0e2d\u0e07\u0e40\u0e17\u0e49\u0e32\u0e27\u0e34\u0e48\u0e07", "running shoes"),
    ("\u0e23\u0e2d\u0e07\u0e40\u0e17\u0e49\u0e32\u0e1c\u0e49\u0e32\u0e43\u0e1a", "sneakers"),
    ("\u0e23\u0e2d\u0e07\u0e40\u0e17\u0e49\u0e32\u0e2a\u0e49\u0e19\u0e2a\u0e39\u0e07", "high heels"),
    ("\u0e23\u0e2d\u0e07\u0e40\u0e17\u0e49\u0e32\u0e2a\u0e1b\u0e2d\u0e23\u0e4c\u0e15", "sports shoes"),
    ("\u0e23\u0e2d\u0e07\u0e40\u0e17\u0e49\u0e32\u0e41\u0e15\u0e30", "sandals"),
    ("\u0e23\u0e2d\u0e07\u0e40\u0e17\u0e49\u0e32\u0e2b\u0e19\u0e31\u0e07", "leather shoes"),
    ("\u0e23\u0e2d\u0e07\u0e40\u0e17\u0e49\u0e32", "shoes"),
    ("\u0e2b\u0e39\u0e1f\u0e31\u0e07\u0e1a\u0e25\u0e39\u0e17\u0e39\u0e18", "bluetooth earphone"),
    ("\u0e25\u0e33\u0e42\u0e1e\u0e07\u0e1a\u0e25\u0e39\u0e17\u0e39\u0e18", "bluetooth speaker"),
    ("\u0e2a\u0e21\u0e32\u0e23\u0e4c\u0e17\u0e42\u0e1f\u0e19", "smartphone"),
    ("\u0e2a\u0e21\u0e32\u0e23\u0e4c\u0e15\u0e42\u0e1f\u0e19", "smartphone"),
    ("\u0e42\u0e17\u0e23\u0e28\u0e31\u0e1e\u0e17\u0e4c\u0e21\u0e37\u0e2d\u0e16\u0e37\u0e2d", "mobile phone"),
    ("\u0e21\u0e37\u0e2d\u0e16\u0e37\u0e2d", "mobile phone"),
    ("\u0e42\u0e17\u0e23\u0e28\u0e31\u0e1e\u0e17\u0e4c", "telephone"),
    ("\u0e41\u0e1a\u0e15\u0e40\u0e15\u0e2d\u0e23\u0e35\u0e48", "battery"),
    ("\u0e2a\u0e32\u0e22\u0e0a\u0e32\u0e23\u0e4c\u0e08", "charging cable"),
    ("\u0e17\u0e35\u0e48\u0e0a\u0e32\u0e23\u0e4c\u0e08", "charger"),
    ("\u0e0a\u0e32\u0e23\u0e4c\u0e08\u0e40\u0e08\u0e2d\u0e23\u0e4c", "charger"),
    ("\u0e2a\u0e32\u0e22\u0e44\u0e1f", "cable"),
    ("\u0e40\u0e04\u0e23\u0e37\u0e48\u0e2d\u0e07\u0e0b\u0e31\u0e01\u0e1c\u0e49\u0e32", "washing machine"),
    ("\u0e15\u0e39\u0e49\u0e40\u0e22\u0e47\u0e19", "refrigerator"),
    ("\u0e44\u0e21\u0e42\u0e04\u0e23\u0e40\u0e27\u0e1f", "microwave oven"),
    ("\u0e40\u0e04\u0e23\u0e37\u0e48\u0e2d\u0e07\u0e14\u0e39\u0e14\u0e1d\u0e38\u0e48\u0e19", "vacuum cleaner"),
    ("\u0e40\u0e04\u0e23\u0e37\u0e48\u0e2d\u0e07\u0e1b\u0e23\u0e31\u0e1a\u0e2d\u0e32\u0e01\u0e32\u0e28", "air conditioner"),
    ("\u0e2b\u0e21\u0e49\u0e2d\u0e2b\u0e38\u0e07\u0e02\u0e49\u0e32\u0e27", "rice cooker"),
    ("\u0e01\u0e23\u0e30\u0e40\u0e1b\u0e4b\u0e32\u0e16\u0e37\u0e2d", "handbag"),
    ("\u0e01\u0e23\u0e30\u0e40\u0e1b\u0e4b\u0e32\u0e40\u0e14\u0e34\u0e19\u0e17\u0e32\u0e07", "luggage"),
    ("\u0e01\u0e23\u0e30\u0e40\u0e1b\u0e4b\u0e32\u0e2a\u0e30\u0e1e\u0e32\u0e22", "shoulder bag"),
    ("\u0e01\u0e23\u0e30\u0e40\u0e1b\u0e4b\u0e32\u0e40\u0e1b\u0e49", "backpack"),
    ("\u0e01\u0e23\u0e30\u0e40\u0e1b\u0e4b\u0e32", "bag"),
    ("\u0e19\u0e32\u0e2c\u0e34\u0e01\u0e32\u0e02\u0e49\u0e2d\u0e21\u0e37\u0e2d", "wristwatch"),
    ("\u0e19\u0e32\u0e2c\u0e34\u0e01\u0e32", "watch"),
    ("\u0e41\u0e27\u0e48\u0e19\u0e01\u0e31\u0e19\u0e41\u0e14\u0e14", "sunglasses"),
    ("\u0e41\u0e27\u0e48\u0e19\u0e15\u0e32", "eyeglasses"),
    ("\u0e2d\u0e32\u0e2b\u0e32\u0e23\u0e40\u0e2a\u0e23\u0e34\u0e21", "food supplement"),
    ("\u0e19\u0e49\u0e33\u0e1c\u0e25\u0e44\u0e21\u0e49", "fruit juice"),
    ("\u0e19\u0e49\u0e33\u0e21\u0e31\u0e19\u0e40\u0e04\u0e23\u0e37\u0e48\u0e2d\u0e07", "engine oil"),
    ("\u0e2d\u0e30\u0e44\u0e2b\u0e25\u0e48\u0e23\u0e16", "auto parts"),
    ("\u0e22\u0e32\u0e07\u0e23\u0e16\u0e22\u0e19\u0e15\u0e4c", "car tyre"),
    ("\u0e22\u0e32\u0e07\u0e18\u0e23\u0e23\u0e21\u0e0a\u0e32\u0e15\u0e34", "natural rubber"),
    ("\u0e22\u0e32\u0e07", "rubber"),
    ("\u0e41\u0e1a\u0e15\u0e40\u0e15\u0e2d\u0e23\u0e35\u0e48\u0e23\u0e16\u0e22\u0e19\u0e15\u0e4c", "car battery"),
    ("\u0e23\u0e16\u0e22\u0e19\u0e15\u0e4c", "automobile"),
    ("\u0e2b\u0e19\u0e49\u0e32\u0e01\u0e32\u0e01\u0e2d\u0e19\u0e32\u0e21\u0e31\u0e22", "surgical mask"),
    ("\u0e22\u0e32\u0e2a\u0e35\u0e1f\u0e31\u0e19", "toothpaste"),
    ("\u0e19\u0e49\u0e33\u0e2b\u0e2d\u0e21", "perfume"),
    # ── อาหาร/เครื่องดื่ม/ยานยนต์/สิ่งทอ/เคมี/ยา ──────
    ("\u0e19\u0e49\u0e33\u0e2d\u0e31\u0e14\u0e25\u0e21", "carbonated drink"),
    ("\u0e19\u0e49\u0e33\u0e21\u0e31\u0e19\u0e1e\u0e37\u0e0a", "vegetable oil"),
    ("\u0e19\u0e49\u0e33\u0e21\u0e31\u0e19\u0e1b\u0e32\u0e25\u0e4c\u0e21", "palm oil"),
    ("\u0e19\u0e49\u0e33\u0e21\u0e31\u0e19\u0e21\u0e30\u0e1e\u0e23\u0e49\u0e32\u0e27", "coconut oil"),
    ("\u0e2d\u0e32\u0e2b\u0e32\u0e23\u0e2a\u0e31\u0e15\u0e27\u0e4c", "pet food"),
    ("\u0e40\u0e19\u0e37\u0e49\u0e2d\u0e27\u0e31\u0e27", "beef"),
    ("\u0e40\u0e19\u0e37\u0e49\u0e2d\u0e2b\u0e21\u0e39", "pork"),
    ("\u0e40\u0e19\u0e37\u0e49\u0e2d\u0e44\u0e01\u0e48", "chicken meat"),
    ("\u0e40\u0e19\u0e37\u0e49\u0e2d\u0e41\u0e01\u0e30", "mutton"),
    ("\u0e1b\u0e25\u0e32\u0e2a\u0e14", "fresh fish"),
    ("\u0e19\u0e21\u0e1c\u0e07", "milk powder"),
    ("\u0e19\u0e21\u0e2a\u0e14", "fresh milk"),
    ("\u0e44\u0e02\u0e48\u0e44\u0e01\u0e48", "chicken egg"),
    ("\u0e23\u0e16\u0e22\u0e19\u0e15\u0e4c\u0e44\u0e1f\u0e1f\u0e49\u0e32", "electric vehicle"),
    ("\u0e40\u0e04\u0e23\u0e37\u0e48\u0e2d\u0e07\u0e22\u0e19\u0e15\u0e4c", "engine"),
    ("\u0e01\u0e23\u0e2d\u0e07\u0e2d\u0e32\u0e01\u0e32\u0e28", "air filter"),
    ("\u0e1b\u0e38\u0e4b\u0e22\u0e40\u0e04\u0e21\u0e35", "chemical fertilizer"),
    ("\u0e22\u0e32\u0e06\u0e48\u0e32\u0e41\u0e21\u0e25\u0e07", "pesticide"),
    ("\u0e22\u0e32\u0e06\u0e48\u0e32\u0e27\u0e31\u0e0a\u0e1e\u0e37\u0e0a", "herbicide"),
    ("\u0e41\u0e1c\u0e07\u0e42\u0e0b\u0e25\u0e32\u0e23\u0e4c\u0e40\u0e0b\u0e25\u0e25\u0e4c", "solar panel"),
    ("\u0e2d\u0e38\u0e1b\u0e01\u0e23\u0e13\u0e4c\u0e41\u0e1e\u0e17\u0e22\u0e4c", "medical equipment"),
    ("\u0e40\u0e04\u0e23\u0e37\u0e48\u0e2d\u0e07\u0e21\u0e37\u0e2d\u0e41\u0e1e\u0e17\u0e22\u0e4c", "medical device"),
    ("\u0e1c\u0e49\u0e32\u0e1d\u0e49\u0e32\u0e22", "cotton fabric"),
    ("\u0e40\u0e2a\u0e37\u0e49\u0e2d\u0e01\u0e31\u0e19\u0e2b\u0e19\u0e32\u0e27", "winter jacket"),
    ("\u0e40\u0e2a\u0e37\u0e49\u0e2d\u0e2a\u0e27\u0e21\u0e2b\u0e21\u0e27\u0e01", "hoodie"),
    ("\u0e0a\u0e38\u0e14\u0e0a\u0e31\u0e49\u0e19\u0e43\u0e19", "underwear"),
    ("\u0e04\u0e23\u0e35\u0e21\u0e01\u0e31\u0e19\u0e41\u0e14\u0e14", "sunscreen"),
    ("\u0e04\u0e23\u0e35\u0e21\u0e1a\u0e33\u0e23\u0e38\u0e07\u0e1c\u0e34\u0e27", "skin cream"),
    ("\u0e04\u0e23\u0e35\u0e21\u0e1a\u0e33\u0e23\u0e38\u0e07\u0e1c\u0e21", "hair conditioner"),
    ("\u0e22\u0e32\u0e1b\u0e0f\u0e34\u0e0a\u0e35\u0e27\u0e19\u0e30", "antibiotic"),
    ("\u0e22\u0e32\u0e41\u0e01\u0e49\u0e1b\u0e27\u0e14", "painkiller"),
    ("\u0e2d\u0e32\u0e2b\u0e32\u0e23\u0e40\u0e2a\u0e23\u0e34\u0e21\u0e42\u0e1b\u0e23\u0e15\u0e35\u0e19", "protein supplement"),
]

# Single words
_SINGLES = [
    ("\u0e44\u0e2d\u0e42\u0e1f\u0e19", "iphone"),
    ("\u0e44\u0e2d\u0e41\u0e1e\u0e14", "ipad"),
    ("\u0e44\u0e2d\u0e41\u0e21\u0e04", "imac"),
    ("\u0e41\u0e21\u0e04\u0e1a\u0e38\u0e4a\u0e04", "macbook"),
    ("\u0e41\u0e21\u0e04\u0e1a\u0e38\u0e49\u0e04", "macbook"),
    ("\u0e41\u0e2d\u0e1b\u0e40\u0e1b\u0e34\u0e49\u0e25", "apple"),
    ("\u0e41\u0e2d\u0e1b\u0e40\u0e1b\u0e34\u0e25", "apple"),
    ("\u0e01\u0e32\u0e41\u0e25\u0e47\u0e01\u0e0b\u0e35\u0e48", "galaxy"),
    ("\u0e0b\u0e31\u0e21\u0e0b\u0e38\u0e07", "samsung"),
    ("\u0e0b\u0e31\u0e21\u0e0b\u0e31\u0e07", "samsung"),
    ("\u0e2b\u0e31\u0e27\u0e40\u0e27\u0e48\u0e22", "huawei"),
    ("\u0e42\u0e2d\u0e1b\u0e42\u0e1b\u0e49", "oppo"),
    ("\u0e27\u0e35\u0e42\u0e27\u0e48", "vivo"),
    ("\u0e42\u0e19\u0e40\u0e01\u0e35\u0e22", "nokia"),
    ("\u0e42\u0e0b\u0e19\u0e35\u0e48", "sony"),
    ("\u0e41\u0e2d\u0e25\u0e08\u0e35", "lg"),
    ("\u0e1e\u0e32\u0e19\u0e32\u0e42\u0e0b\u0e19\u0e34\u0e04", "panasonic"),
    ("\u0e42\u0e15\u0e0a\u0e34\u0e1a\u0e32", "toshiba"),
    ("\u0e41\u0e25\u0e47\u0e1b\u0e17\u0e47\u0e2d\u0e1b", "laptop"),
    ("\u0e41\u0e25\u0e47\u0e1b\u0e17\u0e49\u0e2d\u0e1b", "laptop"),
    ("\u0e42\u0e19\u0e49\u0e15\u0e1a\u0e38\u0e4a\u0e04", "notebook"),
    ("\u0e42\u0e19\u0e49\u0e15\u0e1a\u0e38\u0e4a\u0e01", "notebook"),
    ("\u0e04\u0e2d\u0e21\u0e1e\u0e34\u0e27\u0e40\u0e15\u0e2d\u0e23\u0e4c", "computer"),
    ("\u0e04\u0e2d\u0e21\u0e1e\u0e4c", "computer"),
    ("\u0e41\u0e17\u0e47\u0e1a\u0e40\u0e25\u0e47\u0e15", "tablet"),
    ("\u0e1a\u0e25\u0e39\u0e17\u0e39\u0e18", "bluetooth"),
    ("\u0e25\u0e33\u0e42\u0e1e\u0e07", "speaker"),
    ("\u0e01\u0e25\u0e49\u0e2d\u0e07", "camera"),
    ("\u0e17\u0e35\u0e27\u0e35", "television"),
    ("\u0e42\u0e17\u0e23\u0e17\u0e31\u0e28\u0e19\u0e4c", "television"),
    ("\u0e42\u0e1b\u0e23\u0e40\u0e08\u0e04\u0e40\u0e15\u0e2d\u0e23\u0e4c", "projector"),
    ("\u0e42\u0e14\u0e23\u0e19", "drone"),
    ("\u0e42\u0e14\u0e23\u0e13", "drone"),
    ("\u0e40\u0e23\u0e32\u0e40\u0e15\u0e2d\u0e23\u0e4c", "router"),
    ("\u0e1e\u0e23\u0e34\u0e49\u0e19\u0e40\u0e15\u0e2d\u0e23\u0e4c", "printer"),
    ("\u0e40\u0e21\u0e32\u0e2a\u0e4c", "mouse"),
    ("\u0e2b\u0e39\u0e1f\u0e31\u0e07", "earphone"),
    ("\u0e41\u0e1a\u0e15", "battery"),
    ("\u0e40\u0e04\u0e40\u0e1a\u0e34\u0e25", "cable"),
    ("\u0e19\u0e34\u0e49\u0e27", "inch"),
    ("\u0e40\u0e21\u0e15\u0e23", "meter"),
    ("\u0e01\u0e34\u0e42\u0e25\u0e01\u0e23\u0e31\u0e21", "kg"),
    ("\u0e01\u0e34\u0e42\u0e25", "kg"),
    ("\u0e42\u0e1b\u0e23\u0e15\u0e35\u0e19", "protein"),
    ("\u0e42\u0e1b\u0e23", "pro"),
    ("\u0e41\u0e21\u0e01\u0e0b\u0e4c", "max"),
    ("\u0e41\u0e21\u0e47\u0e01\u0e0b\u0e4c", "max"),
    ("\u0e41\u0e21\u0e47\u0e01\u0e0b\u0e4c", "max"),
    ("\u0e21\u0e34\u0e19\u0e34", "mini"),
    ("\u0e2d\u0e31\u0e25\u0e15\u0e23\u0e49\u0e32", "ultra"),
    ("\u0e1e\u0e25\u0e31\u0e2a", "plus"),
    ("\u0e44\u0e25\u0e17\u0e4c", "lite"),
    ("\u0e44\u0e19\u0e01\u0e35\u0e49", "nike"),
    ("\u0e2d\u0e32\u0e14\u0e34\u0e14\u0e32\u0e2a", "adidas"),
    ("\u0e1e\u0e39\u0e21\u0e48\u0e32", "puma"),
    ("\u0e40\u0e2a\u0e37\u0e49\u0e2d\u0e22\u0e37\u0e14", "t-shirt"),
    ("\u0e40\u0e2a\u0e37\u0e49\u0e2d\u0e40\u0e0a\u0e34\u0e49\u0e15", "shirt"),
    ("\u0e40\u0e2a\u0e37\u0e49\u0e2d", "shirt"),
    ("\u0e01\u0e32\u0e07\u0e40\u0e01\u0e07", "pants"),
    ("\u0e41\u0e08\u0e47\u0e04\u0e40\u0e01\u0e47\u0e15", "jacket"),
    ("\u0e27\u0e34\u0e15\u0e32\u0e21\u0e34\u0e19", "vitamin"),
    ("\u0e01\u0e32\u0e41\u0e1f", "coffee"),
    ("\u0e19\u0e21", "milk"),
    ("\u0e08\u0e31\u0e01\u0e23\u0e22\u0e32\u0e19", "bicycle"),
    ("\u0e2a\u0e01\u0e39\u0e15\u0e40\u0e15\u0e2d\u0e23\u0e4c", "scooter"),
    ("\u0e02\u0e2d\u0e07\u0e40\u0e25\u0e48\u0e19", "toy"),
    ("\u0e15\u0e38\u0e4a\u0e01\u0e15\u0e32", "doll"),
    ("\u0e2b\u0e38\u0e48\u0e19\u0e22\u0e19\u0e15\u0e4c", "robot"),
    ("\u0e04\u0e23\u0e35\u0e21", "cream"),
    ("\u0e25\u0e34\u0e1b\u0e2a\u0e15\u0e34\u0e01", "lipstick"),
    ("\u0e41\u0e0a\u0e21\u0e1e\u0e39", "shampoo"),
    ("\u0e2a\u0e1a\u0e39\u0e48", "soap"),
    ("\u0e22\u0e32", "medicine"),
    ("\u0e41\u0e2d\u0e23\u0e4c", "air conditioner"),
    # ── อาหาร/ยานยนต์/วัสดุ/เสื้อผ้า/เคมี/กีฬา ──────
    ("\u0e02\u0e49\u0e32\u0e27", "rice"),
    ("\u0e41\u0e1b\u0e49\u0e07", "flour"),
    ("\u0e40\u0e01\u0e25\u0e37\u0e2d", "salt"),
    ("\u0e1e\u0e23\u0e34\u0e01", "chilli"),
    ("\u0e01\u0e38\u0e49\u0e07", "shrimp"),
    ("\u0e1b\u0e25\u0e32", "fish"),
    ("\u0e27\u0e31\u0e27", "cattle"),
    ("\u0e1c\u0e25\u0e44\u0e21\u0e49", "fruit"),
    ("\u0e1c\u0e31\u0e01", "vegetable"),
    ("\u0e1b\u0e38\u0e4b\u0e22", "fertilizer"),
    ("\u0e21\u0e2d\u0e40\u0e15\u0e2d\u0e23\u0e4c\u0e44\u0e0b\u0e04\u0e4c", "motorcycle"),
    ("\u0e2a\u0e01\u0e39\u0e15\u0e40\u0e15\u0e2d\u0e23\u0e4c", "scooter"),
    ("\u0e2d\u0e30\u0e44\u0e2b\u0e25\u0e48", "spare parts"),
    ("\u0e1e\u0e25\u0e32\u0e2a\u0e15\u0e34\u0e01", "plastic"),
    ("\u0e2d\u0e30\u0e25\u0e39\u0e21\u0e34\u0e40\u0e19\u0e35\u0e22\u0e21", "aluminium"),
    ("\u0e17\u0e2d\u0e07\u0e41\u0e14\u0e07", "copper"),
    ("\u0e2a\u0e31\u0e07\u0e01\u0e30\u0e2a\u0e35", "zinc"),
    ("\u0e40\u0e04\u0e23\u0e37\u0e48\u0e2d\u0e07\u0e08\u0e31\u0e01\u0e23", "machine"),
    ("\u0e1b\u0e31\u0e4a\u0e21", "pump"),
    ("\u0e16\u0e38\u0e07\u0e40\u0e17\u0e49\u0e32", "socks"),
    ("\u0e16\u0e38\u0e07\u0e21\u0e37\u0e2d", "gloves"),
    ("\u0e2b\u0e21\u0e27\u0e01", "cap"),
    ("\u0e40\u0e02\u0e47\u0e21\u0e02\u0e31\u0e14", "belt"),
    ("\u0e04\u0e23\u0e35\u0e21", "cream"),
    ("\u0e42\u0e25\u0e0a\u0e31\u0e48\u0e19", "lotion"),
    ("\u0e40\u0e0b\u0e23\u0e31\u0e21", "serum"),
    ("\u0e2a\u0e40\u0e1b\u0e23\u0e22\u0e4c", "spray"),
    ("\u0e41\u0e04\u0e1b\u0e0b\u0e39\u0e25", "capsule"),
    ("\u0e08\u0e31\u0e01\u0e23\u0e22\u0e32\u0e19", "bicycle"),
    ("\u0e2d\u0e38\u0e1b\u0e01\u0e23\u0e13\u0e4c\u0e01\u0e35\u0e2c\u0e32", "sports equipment"),
]


# ── Chinese (ZH) Compound phrases — longest first ─────────────────────────────
_ZH_COMPOUNDS = [
    # Electronics
    ("笔记本电脑",  "laptop"),
    ("平板电脑",    "tablet"),
    ("智能手机",    "smartphone"),
    ("蓝牙耳机",    "bluetooth earphone"),
    ("蓝牙音箱",    "bluetooth speaker"),
    ("无线耳机",    "wireless earphone"),
    ("充电宝",      "power bank"),
    ("太阳能板",    "solar panel"),
    ("空气净化器",  "air purifier"),
    ("洗衣机",      "washing machine"),
    ("电冰箱",      "refrigerator"),
    ("微波炉",      "microwave oven"),
    ("电视机",      "television"),
    ("空调机",      "air conditioner"),
    # Food & Agriculture
    ("天然橡胶",    "natural rubber"),
    ("椰子油",      "coconut oil"),
    ("棕榈油",      "palm oil"),
    ("辣椒酱",      "chili sauce"),
    ("鱼露",        "fish sauce"),
    ("椰子水",      "coconut water"),
    ("菠萝罐头",    "canned pineapple"),
    ("金枪鱼",      "tuna"),
    ("罗非鱼",      "tilapia"),
    # Vehicles
    ("电动汽车",    "electric vehicle"),
    ("汽车零件",    "auto parts"),
    ("汽车配件",    "auto parts"),
    ("摩托车",      "motorcycle"),
    # Medical / PPE
    ("外科口罩",    "surgical mask"),
    ("医用手套",    "medical gloves"),
    ("手术手套",    "surgical gloves"),
    ("乳胶手套",    "latex gloves"),
    ("橡胶手套",    "rubber gloves"),
    ("一次性手套",  "disposable gloves"),
    ("抗生素",      "antibiotic"),
    # Cosmetics
    ("防晒霜",      "sunscreen"),
    ("润肤霜",      "moisturizer"),
    ("洗发水",      "shampoo"),
    ("护发素",      "conditioner"),
    ("沐浴露",      "shower gel"),
    # Textiles
    ("棉布",        "cotton fabric"),
    ("运动鞋",      "sports shoes"),
    ("牛仔裤",      "jeans"),
    ("T恤",         "t-shirt"),
    ("羊毛衫",      "woollen sweater"),
    ("羽绒服",      "down jacket"),
    # Gems / Precious metals
    ("黄金首饰",    "gold jewelry"),
    ("钻石戒指",    "diamond ring"),
]

# ── Chinese (ZH) Single words ─────────────────────────────────────────────────
_ZH_SINGLES = [
    # Electronics
    ("电脑",    "computer"),
    ("手机",    "mobile phone"),
    ("耳机",    "earphone"),
    ("充电器",  "charger"),
    ("电池",    "battery"),
    ("键盘",    "keyboard"),
    ("鼠标",    "mouse"),
    ("显示器",  "monitor"),
    ("打印机",  "printer"),
    ("相机",    "camera"),
    ("电视",    "television"),
    ("空调",    "air conditioner"),
    # Food & Agri
    ("大米",    "rice"),
    ("橡胶",    "rubber"),
    ("木薯",    "cassava"),
    ("虾",      "shrimp"),
    ("菠萝",    "pineapple"),
    ("芒果",    "mango"),
    ("榴莲",    "durian"),
    ("龙眼",    "longan"),
    ("木瓜",    "papaya"),
    ("香蕉",    "banana"),
    ("椰子",    "coconut"),
    ("咖啡",    "coffee"),
    ("茶叶",    "tea"),
    ("糖",      "sugar"),
    ("盐",      "salt"),
    # Vehicles & Parts
    ("汽车",    "car"),
    ("轮胎",    "car tyre"),
    ("自行车",  "bicycle"),
    ("发动机",  "engine"),
    # Chemicals / Raw materials
    ("化肥",    "fertilizer"),
    ("农药",    "pesticide"),
    ("塑料",    "plastic"),
    ("钢铁",    "steel"),
    ("铜",      "copper"),
    ("铝",      "aluminium"),
    ("木材",    "timber"),
    ("纸张",    "paper"),
    # Textiles
    ("棉花",    "cotton"),
    ("棉",      "cotton"),
    ("丝绸",    "silk"),
    ("纺织品",  "textile"),
    ("服装",    "clothing"),
    ("鞋",      "shoes"),
    ("手套",    "gloves"),
    ("口罩",    "face mask"),
    ("帽子",    "hat"),
    ("袜子",    "socks"),
    # Cosmetics / Health
    ("化妆品",  "cosmetics"),
    ("香皂",    "soap"),
    ("牙膏",    "toothpaste"),
    ("维生素",  "vitamin"),
    ("药",      "medicine"),
    # Gems
    ("钻石",    "diamond"),
    ("黄金",    "gold"),
    ("宝石",    "gemstone"),
    ("珠宝",    "jewelry"),
]

# ── Japanese (JA) Compound phrases — longest first ────────────────────────────
_JA_COMPOUNDS = [
    # Electronics
    ("ノートパソコン",      "laptop"),
    ("タブレット端末",      "tablet"),
    ("スマートフォン",      "smartphone"),
    ("ブルートゥースイヤホン", "bluetooth earphone"),
    ("ワイヤレスイヤホン",  "wireless earphone"),
    ("モバイルバッテリー",  "power bank"),
    ("太陽光パネル",        "solar panel"),
    ("空気清浄機",          "air purifier"),
    ("洗濯機",              "washing machine"),
    ("冷蔵庫",              "refrigerator"),
    ("電子レンジ",          "microwave oven"),
    ("エアコン",            "air conditioner"),
    # Food & Agriculture
    ("天然ゴム",            "natural rubber"),
    ("ヤシ油",              "palm oil"),
    ("ココナッツオイル",    "coconut oil"),
    ("フィッシュソース",    "fish sauce"),
    ("唐辛子ソース",        "chili sauce"),
    ("缶詰パイナップル",    "canned pineapple"),
    # Vehicles
    ("電気自動車",          "electric vehicle"),
    ("自動車部品",          "auto parts"),
    ("自動車零部品",        "auto parts"),
    ("オートバイ",          "motorcycle"),
    # Medical / PPE
    ("サージカルマスク",    "surgical mask"),
    ("医療用手袋",          "medical gloves"),
    ("ラテックス手袋",      "latex gloves"),
    ("使い捨て手袋",        "disposable gloves"),
    ("抗生物質",            "antibiotic"),
    ("ビタミン剤",          "vitamin supplement"),
    # Cosmetics
    ("日焼け止め",          "sunscreen"),
    ("保湿クリーム",        "moisturizer"),
    ("ヘアコンディショナー","conditioner"),
    ("ボディソープ",        "shower gel"),
    # Textiles
    ("綿布",                "cotton fabric"),
    ("スポーツシューズ",    "sports shoes"),
    ("ジーンズ",            "jeans"),
    ("Tシャツ",             "t-shirt"),
    ("ダウンジャケット",    "down jacket"),
    # Gems
    ("ダイヤモンドリング",  "diamond ring"),
    ("金製品",              "gold product"),
]

# ── Japanese (JA) Single words ────────────────────────────────────────────────
_JA_SINGLES = [
    # Electronics
    ("パソコン",    "computer"),
    ("スマホ",      "smartphone"),
    ("携帯電話",    "mobile phone"),
    ("イヤホン",    "earphone"),
    ("充電器",      "charger"),
    ("バッテリー",  "battery"),
    ("キーボード",  "keyboard"),
    ("マウス",      "mouse"),
    ("モニター",    "monitor"),
    ("プリンター",  "printer"),
    ("カメラ",      "camera"),
    ("テレビ",      "television"),
    # Food & Agri
    ("お米",        "rice"),
    ("米",          "rice"),
    ("ゴム",        "rubber"),
    ("タピオカ",    "tapioca"),
    ("エビ",        "shrimp"),
    ("海老",        "shrimp"),
    ("まぐろ",      "tuna"),
    ("マグロ",      "tuna"),
    ("パイナップル","pineapple"),
    ("マンゴー",    "mango"),
    ("ドリアン",    "durian"),
    ("バナナ",      "banana"),
    ("ヤシ",        "coconut palm"),
    ("コーヒー",    "coffee"),
    ("お茶",        "tea"),
    ("砂糖",        "sugar"),
    # Vehicles & Parts
    ("自動車",      "car"),
    ("バイク",      "motorcycle"),
    ("タイヤ",      "car tyre"),
    ("自転車",      "bicycle"),
    ("エンジン",    "engine"),
    # Chemicals / Raw materials
    ("化学肥料",    "fertilizer"),
    ("農薬",        "pesticide"),
    ("プラスチック","plastic"),
    ("鉄鋼",        "steel"),
    ("銅",          "copper"),
    ("アルミ",      "aluminium"),
    ("木材",        "timber"),
    ("紙",          "paper"),
    # Textiles
    ("綿",          "cotton"),
    ("シルク",      "silk"),
    ("繊維",        "textile"),
    ("衣類",        "clothing"),
    ("靴",          "shoes"),
    ("手袋",        "gloves"),
    ("マスク",      "face mask"),
    ("帽子",        "hat"),
    ("靴下",        "socks"),
    # Cosmetics / Health
    ("化粧品",      "cosmetics"),
    ("石鹸",        "soap"),
    ("歯磨き粉",    "toothpaste"),
    ("シャンプー",  "shampoo"),
    ("ビタミン",    "vitamin"),
    ("薬",          "medicine"),
    # Gems
    ("ダイヤモンド","diamond"),
    ("金",          "gold"),
    ("宝石",        "gemstone"),
    ("ジュエリー",  "jewelry"),
]

_NOISE = re.compile(
    r'\b(pcs|pieces?|units?|sets?|pack|packs?|new|original|genuine|sale|discount)\b',
    re.IGNORECASE,
)

@lru_cache(maxsize=4096)
def normalize(description: str) -> str:
    if not description:
        return ""
    text = description.strip()
    # Thai
    for th, en in _COMPOUNDS:
        text = text.replace(th, en)
    for th, en in _SINGLES:
        text = text.replace(th, en)
    # Chinese
    for zh, en in _ZH_COMPOUNDS:
        text = text.replace(zh, en)
    for zh, en in _ZH_SINGLES:
        text = text.replace(zh, en)
    # Japanese
    for ja, en in _JA_COMPOUNDS:
        text = text.replace(ja, en)
    for ja, en in _JA_SINGLES:
        text = text.replace(ja, en)
    text = text.lower()
    text = _NOISE.sub("", text)
    # strip remaining Thai chars
    text = re.sub(r'[\u0e00-\u0e7f]+', " ", text)
    # strip remaining CJK / Hiragana / Katakana / full-width
    text = re.sub(r'[\u3000-\u9fff\uff00-\uffef]+', " ", text)
    text = re.sub(r'[^\w\s\-\.]', " ", text)
    text = re.sub(r'\s+', " ", text).strip()
    return text

def normalize_for_cache_key(description: str, origin_country: str = "") -> str:
        return normalize(description) + '|' + (origin_country or '').upper().strip()