# 📈 EMETIQ

> **Intelligence built on truth.**

**EMETIQ** adalah platform untuk **memantau, menganalisis, dan mendiskusikan saham
Indonesia (IDX)** — watchlist, portofolio, screener, **AI Advisor**, dan pelacak aliran
dana besar **Big Money** dalam satu tempat, dengan tampilan bersih bertema terang yang
responsif di desktop maupun mobile.

Namanya menggabungkan dua akar kata: **Emet** (אֶמֶת, "kebenaran" dalam bahasa Ibrani)
dan **IQ** (kecerdasan). Filosofinya sederhana — kecerdasan yang dibangun di atas data
yang benar. Setiap sinyal, skor, dan saran di EMETIQ berangkat dari data pasar nyata,
bukan tebakan.

---

## 🌟 Fitur

### 🏠 Overview
Halaman utama: ringkasan **IHSG hari ini**, **Watchlist** pribadi, serta **Top Gainer**
dan **Top Loser** pasar hari ini.

### 📊 Market
Daftar saham dengan **filter cepat indeks** (IDX30, LQ45, SRI-KEHATI, JII, ISSI),
pengurutan (nama / harga / %), pemuatan bertahap (infinite scroll), dan grafik IHSG
yang warnanya mengikuti arah (hijau saat naik, merah saat turun).

### 🔎 Screener (3 mode)
- **Strategi Teknikal** — pindai pasar memakai preset strategi (Triple Confirmation, Institutional Trend, Volatility Sniper, dll).
- **Fundamental** — saring berdasarkan PE, PBV, dividend yield, dan sektor.
- **Backtest** — pilih aset, jalankan semua strategi, lihat **ranking** hasilnya.

### 💼 Portofolio
Posisi aktif (invested + avg price, market value + lot, P&L), grafik pertumbuhan,
**Analitik** (win rate, max drawdown, alokasi, P&L bulanan), dan **Riwayat** transaksi.
Setiap pengguna punya portofolio & watchlist sendiri.

### 🤖 AI Advisor
Asisten saham berbahasa natural (didukung **Groq**). Bisa **mencari saham** sesuai
kriteria, **menganalisis satu saham**, dan memberi **saran portofolio** — lengkap dengan
skor keyakinan. Riwayat percakapan tersimpan per sesi, dengan kuota mengikuti tier akun.
Saran AI bersifat edukatif, **bukan** rekomendasi finansial.

### 🧪 AI Porto _(tier dev)_
Portofolio yang dikelola AI lewat percakapan: kamu beri arahan, AI yang menyusun dan
mengeksekusi transaksinya di bucket terpisah, lengkap dengan riwayat trade dan alasan
di balik tiap keputusan.

### 🐋 Big Money _(tier dev)_
Melacak **jejak uang besar** di bursa. Tiap sore, ringkasan perdagangan IDX ditarik untuk
seluruh pasar (~965 saham), lalu mesin skor menandai saham yang sedang **diakumulasi**
asing — bukan sekadar yang naik paling tinggi hari itu. Posisi akumulasi dilacak lintas
hari (dibuka, dipantau, ditutup), bukan hanya peringkat harian.

Di atasnya berdiri tim AI (**Gemini**): pekerja berita, pekerja aliran dana, dan seorang
kritikus, dengan supervisor yang memutuskan hari itu layak dikabarkan atau tidak. Setiap
angka lewat pemeriksa fakta deterministik sebelum masuk laporan. Hasilnya bisa dikirim ke
**bot Telegram** yang ditautkan ke akunmu lewat kode sekali pakai.

> Nilai aliran dana asing adalah **estimasi** (net lembar × VWAP pasar) — IDX tidak
> menyediakan harga per sisi asing. Alat bantu analisis, bukan nasihat investasi.

### 🔐 Akun & Tier
Login/registrasi lewat **Supabase Auth** (verifikasi email), dengan sistem **tier** yang
mengatur batas penggunaan (mis. kuota AI Advisor) dan membuka fitur eksperimental (Big
Money, AI Porto) hanya untuk tier `dev`. Data tiap pengguna terisolasi lewat Row-Level
Security (RLS) di Supabase. Ada halaman **admin** untuk mengatur tier pengguna.

---

## 🏗️ Tech Stack

| Lapisan | Teknologi |
|---|---|
| **Frontend** | Next.js 16 (App Router), React 19, Tailwind CSS v4, Lightweight Charts 5 |
| **Backend** | FastAPI (Python), SQLAlchemy 2, Pydantic |
| **Database** | PostgreSQL (via **Supabase**) |
| **Auth** | Supabase Auth (JWT) + Row-Level Security |
| **AI** | **Groq** (AI Advisor & AI Porto) · **Gemini** (laporan Big Money) |
| **ML** | scikit-learn — prediksi harga, dilatih ulang tiap hari |
| **Data** | Yahoo Finance (`yfinance`) untuk harga EOD · **API IDX Trading Summary** untuk aliran dana asing |
| **Otomasi** | GitHub Actions — sinkron harga + latih ulang ML (17:00 WIB), pipeline Big Money (17:30 WIB), Senin–Jumat |
| **Notifikasi** | Bot Telegram (laporan harian Big Money) |
| **Deploy** | Frontend → **Vercel** · Backend → **Hugging Face Spaces** · DB/Auth → **Supabase** |

**Tema EMETIQ:** latar `#FCFCFB`, accent oranye `#F26A1B`, font Plus Jakarta Sans + IBM Plex Mono.

---

## 🚀 Instalasi & Menjalankan

### Prasyarat
- Python 3.10+
- Node.js 18+
- Project **Supabase** (URL + JWT secret) dan **Groq API key**

### 1. Backend
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate        # Windows  (atau: source venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env           # lalu isi nilainya
python main.py
```

`backend/.env` (lihat `.env.example` untuk penjelasan tiap variabel):
```env
DATABASE_URL=postgresql://...        # connection string Supabase Postgres
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_JWT_SECRET=...              # untuk verifikasi JWT
GROQ_API_KEY=...                     # AI Advisor & AI Porto

# Big Money — semuanya OPSIONAL. Tanpa ini, ingest IDX dan skor tetap jalan penuh;
# hanya laporan AI dan notifikasi Telegram yang dilewati.
GEMINI_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_WEBHOOK_SECRET=...
```

### 2. Frontend
```bash
cd frontend
npm install
cp .env.local.example .env.local     # lalu isi nilainya
npm run dev
```

`frontend/.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SITE_URL=http://localhost:3000
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

Buka `http://localhost:3000`, daftar/masuk, lalu mulai dari **Overview**.
Pastikan backend berjalan agar data pasar termuat.

### 3. Data & pekerjaan batch
```bash
cd backend
.\venv\Scripts\python.exe scripts/daily_sync.py                    # harga 5 hari terakhir + latih ulang ML
.\venv\Scripts\python.exe scripts/bigmoney_daily.py                # ingest IDX + skor + laporan (hari ini)
.\venv\Scripts\python.exe scripts/bigmoney_daily.py --no-report    # skor saja, tanpa Gemini & Telegram
.\venv\Scripts\python.exe scripts/bigmoney_backfill.py --days 90   # isi riwayat Big Money
```
Di produksi ketiganya dijadwalkan lewat **GitHub Actions** (`.github/workflows/`).

### Tes
```bash
cd backend
.\venv\Scripts\python.exe -m pytest tests/ -q      # 358 tes
```

---

## 🗺️ Status & Roadmap

- [x] Backend, database (Postgres/Supabase), data EOD
- [x] Screener teknikal + fundamental + backtest (satu halaman)
- [x] Rebrand & UI tema terang EMETIQ, responsif mobile
- [x] Portofolio & watchlist per-pengguna
- [x] Login + tier via Supabase Auth (RLS aktif) + halaman admin
- [x] AI Advisor (chat, Groq, kuota per-tier)
- [x] AI Porto — portofolio yang dikelola AI lewat percakapan _(tier dev)_
- [x] Big Money — ingest IDX, mesin skor, pelacakan posisi, tim AI Gemini, bot Telegram _(tier dev)_
- [x] Prediksi harga berbasis ML + sinkron harian otomatis (GitHub Actions)
- [ ] **Jalur otomatis Big Money** — IDX menolak IP datacenter (403 dari runner GitHub), pipeline masih dijalankan manual
- [ ] PWA — installable / standalone (add to home screen)
- [ ] Big Money keluar dari tier dev (rilis publik)

---

## 🛡️ Catatan
Strategi kustom disimpan di `frontend/strategies_local/` dan masuk `.gitignore`,
jadi algoritma kamu tetap aman di komputer lokal.

EMETIQ menampilkan data untuk **pemantauan & edukasi** — **bukan rekomendasi
beli/jual**. Keputusan dan risiko sepenuhnya di tanganmu.

---

<p align="center"><strong>EMETIQ</strong> — Intelligence built on truth.<br/>© 2026</p>
