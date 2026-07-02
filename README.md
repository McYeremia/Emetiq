# 📈 EMETIQ

> **Intelligence built on truth.**

**EMETIQ** adalah platform untuk **memantau, menganalisis, dan mendiskusikan saham
Indonesia (IDX)** — watchlist, portofolio, screener, dan **AI Advisor** dalam satu
tempat, dengan tampilan bersih bertema terang yang responsif di desktop maupun mobile.

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

### 🔐 Akun & Tier
Login/registrasi lewat **Supabase Auth** (verifikasi email), dengan sistem **tier** yang
mengatur batas penggunaan (mis. kuota AI Advisor). Data tiap pengguna terisolasi lewat
Row-Level Security (RLS) di Supabase.

---

## 🏗️ Tech Stack

| Lapisan | Teknologi |
|---|---|
| **Frontend** | Next.js 16 (App Router), React 19, Tailwind CSS v4, Lightweight Charts 5 |
| **Backend** | FastAPI (Python), SQLAlchemy 2, Pydantic |
| **Database** | PostgreSQL (via **Supabase**) |
| **Auth** | Supabase Auth (JWT) + Row-Level Security |
| **AI** | Groq (LLM) |
| **Data** | Yahoo Finance (`yfinance`), End-of-Day (refresh ~16:00 WIB) |
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

`backend/.env`:
```env
DATABASE_URL=postgresql://...        # connection string Supabase Postgres
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_JWT_SECRET=...              # untuk verifikasi JWT
GROQ_API_KEY=...                     # untuk AI Advisor
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

### Refresh / Scan data (opsional)
```bash
cd backend
.\venv\Scripts\python.exe services/watcher.py
```

---

## 🗺️ Status & Roadmap

- [x] Backend, database (Postgres/Supabase), data EOD
- [x] Screener teknikal + fundamental + backtest (satu halaman)
- [x] Rebrand & UI tema terang EMETIQ, responsif mobile
- [x] Portofolio & watchlist per-pengguna
- [x] Login + tier via Supabase Auth (RLS aktif)
- [x] AI Advisor (chat, Groq, kuota per-tier)
- [ ] PWA — installable / standalone (add to home screen)
- [ ] Migrasi halaman tersisa (Broker Flow, detail saham)
- [ ] Notifikasi & prediksi harga berbasis ML

---

## 🛡️ Catatan
Strategi kustom disimpan di `frontend/strategies_local/` dan masuk `.gitignore`,
jadi algoritma kamu tetap aman di komputer lokal.

EMETIQ menampilkan data untuk **pemantauan & edukasi** — **bukan rekomendasi
beli/jual**. Keputusan dan risiko sepenuhnya di tanganmu.

---

<p align="center"><strong>EMETIQ</strong> — Intelligence built on truth.<br/>© 2026</p>
