-- schema_invoice.sql
-- Phase 8.1 — Invoice Intelligence Pipeline
-- invoice_submissions + invoice_items

-- ─── invoice_submissions — ปกหน้าของแต่ละใบ invoice ────────────────────────
CREATE TABLE IF NOT EXISTS invoice_submissions (
    id               TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    client_api_key   TEXT NOT NULL,
    filename         TEXT,
    file_type        TEXT,                    -- PDF_TEXT / PDF_SCAN / IMAGE / EXCEL / CSV
    invoice_no       TEXT,
    invoice_date     DATE,
    seller_name      TEXT,
    seller_country   TEXT,                    -- ISO 2-letter: CN, TH, BR ...
    buyer_name       TEXT,
    buyer_country    TEXT,
    incoterms        TEXT,                    -- FOB / CIF / EXW / DDP ...
    currency         TEXT DEFAULT 'USD',
    total_value      NUMERIC(18,4),
    item_count       INT DEFAULT 0,
    status           TEXT DEFAULT 'PENDING',  -- PENDING / PROCESSING / DONE / ERROR
    error_msg        TEXT,
    raw_text         TEXT,                    -- ข้อความดิบที่ OCR/parse ได้
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    completed_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_inv_sub_client  ON invoice_submissions(client_api_key);
CREATE INDEX IF NOT EXISTS idx_inv_sub_status  ON invoice_submissions(status);
CREATE INDEX IF NOT EXISTS idx_inv_sub_created ON invoice_submissions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_inv_sub_country ON invoice_submissions(seller_country, buyer_country);

-- ─── invoice_items — รายการสินค้าแต่ละบรรทัด ────────────────────────────────
CREATE TABLE IF NOT EXISTS invoice_items (
    id                  TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    submission_id       TEXT NOT NULL REFERENCES invoice_submissions(id) ON DELETE CASCADE,
    line_no             INT NOT NULL,

    -- ข้อมูลจาก invoice จริง
    description         TEXT,                 -- ชื่อสินค้าต้นฉบับ ← trade intelligence
    description_norm    TEXT,                 -- หลัง normalize
    hs_code_declared    TEXT,                 -- HS ที่ลูกค้าระบุมาในใบ (ถ้ามี)
    qty                 NUMERIC(18,4),
    unit                TEXT,                 -- KG / PCS / CARTON / CBM / L
    unit_price          NUMERIC(18,4),
    line_value          NUMERIC(18,4),        -- qty × unit_price
    currency            TEXT,
    country_origin      TEXT,                 -- แหล่งกำเนิด item นี้ (อาจต่างจาก seller)
    marks_numbers       TEXT,                 -- ป้ายลัง (ถ้ามี)

    -- ผลลัพธ์จาก AI Classification
    hs_code_ai          TEXT,                 -- HS ที่ AI classify ได้
    hs_code_final       TEXT,                 -- ใช้จริง (ถ้า declared ถูก ใช้ declared)
    hs_match            BOOLEAN,              -- declared vs AI ตรงกันไหม (NULL=ไม่มี declared)
    confidence          NUMERIC(5,4),         -- 0.0000 - 1.0000
    reasoning           TEXT,                 -- XAI อธิบายเหตุผล

    -- ภาษีและ FTA
    cif_value_usd       NUMERIC(18,4),        -- ฐานคำนวณภาษี (แปลงเป็น USD แล้ว)
    duty_rate           NUMERIC(8,4),         -- % อัตราภาษี
    duty_estimate_usd   NUMERIC(18,4),        -- ประมาณการภาษีที่ต้องจ่าย
    fta_eligible        BOOLEAN DEFAULT FALSE,
    fta_agreement       TEXT,                 -- ATIGA / ACFTA / JTEPA ...
    fta_rate            NUMERIC(8,4),         -- อัตราภาษีหลัง FTA
    fta_saving_usd      NUMERIC(18,4),        -- ประหยัดได้เท่าไหร่

    -- OGA & Halal
    oga_required        BOOLEAN DEFAULT FALSE,
    oga_agencies        TEXT[],               -- ["DLD","FDA"]
    oga_details         JSONB,                -- รายละเอียดเพิ่มเติม
    halal_required      BOOLEAN DEFAULT FALSE,
    halal_cert_body     TEXT,                 -- JAKIM / CICOT ...

    -- Risk flags
    valuation_flag      BOOLEAN DEFAULT FALSE, -- ราคาต่ำกว่า benchmark
    valuation_note      TEXT,                  -- อธิบายว่าผิดปกติอย่างไร
    hs_mismatch_flag    BOOLEAN DEFAULT FALSE,  -- HS declared ≠ AI → learning signal

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inv_items_sub     ON invoice_items(submission_id);
CREATE INDEX IF NOT EXISTS idx_inv_items_hs      ON invoice_items(hs_code_ai);
CREATE INDEX IF NOT EXISTS idx_inv_items_origin  ON invoice_items(country_origin);
CREATE INDEX IF NOT EXISTS idx_inv_items_fta     ON invoice_items(fta_eligible);
CREATE INDEX IF NOT EXISTS idx_inv_items_mismatch ON invoice_items(hs_mismatch_flag) WHERE hs_mismatch_flag = TRUE;
CREATE INDEX IF NOT EXISTS idx_inv_items_valuation ON invoice_items(valuation_flag) WHERE valuation_flag = TRUE;
CREATE INDEX IF NOT EXISTS idx_inv_items_desc    ON invoice_items USING gin(to_tsvector('english', COALESCE(description,'')));
