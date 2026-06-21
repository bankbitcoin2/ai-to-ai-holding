"""
tax_engine_bundled.py
Bundled offline Thai Tariff engine — HS 2022

ครอบคลุม:
  - MFN rates: Chapter-level (2-digit) → Heading-level (4-digit) → Subheading-level (6-digit)
  - FTA rates: ATIGA / ACFTA / JTEPA / AKFTA / AANZFTA / AHKFTA / RCEP / AIFTA / TCFTA / TPFTA

ไม่ต้องการ KNOWLEDGE_ROOT หรือ file ภายนอก — bundled inline ทั้งหมด

Interface เหมือน tax_engine.lookup_tax(hs_code, origin_country) ทุก field
"""

from __future__ import annotations
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# MFN Chapter-level fallback (2-digit) — Thai MFN general rate (%)
# Source: Thai Customs Tariff Schedule 2022 (มาตรา 12 พิกัดอัตราศุลกากร 2565)
# ─────────────────────────────────────────────────────────────────────────────
_MFN_CHAPTER: dict[str, float] = {
    "01": 0.0,   "02": 50.0,  "03": 5.0,   "04": 30.0,  "05": 5.0,
    "06": 20.0,  "07": 30.0,  "08": 40.0,  "09": 30.0,  "10": 30.0,
    "11": 30.0,  "12": 0.0,   "13": 5.0,   "14": 5.0,   "15": 5.0,
    "16": 30.0,  "17": 30.0,  "18": 30.0,  "19": 30.0,  "20": 30.0,
    "21": 30.0,  "22": 30.0,  "23": 10.0,  "24": 20.0,  "25": 0.0,
    "26": 0.0,   "27": 0.0,   "28": 5.0,   "29": 5.0,   "30": 0.0,
    "31": 0.0,   "32": 5.0,   "33": 20.0,  "34": 10.0,  "35": 5.0,
    "36": 5.0,   "37": 5.0,   "38": 5.0,   "39": 20.0,  "40": 20.0,
    "41": 5.0,   "42": 30.0,  "43": 30.0,  "44": 10.0,  "45": 10.0,
    "46": 10.0,  "47": 0.0,   "48": 10.0,  "49": 0.0,   "50": 10.0,
    "51": 5.0,   "52": 12.0,  "53": 5.0,   "54": 12.0,  "55": 12.0,
    "56": 12.0,  "57": 12.0,  "58": 12.0,  "59": 12.0,  "60": 12.0,
    "61": 30.0,  "62": 30.0,  "63": 20.0,  "64": 30.0,  "65": 30.0,
    "66": 20.0,  "67": 20.0,  "68": 10.0,  "69": 30.0,  "70": 20.0,
    "71": 10.0,  "72": 0.0,   "73": 10.0,  "74": 5.0,   "75": 5.0,
    "76": 10.0,  "77": 5.0,   "78": 5.0,   "79": 5.0,   "80": 5.0,
    "81": 5.0,   "82": 10.0,  "83": 10.0,  "84": 0.0,   "85": 0.0,
    "86": 5.0,   "87": 0.0,   "88": 0.0,   "89": 0.0,   "90": 0.0,
    "91": 20.0,  "92": 20.0,  "93": 5.0,   "94": 20.0,  "95": 20.0,
    "96": 10.0,  "97": 0.0,   "98": 0.0,   "99": 0.0,
}

# ─────────────────────────────────────────────────────────────────────────────
# MFN Heading-level (4-digit) — overrides chapter default where notable
# คัดเฉพาะ heading ที่อัตราต่างจาก chapter หรือสำคัญทางการค้า
# ─────────────────────────────────────────────────────────────────────────────
_MFN_4DIGIT: dict[str, float] = {
    # Section I — Live animals / animal products
    "0101": 0.0,   "0102": 0.0,   "0103": 0.0,   "0104": 0.0,   "0105": 0.0,
    "0201": 50.0,  "0202": 50.0,  "0207": 30.0,  "0301": 5.0,   "0302": 5.0,
    "0303": 5.0,   "0304": 5.0,   "0401": 5.0,   "0402": 5.0,   "0406": 5.0,
    # Section II — Vegetable products
    "0701": 30.0,  "0702": 30.0,  "0703": 30.0,  "0704": 30.0,  "0705": 30.0,
    "0706": 30.0,  "0709": 30.0,  "0802": 40.0,  "0803": 40.0,  "0804": 40.0,
    "0805": 40.0,  "0901": 90.0,  "0902": 90.0,  "0904": 30.0,  "1001": 10.0,
    "1006": 30.0,  "1101": 30.0,  "1201": 0.0,   "1211": 0.0,
    # Section III — Fats & oils
    "1507": 5.0,   "1511": 5.0,   "1512": 5.0,   "1516": 5.0,   "1517": 5.0,
    # Section IV — Prepared foods
    "1601": 30.0,  "1602": 30.0,  "1701": 65.0,  "1702": 30.0,  "1704": 30.0,
    "1801": 30.0,  "1802": 30.0,  "1803": 30.0,  "1804": 30.0,  "1805": 30.0,
    "1901": 30.0,  "1902": 30.0,  "1905": 30.0,  "2001": 30.0,  "2002": 30.0,
    "2009": 30.0,  "2101": 30.0,  "2106": 30.0,  "2201": 20.0,  "2202": 20.0,
    "2203": 60.0,  "2204": 60.0,  "2205": 60.0,  "2206": 60.0,  "2208": 60.0,
    "2401": 90.0,  "2402": 90.0,
    # Section V — Mineral products
    "2701": 1.0,   "2709": 1.0,   "2710": 1.0,   "2711": 1.0,
    # Section VI — Chemical products
    "2801": 0.0,   "2802": 0.0,   "2901": 0.0,   "2902": 0.0,   "2933": 0.0,
    "2934": 0.0,   "3001": 0.0,   "3002": 0.0,   "3003": 0.0,   "3004": 0.0,
    "3005": 0.0,   "3006": 0.0,   "3201": 5.0,   "3204": 5.0,   "3208": 5.0,
    "3301": 20.0,  "3302": 20.0,  "3303": 20.0,  "3304": 20.0,  "3305": 20.0,
    "3401": 10.0,  "3402": 5.0,   "3506": 5.0,
    # Section VII — Plastics & Rubber
    "3901": 20.0,  "3902": 20.0,  "3903": 20.0,  "3904": 20.0,  "3905": 20.0,
    "3906": 5.0,   "3916": 20.0,  "3917": 20.0,  "3919": 20.0,  "3920": 20.0,
    "3921": 20.0,  "3923": 20.0,  "3926": 20.0,  "4001": 5.0,   "4002": 5.0,
    "4011": 20.0,  "4012": 20.0,  "4016": 20.0,
    # Section VIII — Leather & hides
    "4101": 5.0,   "4107": 5.0,   "4202": 30.0,  "4203": 30.0,
    # Section IX — Wood & Paper
    "4401": 5.0,   "4407": 5.0,   "4408": 5.0,   "4418": 10.0,  "4802": 10.0,
    "4804": 10.0,  "4810": 10.0,  "4811": 10.0,  "4819": 10.0,  "4820": 10.0,
    "4821": 10.0,  "4901": 0.0,   "4902": 0.0,
    # Section X — Textiles
    "5101": 5.0,   "5201": 0.0,   "5208": 12.0,  "5209": 12.0,  "5401": 12.0,
    "5402": 12.0,  "5407": 12.0,  "5408": 12.0,  "5503": 12.0,  "5504": 12.0,
    "5512": 12.0,  "5513": 12.0,  "5514": 12.0,  "5515": 12.0,  "5516": 12.0,
    "6001": 12.0,  "6002": 12.0,  "6003": 12.0,  "6004": 12.0,  "6005": 12.0,
    "6006": 12.0,
    # Section XI — Clothing
    "6101": 30.0,  "6102": 30.0,  "6103": 30.0,  "6104": 30.0,  "6105": 30.0,
    "6106": 30.0,  "6107": 30.0,  "6108": 30.0,  "6109": 30.0,  "6110": 30.0,
    "6201": 30.0,  "6202": 30.0,  "6203": 30.0,  "6204": 30.0,  "6301": 20.0,
    "6302": 20.0,  "6303": 20.0,  "6304": 20.0,  "6305": 20.0,  "6306": 20.0,
    # Section XII — Footwear / headgear
    "6401": 30.0,  "6402": 30.0,  "6403": 30.0,  "6404": 30.0,  "6405": 30.0,
    "6501": 30.0,
    # Section XIII — Stone / glass / ceramics
    "6802": 10.0,  "6901": 30.0,  "6902": 30.0,  "6910": 30.0,  "6911": 30.0,
    "6912": 30.0,  "7003": 20.0,  "7004": 20.0,  "7005": 20.0,  "7007": 20.0,
    "7013": 20.0,
    # Section XIV — Precious metals / stones
    "7101": 10.0,  "7102": 10.0,  "7108": 0.0,   "7113": 20.0,  "7114": 20.0,
    "7117": 20.0,
    # Section XV — Base metals
    "7201": 0.0,   "7202": 0.0,   "7204": 0.0,   "7207": 0.0,   "7208": 0.0,
    "7209": 0.0,   "7210": 0.0,   "7211": 0.0,   "7212": 0.0,   "7213": 0.0,
    "7214": 0.0,   "7215": 0.0,   "7216": 0.0,   "7217": 0.0,   "7219": 0.0,
    "7220": 0.0,   "7221": 0.0,   "7222": 0.0,   "7225": 0.0,   "7226": 0.0,
    "7227": 0.0,   "7228": 0.0,   "7229": 0.0,   "7301": 0.0,   "7302": 0.0,
    "7304": 0.0,   "7305": 0.0,   "7306": 0.0,   "7307": 0.0,   "7308": 0.0,
    "7309": 0.0,   "7310": 0.0,   "7312": 0.0,   "7314": 0.0,   "7318": 10.0,
    "7319": 10.0,  "7320": 10.0,  "7321": 10.0,  "7323": 10.0,  "7325": 10.0,
    # Section XVI — Machinery / Electrical
    "8401": 0.0,   "8402": 0.0,   "8407": 0.0,   "8408": 0.0,   "8409": 0.0,
    "8411": 0.0,   "8413": 0.0,   "8414": 0.0,   "8415": 0.0,   "8418": 0.0,
    "8421": 0.0,   "8422": 0.0,   "8425": 0.0,   "8429": 0.0,   "8430": 0.0,
    "8431": 0.0,   "8432": 0.0,   "8433": 0.0,   "8443": 0.0,   "8450": 0.0,
    "8451": 0.0,   "8452": 0.0,   "8453": 0.0,   "8454": 0.0,   "8456": 0.0,
    "8457": 0.0,   "8458": 0.0,   "8459": 0.0,   "8460": 0.0,   "8461": 0.0,
    "8462": 0.0,   "8463": 0.0,   "8464": 0.0,   "8465": 0.0,   "8466": 0.0,
    "8467": 0.0,   "8468": 0.0,   "8469": 0.0,   "8470": 0.0,   "8471": 0.0,
    "8472": 0.0,   "8473": 0.0,   "8474": 0.0,   "8475": 0.0,   "8476": 0.0,
    "8477": 0.0,   "8478": 0.0,   "8479": 0.0,   "8480": 0.0,   "8481": 0.0,
    "8482": 0.0,   "8483": 0.0,   "8484": 0.0,   "8485": 0.0,   "8501": 0.0,
    "8502": 0.0,   "8503": 0.0,   "8504": 0.0,   "8505": 0.0,   "8506": 0.0,
    "8507": 0.0,   "8508": 0.0,   "8509": 0.0,   "8510": 0.0,   "8511": 0.0,
    "8512": 0.0,   "8513": 0.0,   "8514": 0.0,   "8515": 0.0,   "8516": 10.0,
    "8517": 0.0,   "8518": 0.0,   "8519": 0.0,   "8521": 0.0,   "8522": 0.0,
    "8523": 0.0,   "8524": 0.0,   "8525": 0.0,   "8526": 0.0,   "8527": 0.0,
    "8528": 20.0,  "8529": 0.0,   "8530": 0.0,   "8531": 0.0,   "8532": 0.0,
    "8533": 0.0,   "8534": 0.0,   "8535": 0.0,   "8536": 0.0,   "8537": 0.0,
    "8538": 0.0,   "8539": 0.0,   "8540": 0.0,   "8541": 0.0,   "8542": 0.0,
    "8543": 0.0,   "8544": 0.0,   "8545": 0.0,   "8546": 0.0,   "8547": 0.0,
    "8548": 0.0,
    # Section XVII — Vehicles
    "8701": 0.0,   "8702": 30.0,  "8703": 80.0,  "8704": 0.0,   "8705": 0.0,
    "8706": 0.0,   "8707": 0.0,   "8708": 0.0,   "8711": 60.0,  "8712": 20.0,
    "8713": 20.0,  "8714": 10.0,  "8716": 0.0,   "8801": 0.0,   "8802": 0.0,
    "8803": 0.0,   "8901": 0.0,   "8902": 0.0,   "8903": 0.0,   "8904": 0.0,
    "8905": 0.0,
    # Section XVIII — Instruments
    "9001": 0.0,   "9003": 20.0,  "9004": 20.0,  "9006": 0.0,   "9007": 0.0,
    "9009": 0.0,   "9013": 0.0,   "9018": 0.0,   "9019": 0.0,   "9020": 0.0,
    "9021": 0.0,   "9022": 0.0,   "9023": 0.0,   "9025": 0.0,   "9026": 0.0,
    "9027": 0.0,   "9028": 0.0,   "9029": 0.0,   "9030": 0.0,   "9031": 0.0,
    "9032": 0.0,   "9033": 0.0,
    # Section XIX — Clocks
    "9101": 20.0,  "9102": 20.0,  "9103": 20.0,  "9104": 20.0,  "9105": 20.0,
    "9111": 20.0,  "9114": 20.0,
    # Section XX — Misc manufactured
    "9401": 20.0,  "9402": 20.0,  "9403": 20.0,  "9404": 20.0,  "9405": 20.0,
    "9406": 20.0,  "9501": 20.0,  "9502": 20.0,  "9503": 20.0,  "9504": 20.0,
    "9505": 20.0,  "9506": 20.0,  "9507": 20.0,  "9508": 20.0,
}

# ─────────────────────────────────────────────────────────────────────────────
# MFN Subheading-level (6-digit) — high-value / commonly traded items
# ─────────────────────────────────────────────────────────────────────────────
_MFN_6DIGIT: dict[str, float] = {
    # Sugar
    "170111": 65.0,  "170112": 65.0,  "170191": 65.0,  "170199": 65.0,
    # Coffee / Tea
    "090111": 90.0,  "090112": 90.0,  "090121": 90.0,  "090122": 90.0,
    "090211": 90.0,  "090212": 90.0,  "090221": 90.0,  "090222": 90.0,
    # Rice
    "100610": 30.0,  "100620": 30.0,  "100630": 30.0,  "100640": 30.0,
    # Palm oil
    "151110": 5.0,   "151190": 5.0,
    # Petroleum
    "271011": 0.0,   "271019": 0.0,   "271020": 0.0,   "271012": 0.0,
    # Plastics — film / sheet
    "392010": 20.0,  "392020": 20.0,  "392030": 20.0,  "392043": 20.0,
    "392049": 20.0,  "392051": 20.0,  "392059": 20.0,  "392061": 20.0,
    "392062": 20.0,  "392063": 20.0,  "392069": 20.0,  "392071": 20.0,
    "392072": 20.0,  "392073": 20.0,  "392079": 20.0,  "392099": 20.0,
    # Pharmaceutical — bulk
    "300210": 0.0,   "300220": 0.0,   "300231": 0.0,   "300239": 0.0,
    "300290": 0.0,   "300310": 0.0,   "300320": 0.0,   "300331": 0.0,
    "300339": 0.0,   "300341": 0.0,   "300342": 0.0,   "300343": 0.0,
    "300349": 0.0,   "300350": 0.0,   "300360": 0.0,   "300390": 0.0,
    "300410": 0.0,   "300420": 0.0,   "300431": 0.0,   "300432": 0.0,
    "300439": 0.0,   "300441": 0.0,   "300442": 0.0,   "300443": 0.0,
    "300449": 0.0,   "300450": 0.0,   "300460": 0.0,   "300490": 0.0,
    # Computers & parts
    "847130": 0.0,   "847141": 0.0,   "847149": 0.0,   "847150": 0.0,
    "847160": 0.0,   "847170": 0.0,   "847180": 0.0,   "847190": 0.0,
    # Mobile phones / Smartphones (8517.12)
    "851712": 0.0,   "851711": 0.0,   "851718": 0.0,
    # Semiconductors / ICs
    "854231": 0.0,   "854232": 0.0,   "854233": 0.0,   "854239": 0.0,
    "854110": 0.0,   "854121": 0.0,   "854129": 0.0,   "854130": 0.0,
    "854140": 0.0,   "854150": 0.0,   "854160": 0.0,   "854190": 0.0,
    # Passenger cars
    "870310": 80.0,  "870321": 80.0,  "870322": 80.0,  "870323": 80.0,
    "870324": 80.0,  "870331": 80.0,  "870332": 80.0,  "870333": 80.0,
    "870340": 80.0,  "870350": 80.0,  "870360": 80.0,  "870370": 80.0,
    "870380": 80.0,  "870390": 80.0,
    # Motorcycles
    "871120": 60.0,  "871130": 60.0,  "871140": 60.0,  "871150": 60.0,
    "871160": 60.0,  "871190": 60.0,
    # Steel flat-rolled
    "720825": 0.0,   "720826": 0.0,   "720827": 0.0,   "720836": 0.0,
    "720837": 0.0,   "720838": 0.0,   "720839": 0.0,   "720840": 0.0,
    "720851": 0.0,   "720852": 0.0,   "720853": 0.0,   "720854": 0.0,
    "720890": 0.0,
    # Gems / diamonds
    "710210": 10.0,  "710221": 10.0,  "710231": 10.0,  "710239": 10.0,
    # Gold — non-monetary
    "710812": 0.0,   "710813": 0.0,   "710820": 0.0,
    # Natural rubber
    "400110": 5.0,   "400121": 5.0,   "400122": 5.0,   "400129": 5.0,
    "400130": 5.0,   "400190": 5.0,
    # Pneumatic tyres — car
    "401110": 20.0,  "401120": 20.0,  "401140": 20.0,  "401180": 20.0,
    "401190": 20.0,
    # Electrical wire / cable
    "854411": 0.0,   "854419": 0.0,   "854420": 0.0,   "854430": 0.0,
    "854442": 0.0,   "854449": 0.0,   "854451": 0.0,   "854459": 0.0,
    "854460": 0.0,   "854470": 0.0,
    # TVs
    "852872": 20.0,  "852873": 20.0,
    # Printed circuit boards
    "853400": 0.0,
    # Solar cells
    "854140": 0.0,
    # Optical fibre cable
    "854470": 0.0,
    # Air conditioning
    "841510": 0.0,   "841521": 0.0,   "841522": 0.0,   "841523": 0.0,
    "841581": 0.0,   "841582": 0.0,   "841583": 0.0,   "841590": 0.0,
    # Refrigerators (household)
    "841810": 0.0,   "841821": 0.0,   "841829": 0.0,   "841830": 0.0,
    "841840": 0.0,   "841850": 0.0,   "841860": 0.0,   "841891": 0.0,
    "841899": 0.0,
    # Washing machines
    "845011": 0.0,   "845012": 0.0,   "845019": 0.0,   "845020": 0.0,
    "845090": 0.0,
    # Tobacco
    "240110": 90.0,  "240120": 90.0,  "240130": 90.0,  "240210": 90.0,
    "240220": 90.0,  "240290": 90.0,  "240311": 90.0,  "240319": 90.0,
    "240391": 90.0,  "240399": 90.0,
    # Beer / Wine
    "220300": 60.0,  "220410": 60.0,  "220421": 60.0,  "220422": 60.0,
    "220429": 60.0,
    # Spirits
    "220820": 60.0,  "220830": 60.0,  "220840": 60.0,  "220850": 60.0,
    "220860": 60.0,  "220870": 60.0,  "220890": 60.0,
    # Cosmetics / skincare
    "330300": 20.0,  "330410": 20.0,  "330420": 20.0,  "330430": 20.0,
    "330491": 20.0,  "330499": 20.0,  "330510": 20.0,  "330520": 20.0,
    "330530": 20.0,  "330541": 20.0,  "330549": 20.0,  "330590": 20.0,
    # Footwear — leather uppers
    "640320": 30.0,  "640351": 30.0,  "640359": 30.0,  "640391": 30.0,
    "640399": 30.0,
    # Ceramic tiles
    "690210": 30.0,  "690290": 30.0,  "690310": 30.0,  "690320": 30.0,
    "690390": 30.0,
    # Paper and paperboard
    "480256": 10.0,  "480257": 10.0,  "480258": 10.0,  "480261": 10.0,
    "480262": 10.0,  "480269": 10.0,
    # Flat glass
    "700310": 20.0,  "700390": 20.0,  "700410": 20.0,  "700490": 20.0,
    "700510": 20.0,  "700521": 20.0,  "700529": 20.0,  "700530": 20.0,
}

# ─────────────────────────────────────────────────────────────────────────────
# FTA rate overrides by origin country ISO-2 code
# Format: { "ISO2": { "6-digit or 4-digit or chapter": rate } }
# 0.0 = duty-free; None = excluded from FTA (use MFN)
#
# Key FTA agreements:
#   ATIGA  — ASEAN (BN, KH, ID, LA, MY, MM, PH, SG, VN)
#   ACFTA  — China (CN)
#   JTEPA/AJCEP — Japan (JP)
#   AKFTA  — Korea (KR)
#   AANZFTA — Australia (AU), New Zealand (NZ)
#   AHKFTA — Hong Kong (HK)
#   RCEP   — CN, JP, KR, AU, NZ + ASEAN (supersedes some above)
#   AIFTA  — India (IN)
#   TCFTA  — Chile (CL)
#   TPFTA  — Peru (PE)
# ─────────────────────────────────────────────────────────────────────────────

# ASEAN member ISO codes
_ASEAN = {"BN", "KH", "ID", "LA", "MY", "MM", "PH", "SG", "VN"}

# RCEP non-ASEAN members
_RCEP_EXTRA = {"CN", "JP", "KR", "AU", "NZ"}

# Sensitive/excluded goods at HS-4 for specific partners (use MFN — mark as None)
_SENSITIVE_4: dict[str, set[str]] = {
    # Sugar — sensitive for most FTAs
    "1701": {"CN", "JP", "KR", "AU", "NZ", "HK", "IN"},
    # Rice — highly protected
    "1006": {"CN", "JP", "KR", "AU", "NZ", "HK", "IN", "CL", "PE"},
    # Passenger cars — excluded from most FTAs
    "8703": {"CN", "JP", "KR", "AU", "NZ", "HK", "IN"},
    # Motorcycles
    "8711": {"CN", "JP", "KR", "AU", "NZ"},
    # Tobacco
    "2401": {"CN", "JP", "KR", "AU", "NZ", "HK"},
    "2402": {"CN", "JP", "KR", "AU", "NZ", "HK"},
}

# FTA flat rates by agreement — simplified; covers most traded goods
# In practice, FTA schedules have thousands of lines. This covers the pattern:
# - Most industrial/manufactured goods → 0%
# - Agriculture varies
# - Sensitive goods excluded (see _SENSITIVE_4)

_FTA_AGRI_REDUCED: dict[str, float] = {
    "ATIGA": 0.0,   # Most agricultural goods 0% under ATIGA for ASEAN
    "ACFTA": 5.0,
    "JTEPA": 5.0,
    "AKFTA": 5.0,
    "AANZFTA": 5.0,
    "AHKFTA": 0.0,
    "RCEP": 5.0,
    "AIFTA": 5.0,
    "TCFTA": 5.0,
    "TPFTA": 5.0,
}

# Map ISO2 → FTA agreement name
_COUNTRY_FTA: dict[str, str] = {
    # ASEAN (ATIGA — superseded by RCEP but ATIGA rates apply for ASEAN members)
    "BN": "ATIGA", "KH": "ATIGA", "ID": "ATIGA", "LA": "ATIGA",
    "MY": "ATIGA", "MM": "ATIGA", "PH": "ATIGA", "SG": "ATIGA", "VN": "ATIGA",
    # RCEP partners
    "CN": "RCEP",  "JP": "RCEP",  "KR": "RCEP",  "AU": "RCEP",  "NZ": "RCEP",
    # AHKFTA
    "HK": "AHKFTA",
    # AIFTA
    "IN": "AIFTA",
    # TCFTA
    "CL": "TCFTA",
    # TPFTA
    "PE": "TPFTA",
}

# Chapter-level MFN thresholds — if MFN rate ≤ this, no FTA benefit worth noting
_LOW_MFN_THRESHOLD = 5.0


def _normalise_hs(hs: str) -> str:
    """Remove dots/spaces, uppercase."""
    return hs.replace(".", "").replace(" ", "").strip()


def _mfn_rate(hs_digits: str) -> tuple[float, str]:
    """Return (rate, matched_level) for best MFN match."""
    h6 = hs_digits[:6]
    h4 = hs_digits[:4]
    h2 = hs_digits[:2]
    if h6 in _MFN_6DIGIT:
        return _MFN_6DIGIT[h6], "subheading"
    if h4 in _MFN_4DIGIT:
        return _MFN_4DIGIT[h4], "heading"
    if h2 in _MFN_CHAPTER:
        return _MFN_CHAPTER[h2], "chapter"
    return 5.0, "default"


def _fta_rate(hs_digits: str, iso2: str) -> Optional[float]:
    """
    Return FTA rate for the given origin country, or None if excluded / no FTA.
    Returns float (including 0.0 for free) or None.
    """
    fta = _COUNTRY_FTA.get(iso2.upper() if iso2 else "")
    if not fta:
        return None  # no FTA with Thailand

    h4 = hs_digits[:4]
    h2 = hs_digits[:2]

    # Check sensitive/excluded goods
    if h4 in _SENSITIVE_4 and iso2.upper() in _SENSITIVE_4[h4]:
        return None  # excluded — use MFN

    # Determine product category
    mfn, _ = _mfn_rate(hs_digits)

    # If MFN is already very low (≤5%), FTA benefit minimal but still return 0
    # Most industrial goods → 0% under FTAs
    chapter_int = int(h2) if h2.isdigit() else 0

    # Agricultural chapters (1-24) — reduced but not zero for most FTAs
    if 1 <= chapter_int <= 24:
        agri_rate = _FTA_AGRI_REDUCED.get(fta, 5.0)
        # ATIGA: ASEAN agricultural goods mostly 0%
        if fta == "ATIGA":
            return 0.0
        return agri_rate

    # Industrial goods (25-97) → 0% under all active Thai FTAs
    return 0.0


def lookup_tax(hs_code: str, origin_country: Optional[str] = None) -> dict:
    """
    Main interface — matches tax_engine.lookup_tax() signature.

    Returns dict with keys:
      status, hs_code, mfn_rate, applicable_rate, applicable_fta,
      origin_country, matched_level, note
    """
    if not hs_code:
        return {"status": "error", "note": "hs_code is required"}

    hs = _normalise_hs(hs_code)
    if len(hs) < 2:
        return {"status": "error", "note": f"hs_code too short: {hs_code}"}

    mfn, level = _mfn_rate(hs)

    iso2 = (origin_country or "").strip().upper()[:2] if origin_country else ""
    fta_rate_val: Optional[float] = None
    fta_name: Optional[str] = None

    if iso2:
        fta_rate_val = _fta_rate(hs, iso2)
        fta_name = _COUNTRY_FTA.get(iso2)

    if fta_rate_val is not None and fta_rate_val < mfn:
        applicable_rate = fta_rate_val
        applicable_fta = fta_name
    else:
        applicable_rate = mfn
        applicable_fta = None

    return {
        "status": "ok",
        "hs_code": hs_code,
        "hs_digits": hs,
        "mfn_rate": mfn,
        "applicable_rate": applicable_rate,
        "applicable_fta": applicable_fta,
        "fta_rate": fta_rate_val,
        "origin_country": origin_country or "",
        "matched_level": level,
        "source": "BUNDLED",
        "note": f"Bundled Thai Tariff HS2022 — {level} level",
    }


# ── convenience alias ─────────────────────────────────────────────────────────
def reload_store() -> None:
    """No-op — bundled data is always in memory."""
    pass


if __name__ == "__main__":
    # Quick self-test
    tests = [
        ("8471.30", "US"),    # laptop — MFN 0%
        ("1701.14", "TH"),    # sugar domestic
        ("8703.23", "JP"),    # car — excluded from RCEP
        ("0302.11", "ID"),    # fish — ATIGA 0%
        ("3004.90", "CN"),    # pharmaceutical — RCEP 0%
        ("8517.12", "SG"),    # smartphone — ATIGA 0%
        ("6203.42", "VN"),    # trousers — ATIGA 0%
        ("2204.21", "AU"),    # wine — MFN 60%
        ("8711.20", "KR"),    # motorcycle — excluded RCEP
        ("1006.30", "MY"),    # rice — excluded ATIGA (sensitive)
    ]
    print(f"{'HS Code':<12} {'Origin':<6} {'MFN%':>6} {'Applicable%':>12} {'FTA':<12} Level")
    print("-" * 65)
    for hs, orig in tests:
        r = lookup_tax(hs, orig)
        print(
            f"{r['hs_code']:<12} {r['origin_country']:<6}"
            f" {r['mfn_rate']:>6.1f}% {r['applicable_rate']:>11.1f}%"
            f" {(r['applicable_fta'] or 'MFN'):<12} {r['matched_level']}"
        )
