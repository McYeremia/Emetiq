-- ============================================================================
-- Migrasi Big Money 002 — Posisi akumulasi yang dilacak
-- Tanggal: 2026-07-11
--
-- CATATAN: tabel ini akan dibuat OTOMATIS oleh Base.metadata.create_all() saat
-- backend atau skrip mana pun berjalan (create_all membuat tabel baru; yang tak
-- pernah ia lakukan adalah menambah kolom ke tabel lama). SQL ini disediakan agar
-- skema produksi tetap eksplisit dan bisa ditinjau — menjalankannya opsional dan
-- aman (IF NOT EXISTS).
--
-- KENAPA ADA: peringkat harian berganti 6-9 nama tiap hari (terbukti dari data:
-- dari 10 saham, hanya 1-4 bertahan ke hari berikutnya). Dengan pergantian sederas
-- itu, perkembangan sebuah akumulasi mustahil diikuti. Tabel ini melacak akumulasi
-- sebagai POSISI: masuk saat terbukti, bertahan meski peringkat harian jatuh, dan
-- keluar hanya ketika distribusinya nyata.
-- ============================================================================

CREATE TABLE IF NOT EXISTS bigmoney_position (
    id                SERIAL PRIMARY KEY,
    ticker            VARCHAR(10) NOT NULL,

    opened_on         DATE        NOT NULL,
    closed_on         DATE,
    status            VARCHAR(10) NOT NULL DEFAULT 'ACTIVE',   -- ACTIVE | CLOSED

    entry_close       DOUBLE PRECISION,   -- harga saat masuk; pembanding perkembangan harga
    last_close        DOUBLE PRECISION,
    last_date         DATE,

    accumulated_value BIGINT DEFAULT 0,   -- Rupiah, ESTIMASI — net asing sejak masuk
    peak_value        BIGINT DEFAULT 0,   -- akumulasi tertinggi yang pernah dicapai
    inflow_days       INTEGER DEFAULT 0,
    distribution_days INTEGER DEFAULT 0,  -- fase jual beruntun; 2 = keluar

    entry_score       DOUBLE PRECISION,
    last_score        DOUBLE PRECISION,
    close_reason      VARCHAR(40),        -- DISTRIBUSI | OUTFLOW | NULL selama aktif

    updated_at        TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_bigmoney_position_ticker    ON bigmoney_position (ticker);
CREATE INDEX IF NOT EXISTS ix_bigmoney_position_status    ON bigmoney_position (status);
CREATE INDEX IF NOT EXISTS ix_bigmoney_position_opened_on ON bigmoney_position (opened_on);
CREATE INDEX IF NOT EXISTS ix_bigmoney_position_closed_on ON bigmoney_position (closed_on);

-- Opsional, samakan dengan tabel bigmoney lain: kunci dari akses klien langsung.
-- Backend memakai koneksi Postgres langsung, jadi ia tetap leluasa.
ALTER TABLE bigmoney_position ENABLE ROW LEVEL SECURITY;

-- Verifikasi
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'bigmoney_position'
ORDER BY ordinal_position;
