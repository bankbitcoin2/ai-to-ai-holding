"""
oga_engine.py — Phase 26: Dynamic OGA Rules Engine (Enhanced)
AI TO AI HOLDING — Customs Intelligence Division

กฎ OGA (Other Government Agency) 36 หน่วยงานไทย:
  - ตรวจสอบว่า HS code ต้องขอใบอนุญาตจากหน่วยงานใดบ้าง
  - แจ้งเอกสารที่ต้องเตรียม + เวลาดำเนินการ
  - Batch check หลาย HS codes พร้อมกัน
  - NSW (National Single Window) link

Bundled offline rules — ทำงานได้โดยไม่ต้อง KNOWLEDGE_ROOT
อ้างอิง: พ.ร.บ. ศุลกากร 2560, กฎหมายเฉพาะแต่ละหน่วยงาน
Roadmap: auto-sync จาก NSW API ทุกสัปดาห์

หมายเหตุ: ข้อมูลนี้เป็นการประมาณการเบื้องต้น
ยืนยันกับ กรมศุลกากร / หน่วยงานที่เกี่ยวข้องก่อนนำเข้า/ส่งออกจริง
"""

from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# AGENCY DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────
_AGENCIES = {
    "DOF":    {"name_th": "กรมประมง",                             "name_en": "Department of Fisheries",                        "url": "https://www.fisheries.go.th"},
    "DLD":    {"name_th": "กรมปศุสัตว์",                          "name_en": "Department of Livestock Development",             "url": "https://www.dld.go.th"},
    "DOA":    {"name_th": "กรมวิชาการเกษตร",                      "name_en": "Department of Agriculture",                       "url": "https://www.doa.go.th"},
    "FDA":    {"name_th": "สำนักงานคณะกรรมการอาหารและยา",         "name_en": "Food and Drug Administration",                    "url": "https://www.fda.moph.go.th"},
    "EXCISE": {"name_th": "กรมสรรพสามิต",                         "name_en": "Excise Department",                               "url": "https://www.excise.go.th"},
    "DMR":    {"name_th": "กรมทรัพยากรธรณี",                      "name_en": "Department of Mineral Resources",                 "url": "https://www.dmr.go.th"},
    "MOD":    {"name_th": "กระทรวงกลาโหม",                        "name_en": "Ministry of Defence",                             "url": "https://www.mod.go.th"},
    "MOC":    {"name_th": "กระทรวงพาณิชย์",                       "name_en": "Ministry of Commerce",                            "url": "https://www.moc.go.th"},
    "ONCB":   {"name_th": "สำนักงานคณะกรรมการป้องกันและปราบปรามยาเสพติด", "name_en": "Office of the Narcotics Control Board",   "url": "https://www.oncb.go.th"},
    "CITES":  {"name_th": "อนุสัญญา CITES (สัตว์/พืชใกล้สูญพันธุ์)", "name_en": "Convention on International Trade in Endangered Species", "url": "https://www.cites.org"},
    "DNP":    {"name_th": "กรมอุทยานแห่งชาติ สัตว์ป่า และพันธุ์พืช", "name_en": "Department of National Parks, Wildlife and Plant Conservation", "url": "https://www.dnp.go.th"},
    "MOE":    {"name_th": "กระทรวงพลังงาน",                       "name_en": "Ministry of Energy",                              "url": "https://www.energy.go.th"},
    "NRC":    {"name_th": "สำนักงานปรมาณูเพื่อสันติ",             "name_en": "Office of Atoms for Peace",                       "url": "https://www.oap.go.th"},
    "TISI":   {"name_th": "สำนักงานมาตรฐานผลิตภัณฑ์อุตสาหกรรม",  "name_en": "Thai Industrial Standards Institute",             "url": "https://www.tisi.go.th"},
    "DITP":   {"name_th": "กรมส่งเสริมการค้าระหว่างประเทศ",       "name_en": "Department of International Trade Promotion",     "url": "https://www.ditp.go.th"},
}


# ─────────────────────────────────────────────────────────────────────────────
# OGA RULES DATABASE
# key = HS prefix (2, 4, or 6 digits without dot)  OR chapter range string
# value = rule dict
# ─────────────────────────────────────────────────────────────────────────────

def _rule(agencies: list[str], note_th: str, note_en: str,
          permit_type: str = "import_permit", risk: str = "HIGH") -> dict:
    return {
        "is_restricted": True,
        "risk_level": risk,
        "permit_type": permit_type,
        "requires_permits": [
            {
                "agency_abbr": a,
                **_AGENCIES.get(a, {"name_th": a, "name_en": a, "url": ""}),
                "permit_type": permit_type,
            }
            for a in agencies
        ],
        "note_th": note_th,
        "note_en": note_en,
    }


# Prefix → rule  (ยาว-สุดก่อน: 6 digits > 4 digits > 2 digits)
_RULES: dict[str, dict] = {

    # ── Chapter 01 — สัตว์มีชีวิต ─────────────────────────────────────────
    "01":   _rule(["DLD", "DOF", "CITES"],
                  "สัตว์มีชีวิตทุกชนิดต้องขออนุญาตกรมปศุสัตว์ / กรมประมง และ CITES ถ้าอยู่ใน Appendix",
                  "All live animals require DLD/DOF import permit + CITES if listed"),

    # ── Chapter 02 — เนื้อสัตว์ ───────────────────────────────────────────
    "02":   _rule(["DLD"],
                  "เนื้อสัตว์และผลิตภัณฑ์ต้องผ่านการตรวจโรคและรับใบอนุญาตกรมปศุสัตว์",
                  "Meat/meat products require veterinary import permit from DLD"),

    # ── Chapter 03 — ปลา สัตว์น้ำ ────────────────────────────────────────
    "03":   _rule(["DOF", "CITES"],
                  "สัตว์น้ำมีชีวิตและผลิตภัณฑ์ต้องขออนุญาตกรมประมง; สายพันธุ์ CITES ต้องมีใบอนุญาตเพิ่มเติม",
                  "Aquatic animals/products require DOF import permit; CITES species need CITES permit"),

    # ปลาคราฟ (Koi / Common Carp) — HS 0301.99 / 0301.93 / 0301.11
    "030111": _rule(["DOF", "CITES"],
                    "ปลาสวยงามน้ำจืดมีชีวิต — ต้องขออนุญาตกรมประมง + ใบรับรองสุขภาพสัตว์ + CITES (ถ้าอยู่ใน Appendix)",
                    "Ornamental live freshwater fish — DOF import permit + health certificate + CITES if listed"),
    "030193": _rule(["DOF", "CITES"],
                    "ปลาคาร์ปมีชีวิต (Common Carp) — ต้องขออนุญาตกรมประมง; ปลาคราฟ (Cyprinus carpio) อยู่ใน CITES Appendix III บางประเทศ",
                    "Live carp — DOF import permit required; Koi (Cyprinus carpio) may be CITES Appendix III"),
    "030199": _rule(["DOF", "CITES"],
                    "ปลามีชีวิตอื่นๆ รวมปลาคราฟ — ต้องขออนุญาตกรมประมง + ใบรับรองสุขภาพ + CITES ถ้าเกี่ยวข้อง",
                    "Other live fish including Koi — DOF import permit + health cert + CITES if applicable"),

    # ── Chapter 04 — ผลิตภัณฑ์นม ────────────────────────────────────────
    "04":   _rule(["FDA", "DLD"],
                  "ผลิตภัณฑ์นมและไข่ต้องขอ อย. และผ่านการตรวจปศุสัตว์",
                  "Dairy/egg products require FDA registration + DLD veterinary inspection",
                  risk="MEDIUM"),

    # ── Chapter 05 — ผลิตภัณฑ์จากสัตว์ ──────────────────────────────────
    "05":   _rule(["CITES", "DNP"],
                  "ผลิตภัณฑ์จากสัตว์ป่า เช่น งาช้าง หนังสัตว์ ขน — ต้องมีใบอนุญาต CITES และ DNP",
                  "Wildlife products (ivory, hides, feathers) require CITES permit + DNP permit"),

    # ── Chapter 06 — พืช ดอกไม้ ──────────────────────────────────────────
    "06":   _rule(["DOA", "CITES"],
                  "ต้นไม้ พืชมีชีวิต เมล็ดพันธุ์ต้องผ่านการตรวจโรคพืช กรมวิชาการเกษตร + CITES (ถ้าพืชคุ้มครอง)",
                  "Live plants/seeds require plant quarantine inspection (DOA) + CITES if listed",
                  risk="MEDIUM"),

    # ── Chapter 07-09 — ผัก ผลไม้ เครื่องเทศ ────────────────────────────
    "07":   _rule(["DOA"],
                  "ผักสดต้องผ่านการตรวจโรคพืชและมาตรฐาน MRL สารเคมีตกค้าง",
                  "Fresh vegetables require plant quarantine + MRL pesticide residue check",
                  risk="MEDIUM"),
    "08":   _rule(["DOA"],
                  "ผลไม้สดต้องผ่านการตรวจโรคพืช",
                  "Fresh fruit requires plant quarantine inspection",
                  risk="MEDIUM"),

    # ── Chapter 10-12 — เมล็ดพืช ─────────────────────────────────────────
    "10":   _rule(["DOA"],
                  "ธัญพืชนำเข้าต้องขออนุญาตกรมวิชาการเกษตรและผ่านการตรวจกักกันพืช",
                  "Cereal grains require DOA import permit + phytosanitary certificate",
                  risk="MEDIUM"),
    "12":   _rule(["DOA", "MOC"],
                  "เมล็ดพันธุ์พืชและน้ำมันพืชบางชนิดต้องขออนุญาต + มีโควตานำเข้า",
                  "Oil seeds/plant seeds may require DOA permit + import quota from MOC",
                  risk="MEDIUM"),

    # ── Chapter 13 — ยางและของที่ได้จากพืช ──────────────────────────────
    # ส่วนใหญ่ไม่ต้อง OGA ยกเว้น opium latex
    "130220": _rule(["ONCB"],
                    "ยางฝิ่น (Opium latex) — ต้องได้รับอนุญาต ป.ป.ส.",
                    "Opium latex requires ONCB narcotics permit", risk="CRITICAL"),

    # ── Chapter 15 — ไขมันและน้ำมัน ─────────────────────────────────────
    "1516":  _rule(["FDA"],
                   "ไขมันสัตว์/พืชแปรรูปสำหรับบริโภคต้องจดทะเบียน อย.",
                   "Processed edible fats/oils require FDA registration",
                   risk="LOW"),

    # ── Chapter 22 — เครื่องดื่ม ─────────────────────────────────────────
    "2203":  _rule(["EXCISE", "FDA"],
                   "เบียร์นำเข้าต้องเสียสรรพสามิตและได้รับใบอนุญาตนำเข้าสุรา",
                   "Beer requires excise duty payment + liquor import license"),
    "2204":  _rule(["EXCISE", "FDA"],
                   "ไวน์นำเข้าต้องเสียสรรพสามิตและได้รับใบอนุญาตนำเข้าสุรา",
                   "Wine requires excise duty payment + liquor import license"),
    "2205":  _rule(["EXCISE", "FDA"],
                   "เวอร์มุทและไวน์ปรุงแต่ง — ใบอนุญาตสุรา + สรรพสามิต",
                   "Vermouth/fortified wine — liquor license + excise"),
    "2206":  _rule(["EXCISE", "FDA"],
                   "เครื่องดื่มหมักอื่นๆ — ใบอนุญาตสุรา + สรรพสามิต",
                   "Other fermented beverages — liquor license + excise"),
    "2207":  _rule(["EXCISE", "FDA"],
                   "เอทานอลและแอลกอฮอล์กลั่น — ใบอนุญาตพิเศษกรมสรรพสามิต",
                   "Ethyl alcohol/spirits — special excise permit required"),
    "2208":  _rule(["EXCISE", "FDA"],
                   "สุราและสุรากลั่นต้องมีใบอนุญาตนำเข้าสุราและชำระสรรพสามิต",
                   "Spirits/liquors require import license + excise duty payment"),

    # ── Chapter 23 — อาหารสัตว์ ──────────────────────────────────────────
    "23":   _rule(["DLD", "DOA"],
                  "อาหารสัตว์บางชนิดต้องขออนุญาตกรมปศุสัตว์และผ่านการตรวจสุขอนามัย",
                  "Animal feed may require DLD import permit + phytosanitary check",
                  risk="MEDIUM"),

    # ── Chapter 25 — แร่ธาตุ ─────────────────────────────────────────────
    "25":   _rule(["DMR", "MOC"],
                  "แร่ธาตุบางชนิดต้องขออนุญาตกรมทรัพยากรธรณีหรือกระทรวงพาณิชย์",
                  "Certain minerals require DMR permit or MOC import quota",
                  risk="MEDIUM"),

    # ── Chapter 26 — แร่โลหะ ─────────────────────────────────────────────
    "2612":  _rule(["NRC"],
                   "แร่ยูเรเนียมและทอเรียม — ต้องได้รับอนุญาตจาก สปปส. (พลังงานนิวเคลียร์)",
                   "Uranium/thorium ores require OAP nuclear permit", risk="CRITICAL"),

    # ── Chapter 28 — เคมีภัณฑ์อนินทรีย์ ─────────────────────────────────
    "2844":  _rule(["NRC"],
                   "วัสดุนิวเคลียร์และกัมมันตรังสี — ต้องได้รับอนุญาต สปปส.",
                   "Nuclear/radioactive materials require OAP permit", risk="CRITICAL"),
    "2901":  _rule(["EXCISE", "MOE"],
                   "ไฮโดรคาร์บอน (เชื้อเพลิง) — ใบอนุญาตนำเข้าพลังงาน",
                   "Hydrocarbon fuels require energy import permit",
                   risk="MEDIUM"),

    # ── Chapter 29 — เคมีภัณฑ์อินทรีย์ ──────────────────────────────────
    "2939":  _rule(["ONCB", "FDA"],
                   "อัลคาลอยด์จากฝิ่น มอร์ฟีน โคเดอีน — ต้องขออนุญาต ป.ป.ส. + อย.",
                   "Opium alkaloids (morphine, codeine) require ONCB narcotics permit + FDA",
                   risk="CRITICAL"),

    # ── Chapter 30 — ผลิตภัณฑ์ยา ────────────────────────────────────────
    "30":   _rule(["FDA"],
                  "ยาและผลิตภัณฑ์เภสัชกรรมทุกชนิดต้องขออนุญาตและจดทะเบียนกับ อย.",
                  "All pharmaceutical products require FDA import permit + product registration"),

    # ── Chapter 31 — ปุ๋ย ────────────────────────────────────────────────
    "31":   _rule(["DOA"],
                  "ปุ๋ยนำเข้าต้องขึ้นทะเบียนกับกรมวิชาการเกษตร",
                  "Fertilizers require registration with DOA",
                  risk="MEDIUM"),

    # ── Chapter 36 — วัตถุระเบิด ─────────────────────────────────────────
    "36":   _rule(["MOD", "MOC"],
                  "วัตถุระเบิด ดินปืน ประทัด — ต้องได้รับอนุญาตกระทรวงกลาโหมและพาณิชย์",
                  "Explosives/gunpowder/fireworks require MOD + MOC permit", risk="CRITICAL"),

    # ── Chapter 38 — เคมีภัณฑ์เบ็ดเตล็ด ────────────────────────────────
    "3808":  _rule(["DOA", "FDA"],
                   "ยาฆ่าแมลง ยากำจัดศัตรูพืช — ต้องขึ้นทะเบียนกรมวิชาการเกษตร",
                   "Insecticides/pesticides require DOA registration"),

    # ── Chapter 40 — ยาง ─────────────────────────────────────────────────
    # ส่วนใหญ่ไม่ต้อง OGA

    # ── Chapter 50-63 — สิ่งทอ ───────────────────────────────────────────
    # ส่วนใหญ่ไม่ต้อง OGA ยกเว้นโควตา

    # ── Chapter 71 — อัญมณีและโลหะมีค่า ──────────────────────────────────
    "7101":  _rule(["MOC"],
                   "ไข่มุกธรรมชาติ — อาจต้องแสดงหลักฐานต้นกำเนิด",
                   "Natural pearls — may require certificate of origin from MOC",
                   risk="LOW"),
    "7102":  _rule(["MOC"],
                   "เพชร — ต้องมีใบรับรองตามข้อตกลง Kimberley Process",
                   "Diamonds require Kimberley Process Certificate",
                   risk="MEDIUM"),

    # ── Chapter 84-85 — เครื่องจักรและอุปกรณ์ไฟฟ้า ──────────────────────
    "8414":  _rule(["TISI"],
                   "ปั๊มลม เครื่องปรับอากาศ — ต้องมี มอก. (บางรุ่น)",
                   "Air pumps/compressors/AC units may require TISI (TIS) certification",
                   risk="LOW"),
    "8516":  _rule(["TISI"],
                   "เครื่องใช้ไฟฟ้าในครัวเรือน — ต้องได้รับ มอก. บังคับ",
                   "Electric household appliances require mandatory TISI certification",
                   risk="MEDIUM"),
    "8544":  _rule(["TISI"],
                   "สายไฟและสายเคเบิล — ต้องมี มอก. บังคับ",
                   "Insulated wires/cables require mandatory TISI certification",
                   risk="MEDIUM"),

    # ── Chapter 87 — ยานพาหนะ ────────────────────────────────────────────
    "8703":  _rule(["MOC", "TISI"],
                   "รถยนต์นำเข้าต้องมีมาตรฐานความปลอดภัย มอก. และอาจมีโควตา",
                   "Imported passenger cars require TISI safety standards + possible MOC quota",
                   risk="MEDIUM"),

    # ── Chapter 88 — อากาศยาน ────────────────────────────────────────────
    "88":   _rule(["MOD", "MOC"],
                  "อากาศยาน โดรน ต้องขออนุญาต กพท. และ/หรือ กระทรวงกลาโหม",
                  "Aircraft/drones require CAAT permit and/or MOD authorization"),

    # ── Chapter 90 — เครื่องมือแพทย์ ────────────────────────────────────
    "90":   _rule(["FDA"],
                  "เครื่องมือแพทย์และอุปกรณ์การแพทย์ต้องจดทะเบียนกับ อย.",
                  "Medical devices/instruments require FDA registration",
                  risk="MEDIUM"),

    # ── Chapter 93 — อาวุธ ────────────────────────────────────────────────
    "93":   _rule(["MOD", "MOC"],
                  "อาวุธปืน กระสุน อาวุธสงคราม — ต้องได้รับอนุญาตกระทรวงกลาโหมก่อนนำเข้า",
                  "Firearms, ammunition, weapons require MOD import authorization", risk="CRITICAL"),
    "9301":  _rule(["MOD"],
                   "อาวุธสงคราม — ห้ามนำเข้าโดยเอกชน (รัฐบาลเท่านั้น)",
                   "Military weapons — private import prohibited (government only)", risk="CRITICAL"),
    "9302":  _rule(["MOD", "MOC"],
                   "ปืนพกและปืนสั้น — ต้องขออนุญาตกระทรวงกลาโหม",
                   "Revolvers/pistols require MOD import permit", risk="CRITICAL"),
    "9303":  _rule(["MOD"],
                   "ปืนยาวและปืนล่าสัตว์ — ต้องได้รับอนุญาตกระทรวงกลาโหม",
                   "Sporting/hunting rifles require MOD permit", risk="CRITICAL"),
    "9304":  _rule(["MOD"],
                   "อาวุธอื่นๆ เช่น ปืนลม — ต้องขออนุญาต",
                   "Other arms including air guns — permit required", risk="HIGH"),

    # ── Chapter 97 — งานศิลปะ ────────────────────────────────────────────
    "9705":  _rule(["MOC"],
                   "วัตถุโบราณและงานศิลปะ — อาจต้องขออนุญาตส่งออกจากประเทศต้นกำเนิด",
                   "Antiques/artwork may require export permit from country of origin",
                   risk="MEDIUM"),
}


# ─────────────────────────────────────────────────────────────────────────────
# LOOKUP FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def check(hs_code: str, destination_country: Optional[str] = None) -> dict:
    """
    ตรวจสอบว่า HS Code นี้ต้องขออนุญาต OGA ไหม

    Args:
        hs_code: HS Code (รูปแบบใดก็ได้ เช่น "0301.99", "030199", "03")
        destination_country: รหัสประเทศปลายทาง ISO 3166-1 alpha-2 (ยังไม่ใช้ใน v1)

    Returns:
        dict ที่มี:
          is_restricted: bool
          risk_level: str (LOW | MEDIUM | HIGH | CRITICAL)
          requires_permits: list[dict]
          note_th: str
          note_en: str
          matched_prefix: str | None
          source: "OGA_ENGINE_BUNDLED"
    """
    if not hs_code:
        return _not_restricted()

    # normalize — ตัด dot และ space ออก
    digits = hs_code.replace(".", "").replace(" ", "").strip()

    # ค้น prefix ยาวที่สุดก่อน (6 → 4 → 2 digits)
    for length in (6, 4, 2):
        prefix = digits[:length]
        if prefix in _RULES:
            result = dict(_RULES[prefix])
            result["matched_prefix"] = prefix
            result["source"] = "OGA_ENGINE_BUNDLED"
            return result

    return _not_restricted()


def _not_restricted() -> dict:
    return {
        "is_restricted": False,
        "risk_level": "NONE",
        "requires_permits": [],
        "note_th": "ไม่พบกฎ OGA เฉพาะสำหรับ HS Code นี้ในฐานข้อมูลออฟไลน์ — ยืนยันกับกรมศุลกากรก่อนนำเข้าจริง",
        "note_en": "No specific OGA rule found for this HS code in offline database — verify with Thai Customs before actual import",
        "matched_prefix": None,
        "source": "OGA_ENGINE_BUNDLED",
    }


def list_chapters() -> list[str]:
    """คืน list ของ prefixes ทั้งหมดที่ครอบคลุมใน engine"""
    return sorted(_RULES.keys())


def status() -> dict:
    return {
        "engine": "OGA_ENGINE_BUNDLED",
        "version": "2.0.0",
        "rules_count": len(_RULES),
        "agencies_count": len(_AGENCIES),
        "mode": "OFFLINE",
        "note": "Phase 26 enhanced — 36 agencies, batch check, doc listing, processing time",
    }


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 26 ENHANCED — ADDITIONAL AGENCIES
# ─────────────────────────────────────────────────────────────────────────────

_AGENCIES.update({
    "NBTC":   {"name_th": "สำนักงาน กสทช.",                           "name_en": "National Broadcasting and Telecommunications Commission", "url": "https://www.nbtc.go.th"},
    "DIW":    {"name_th": "กรมโรงงานอุตสาหกรรม",                      "name_en": "Department of Industrial Works",                  "url": "https://www.diw.go.th"},
    "OIE":    {"name_th": "สำนักงานเศรษฐกิจอุตสาหกรรม",              "name_en": "Office of Industrial Economics",                  "url": "https://www.oie.go.th"},
    "BOI":    {"name_th": "สำนักงานคณะกรรมการส่งเสริมการลงทุน",      "name_en": "Board of Investment",                              "url": "https://www.boi.go.th"},
    "DFT":    {"name_th": "กรมการค้าต่างประเทศ",                      "name_en": "Department of Foreign Trade",                     "url": "https://www.dft.go.th"},
    "DIT":    {"name_th": "กรมการค้าภายใน",                           "name_en": "Department of Internal Trade",                    "url": "https://www.dit.go.th"},
    "ONEP":   {"name_th": "สำนักงานนโยบายและแผนทรัพยากรธรรมชาติฯ",   "name_en": "Office of Natural Resources and Environmental Policy and Planning", "url": "https://www.onep.go.th"},
    "PCD":    {"name_th": "กรมควบคุมมลพิษ",                           "name_en": "Pollution Control Department",                    "url": "https://www.pcd.go.th"},
    "DMF":    {"name_th": "กรมป่าไม้",                                 "name_en": "Royal Forest Department",                         "url": "https://www.forest.go.th"},
    "DMSC":   {"name_th": "กรมวิทยาศาสตร์การแพทย์",                   "name_en": "Department of Medical Sciences",                  "url": "https://www.dmsc.moph.go.th"},
    "DDC":    {"name_th": "กรมควบคุมโรค",                              "name_en": "Department of Disease Control",                   "url": "https://ddc.moph.go.th"},
    "DEDE":   {"name_th": "กรมพัฒนาพลังงานทดแทนฯ",                   "name_en": "Department of Alternative Energy Development and Efficiency", "url": "https://www.dede.go.th"},
    "DOEB":   {"name_th": "กรมธุรกิจพลังงาน",                         "name_en": "Department of Energy Business",                   "url": "https://www.doeb.go.th"},
    "DPIM":   {"name_th": "กรมอุตสาหกรรมพื้นฐานและการเหมืองแร่",     "name_en": "Department of Primary Industries and Mines",       "url": "https://www.dpim.go.th"},
    "DPC":    {"name_th": "กรมศิลปากร",                                "name_en": "Fine Arts Department",                            "url": "https://www.finearts.go.th"},
    "ACFS":   {"name_th": "สำนักงานมาตรฐานสินค้าเกษตรฯ",             "name_en": "National Bureau of Agricultural Commodity and Food Standards", "url": "https://www.acfs.go.th"},
    "OAE":    {"name_th": "สำนักงานเศรษฐกิจการเกษตร",                 "name_en": "Office of Agricultural Economics",                "url": "https://www.oae.go.th"},
    "RFD":    {"name_th": "กรมการข้าว",                                "name_en": "Rice Department",                                 "url": "https://www.ricethailand.go.th"},
    "SCD":    {"name_th": "กรมหม่อนไหม",                              "name_en": "Queen Sirikit Department of Sericulture",          "url": "https://www.qsds.go.th"},
    "TOBACCO": {"name_th": "การยาสูบแห่งประเทศไทย",                   "name_en": "Tobacco Authority of Thailand",                   "url": "https://www.thaitobacco.or.th"},
    "DOPA":   {"name_th": "กรมการปกครอง",                              "name_en": "Department of Provincial Administration",         "url": "https://www.dopa.go.th"},
    "DSI":    {"name_th": "กรมสอบสวนคดีพิเศษ",                        "name_en": "Department of Special Investigation",             "url": "https://www.dsi.go.th"},
    "OAP":    {"name_th": "สำนักงานปรมาณูเพื่อสันติ",                 "name_en": "Office of Atoms for Peace",                       "url": "https://www.oap.go.th"},
    "MDES":   {"name_th": "กระทรวงดิจิทัลเพื่อเศรษฐกิจและสังคม",     "name_en": "Ministry of Digital Economy and Society",          "url": "https://www.mdes.go.th"},
    "BOT":    {"name_th": "ธนาคารแห่งประเทศไทย",                      "name_en": "Bank of Thailand",                                "url": "https://www.bot.or.th"},
    "SEC":    {"name_th": "สำนักงาน ก.ล.ต.",                          "name_en": "Securities and Exchange Commission",              "url": "https://www.sec.or.th"},
})

# Additional HS rules for enhanced coverage
_RULES.update({
    # ── Chapter 24 — ยาสูบ ────────────────────────────────────────
    "24": _rule(["EXCISE", "FDA"],
                "ยาสูบและบุหรี่ทุกชนิดต้องชำระสรรพสามิตและขอ อย.",
                "Tobacco products require excise duty + FDA permit", risk="CRITICAL"),

    # ── Chapter 27 — เชื้อเพลิง ───────────────────────────────────
    "2709": _rule(["DOEB", "MOE"],
                  "น้ำมันดิบ — ใบอนุญาตธุรกิจพลังงาน",
                  "Crude oil requires energy business permit"),
    "2710": _rule(["DOEB", "EXCISE"],
                  "น้ำมันสำเร็จรูป — ใบอนุญาต + สรรพสามิต",
                  "Refined petroleum requires DOEB permit + excise"),

    # ── Chapter 33 — เครื่องสำอาง ─────────────────────────────────
    "33":   _rule(["FDA"],
                  "เครื่องสำอางทุกชนิดต้องจดแจ้ง อย. และมีฉลากภาษาไทย",
                  "All cosmetics require FDA notification + Thai labels",
                  risk="MEDIUM"),

    # ── Chapter 38 — วัตถุอันตราย ─────────────────────────────────
    "38":   _rule(["DIW", "PCD"],
                  "เคมีภัณฑ์/วัตถุอันตรายต้องขอ วอ.1 จากกรมโรงงาน",
                  "Hazardous chemicals require DIW permit (วอ.1)"),

    # ── Chapter 44 — ไม้ ──────────────────────────────────────────
    "44":   _rule(["DMF", "CITES"],
                  "ไม้และผลิตภัณฑ์ไม้ต้องมีใบรับรองแหล่งกำเนิด + CITES (ไม้หวงห้าม)",
                  "Wood/timber requires certificate of origin + CITES if restricted"),

    # ── Chapter 85 — อิเล็กทรอนิกส์ + วิทยุ ─────────────────────
    "8517": _rule(["NBTC", "TISI"],
                  "โทรศัพท์ อุปกรณ์โทรคมนาคม — ต้องขอ กสทช. + มอก.",
                  "Phones/telecom equipment require NBTC + TISI certification",
                  risk="MEDIUM"),
    "8525": _rule(["NBTC"],
                  "เครื่องส่งวิทยุ/โทรทัศน์ — ใบอนุญาต กสทช.",
                  "Radio/TV transmitters require NBTC permit"),
    "8527": _rule(["NBTC"],
                  "เครื่องรับวิทยุ — ใบอนุญาต กสทช.",
                  "Radio receivers require NBTC permit", risk="MEDIUM"),

    # ── Chapter 97 — วัตถุโบราณ ────────────────────────────────────
    "97":   _rule(["DPC", "MOC"],
                  "วัตถุโบราณ ศิลปวัตถุ — ต้องขอกรมศิลปากร",
                  "Antiques/artworks require Fine Arts Department permit",
                  risk="MEDIUM"),
})


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 26 — ENHANCED FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def check_batch(hs_codes: list[str]) -> list[dict]:
    """ตรวจ OGA หลาย HS codes พร้อมกัน (limit 50)"""
    results = []
    for hs in hs_codes[:50]:
        result = check(hs.strip())
        result["hs_code"] = hs.strip()
        results.append(result)
    return results


def get_documents_checklist(hs_code: str) -> dict:
    """
    สร้างรายการเอกสารที่ต้องเตรียม สำหรับ HS code
    รวมเอกสาร standard + เอกสารเฉพาะ OGA
    """
    result = check(hs_code)

    # เอกสารมาตรฐานทุกการนำเข้า
    standard_docs = [
        "ใบขนสินค้าขาเข้า (Import Declaration)",
        "บัญชีราคาสินค้า (Commercial Invoice)",
        "ใบตราส่งสินค้า (Bill of Lading / Air Waybill)",
        "บัญชีบรรจุหีบห่อ (Packing List)",
        "ใบรับรองแหล่งกำเนิดสินค้า (Certificate of Origin) — ถ้าใช้สิทธิ FTA",
        "หนังสือมอบอำนาจ (Power of Attorney) — กรณีใช้ตัวแทน",
    ]

    oga_docs = []
    agencies_required = []
    total_days = 0

    if result.get("is_restricted"):
        for permit in result.get("requires_permits", []):
            agency_name = permit.get("name_th", permit.get("agency_abbr", ""))
            agencies_required.append({
                "agency": permit.get("agency_abbr", ""),
                "name_th": agency_name,
                "name_en": permit.get("name_en", ""),
                "url": permit.get("url", ""),
                "permit_type": permit.get("permit_type", "import_permit"),
            })
            oga_docs.append(f"ใบอนุญาตจาก {agency_name}")

    # Estimate processing time
    risk = result.get("risk_level", "NONE")
    if risk == "CRITICAL":
        total_days = 45
    elif risk == "HIGH":
        total_days = 30
    elif risk == "MEDIUM":
        total_days = 15
    else:
        total_days = 7

    return {
        "hs_code": hs_code,
        "is_restricted": result.get("is_restricted", False),
        "risk_level": risk,
        "standard_documents": standard_docs,
        "oga_documents": oga_docs,
        "total_documents": len(standard_docs) + len(oga_docs),
        "agencies_required": agencies_required,
        "estimated_processing_days": total_days,
        "note_th": result.get("note_th", ""),
        "note_en": result.get("note_en", ""),
        "nsw_link": "https://nsw.customs.go.th",
    }


def get_all_agencies() -> list[dict]:
    """รายชื่อหน่วยงาน OGA ทั้งหมดที่อยู่ในระบบ"""
    return [
        {"code": code, **info}
        for code, info in sorted(_AGENCIES.items())
    ]


def get_agency_detail(code: str) -> Optional[dict]:
    """ข้อมูลหน่วยงาน OGA เฉพาะรายหน่วยงาน"""
    info = _AGENCIES.get(code.upper())
    if not info:
        return None
    # หา HS codes ที่หน่วยงานนี้รับผิดชอบ
    related_hs = []
    for prefix, rule in _RULES.items():
        for permit in rule.get("requires_permits", []):
            if permit.get("agency_abbr") == code.upper():
                related_hs.append(prefix)
                break
    return {
        "code": code.upper(),
        **info,
        "related_hs_prefixes": related_hs,
        "total_hs_rules": len(related_hs),
    }


def get_restricted_chapters_summary() -> list[dict]:
    """สรุป HS chapters/prefixes ที่ต้อง OGA พร้อมจำนวนหน่วยงาน"""
    summary = []
    for prefix in sorted(_RULES.keys()):
        rule = _RULES[prefix]
        agencies = [p.get("agency_abbr", "") for p in rule.get("requires_permits", [])]
        summary.append({
            "hs_prefix": prefix,
            "agencies": agencies,
            "total_agencies": len(agencies),
            "risk_level": rule.get("risk_level", "NONE"),
            "note_th": rule.get("note_th", ""),
        })
    return summary
