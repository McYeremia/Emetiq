-- ============================================================================
-- Migrasi Big Money → Supabase (Postgres)
-- Tanggal: 2026-07-11
--
-- CARA PAKAI: Supabase Dashboard → SQL Editor → tempel per LANGKAH, jalankan,
-- lalu lanjut ke langkah berikutnya. Boleh juga sekali jalan seluruhnya.
--
-- AMAN UNTUK DATABASE LIVE:
--   * Semua CREATE dan ALTER memakai IF NOT EXISTS → bisa dijalankan berulang.
--   * Kolom baru di `profiles` semuanya NULLABLE tanpa DEFAULT → Postgres tidak
--     menulis ulang satu baris pun, tabel tidak terkunci, user yang sedang login
--     tak merasakan apa-apa.
--   * Tidak ada DROP, tidak ada perubahan tipe, tidak ada data yang tersentuh.
--
-- KENAPA MANUAL: backend memakai Base.metadata.create_all(), yang HANYA membuat
-- tabel baru. Ia tak pernah menambah kolom ke tabel yang sudah ada — jadi tiga
-- kolom Telegram di `profiles` (LANGKAH 6) tak akan pernah lahir sendiri.
-- Tabel baru (LANGKAH 1-5) sebenarnya bisa dibuat otomatis, tapi dibuat di sini
-- juga supaya skema produksi eksplisit dan bisa Anda tinjau sebelum berjalan.
-- ============================================================================


-- ── LANGKAH 1 — Data harian IDX (fondasi; semua yang lain bergantung padanya) ──
-- ~965 baris per hari bursa. `ticker` sengaja BUKAN foreign key ke stocks: IDX
-- memuat ~964 saham sementara tabel stocks hanya ~737, dan agregat pasar harus
-- dihitung dari seluruh pasar agar tidak bias.
CREATE TABLE IF NOT EXISTS bigmoney_stock_daily (
    id                    SERIAL PRIMARY KEY,
    ticker                VARCHAR(10) NOT NULL,
    date                  DATE        NOT NULL,

    prev_close            DOUBLE PRECISION,
    open_price            DOUBLE PRECISION,
    high                  DOUBLE PRECISION,
    low                   DOUBLE PRECISION,
    close                 DOUBLE PRECISION,
    volume                BIGINT  DEFAULT 0,   -- lembar, bukan lot
    value                 BIGINT  DEFAULT 0,   -- Rupiah
    frequency             INTEGER DEFAULT 0,
    listed_shares         BIGINT,
    foreign_buy           BIGINT  DEFAULT 0,   -- lembar
    foreign_sell          BIGINT  DEFAULT 0,   -- lembar

    -- Turunan. NULL bila pembaginya nol — bukan 0. Sekitar 13,7% baris IDX punya
    -- volume = 0, dan nol akan menarik turun AVG() serta merusak peringkat.
    foreign_net           BIGINT,
    vwap                  DOUBLE PRECISION,
    foreign_net_value     BIGINT,              -- ESTIMASI: foreign_net × VWAP pasar
    avg_ticket            DOUBLE PRECISION,
    foreign_participation DOUBLE PRECISION,
    change_pct            DOUBLE PRECISION,

    scraped_at            TIMESTAMP DEFAULT now(),

    CONSTRAINT uq_bmsd_ticker_date UNIQUE (ticker, date)
);

CREATE INDEX IF NOT EXISTS ix_bigmoney_stock_daily_ticker ON bigmoney_stock_daily (ticker);
CREATE INDEX IF NOT EXISTS ix_bigmoney_stock_daily_date   ON bigmoney_stock_daily (date);


-- ── LANGKAH 2 — Rezim pasar harian ────────────────────────────────────────────
-- Diturunkan dari agregat bigmoney_stock_daily, BUKAN dari OHLCV ^JKSE (yang
-- tertinggal berminggu-minggu dan akan menghasilkan rezim yang salah).
CREATE TABLE IF NOT EXISTS bigmoney_market_regime (
    id                      SERIAL PRIMARY KEY,
    date                    DATE NOT NULL,

    volatility_regime       VARCHAR(10),   -- CALM | VOLATILE
    trend_regime            VARCHAR(10),   -- BULL | SIDEWAYS | BEAR
    weight_set              VARCHAR(10),   -- CALM | VOLATILE

    market_return_pct       DOUBLE PRECISION,
    market_volatility_20d   DOUBLE PRECISION,
    breadth                 DOUBLE PRECISION,
    total_foreign_net_value BIGINT,
    sector_rotation         JSONB,

    computed_at             TIMESTAMP DEFAULT now(),

    CONSTRAINT uq_bmmr_date UNIQUE (date)
);

CREATE INDEX IF NOT EXISTS ix_bigmoney_market_regime_date ON bigmoney_market_regime (date);


-- ── LANGKAH 3 — Skor per saham per hari ───────────────────────────────────────
-- Hanya saham yang lolos filter likuiditas (~273 dari ~965 per hari).
-- Subskor adalah peringkat persentil 0-100 terhadap universe HARI ITU.
CREATE TABLE IF NOT EXISTS bigmoney_score (
    id                      SERIAL PRIMARY KEY,
    ticker                  VARCHAR(10) NOT NULL,
    date                    DATE        NOT NULL,

    composite               DOUBLE PRECISION,
    conviction              VARCHAR(10),   -- STRONG | WATCH | WEAK
    phase                   VARCHAR(12),   -- AKUMULASI | MARKUP | DISTRIBUSI | MARKDOWN | NETRAL
    weight_set              VARCHAR(10),

    s_relative_foreign_flow DOUBLE PRECISION,
    s_foreign_persistence   DOUBLE PRECISION,
    s_big_ticket            DOUBLE PRECISION,
    s_cost_basis            DOUBLE PRECISION,
    s_volume_price          DOUBLE PRECISION,

    days_confirmed          INTEGER DEFAULT 0,
    flags                   JSONB,

    computed_at             TIMESTAMP DEFAULT now(),

    CONSTRAINT uq_bms_ticker_date UNIQUE (ticker, date)
);

CREATE INDEX IF NOT EXISTS ix_bigmoney_score_ticker ON bigmoney_score (ticker);
CREATE INDEX IF NOT EXISTS ix_bigmoney_score_date   ON bigmoney_score (date);


-- ── LANGKAH 4 — Peringkat 10 besar per tanggal ────────────────────────────────
-- Tabel tipis; target baca API dan laporan AI supaya keduanya tak perlu memindai
-- bigmoney_score.
CREATE TABLE IF NOT EXISTS bigmoney_top_accumulation (
    id          SERIAL PRIMARY KEY,
    date        DATE        NOT NULL,
    rank        INTEGER     NOT NULL,

    ticker      VARCHAR(10) NOT NULL,
    composite   DOUBLE PRECISION,
    conviction  VARCHAR(10),
    phase       VARCHAR(12),

    computed_at TIMESTAMP DEFAULT now(),

    CONSTRAINT uq_bmta_date_rank UNIQUE (date, rank)
);

CREATE INDEX IF NOT EXISTS ix_bigmoney_top_accumulation_date   ON bigmoney_top_accumulation (date);
CREATE INDEX IF NOT EXISTS ix_bigmoney_top_accumulation_ticker ON bigmoney_top_accumulation (ticker);


-- ── LANGKAH 5 — Laporan harian AI ─────────────────────────────────────────────
-- `context` menyimpan angka dan hasil kerja tiap agen yang disodorkan ke model.
-- Tanpa itu, laporan lama tak bisa diaudit: kita takkan tahu apakah kalimatnya
-- keliru karena modelnya mengarang atau karena datanya memang begitu.
CREATE TABLE IF NOT EXISTS bigmoney_daily_report (
    id           SERIAL PRIMARY KEY,
    date         DATE NOT NULL,

    headline     VARCHAR(300),
    narrative    TEXT,
    context      JSONB,
    model        VARCHAR(50),

    generated_at TIMESTAMP DEFAULT now(),
    sent_at      TIMESTAMP,   -- penanda broadcast Telegram; NULL = belum terkirim

    CONSTRAINT uq_bmdr_date UNIQUE (date)
);

CREATE INDEX IF NOT EXISTS ix_bigmoney_daily_report_date ON bigmoney_daily_report (date);


-- ── LANGKAH 6 — Kolom Telegram di `profiles` (INI YANG WAJIB MANUAL) ──────────
-- `profiles` adalah tabel produksi yang sedang dipakai login. create_all() tak
-- akan pernah menyentuhnya, jadi tanpa langkah ini endpoint Telegram akan gagal
-- dengan "no such column".
--
-- Penautan memakai kode sekali pakai yang diterbitkan untuk user yang SEDANG
-- LOGIN — bukan dengan mengetik email di bot. Email itu identitas, bukan bukti
-- kepemilikan: kalau email jadi kuncinya, siapa pun yang tahu email orang lain
-- bisa membajak notifikasinya.
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS telegram_chat_id         VARCHAR(32);
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS telegram_link_code       VARCHAR(12);
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS telegram_code_expires_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS ix_profiles_telegram_chat_id ON profiles (telegram_chat_id);


-- ── LANGKAH 7 (OPSIONAL) — Kunci tabel dari akses klien langsung ──────────────
-- Seluruh data Big Money hanya diakses lewat backend (yang sudah membatasi ke
-- tier dev). Frontend TIDAK pernah menanyakannya langsung ke Supabase.
--
-- Mengaktifkan RLS tanpa policy apa pun berarti: anon key dan authenticated key
-- tidak bisa membaca tabel ini sama sekali, sementara backend — yang tersambung
-- lewat koneksi Postgres langsung — tetap leluasa. Itu default yang aman.
--
-- Lewati langkah ini bila Anda berencana membaca tabel ini dari frontend.
ALTER TABLE bigmoney_stock_daily      ENABLE ROW LEVEL SECURITY;
ALTER TABLE bigmoney_market_regime    ENABLE ROW LEVEL SECURITY;
ALTER TABLE bigmoney_score            ENABLE ROW LEVEL SECURITY;
ALTER TABLE bigmoney_top_accumulation ENABLE ROW LEVEL SECURITY;
ALTER TABLE bigmoney_daily_report     ENABLE ROW LEVEL SECURITY;


-- ── LANGKAH 8 — Verifikasi ────────────────────────────────────────────────────
-- Harus mengembalikan 5 baris (kelima tabel) dan 3 baris (kolom Telegram).
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public' AND table_name LIKE 'bigmoney%'
ORDER BY table_name;

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'profiles' AND column_name LIKE 'telegram%'
ORDER BY column_name;


-- ============================================================================
-- SETELAH MIGRASI: isi datanya
--
-- Tabel di atas masih KOSONG. Engine butuh jendela 20 hari bursa untuk menghitung
-- fitur, jadi tanpa backfill, skor sebulan pertama akan tipis dan menyesatkan.
-- Jalankan sekali dari laptop, dengan DATABASE_URL diarahkan ke Supabase:
--
--   cd backend
--   DATABASE_URL="<connection string Supabase>" ./venv/Scripts/python.exe scripts/bigmoney_backfill.py --days 90
--   DATABASE_URL="<connection string Supabase>" ./venv/Scripts/python.exe scripts/bigmoney_score.py --days 90
--
-- ~4 menit + ~2 menit. Hasilnya ~74 ribu baris (belasan MB) — kecil untuk kuota
-- gratis Supabase. Setelah itu workflow bigmoney-daily.yml merawatnya tiap hari.
-- ============================================================================
