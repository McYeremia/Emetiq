# 📈 EMETIQ — Monitoring Saham IDX

**EMETIQ** adalah dashboard untuk **memantau dan menganalisis saham Indonesia (IDX)**
memakai data **End-of-Day (EOD)**. Fokusnya sederhana: satu tempat untuk watchlist,
portofolio, dan screener, dengan tampilan bersih yang diperbarui tiap sore.

> Proyek ini sedang bertransformasi dari konsep lama *"IDXAnalyst AI Battle"*
> (paper-trading AI vs manusia) menjadi aplikasi **monitoring pribadi** bertema terang.
> Sebagian halaman sudah memakai brand & tema baru **EMETIQ**, sebagian masih dalam proses.

---

## 🌟 Fitur

### 🏠 Overview
Halaman masuk aplikasi: ringkasan **IHSG hari ini**, **Watchlist** kamu, serta
**Top Gainer** dan **Top Loser** pasar hari ini.

### 📊 Market
Daftar saham dengan **filter cepat indeks** (IDX30, LQ45, SRI-KEHATI, JII, ISSI),
pengurutan (nama / harga / %), pemuatan bertahap (infinite scroll), dan grafik IHSG
garis yang warnanya mengikuti arah (hijau saat naik, merah saat turun).

### 🔎 Screener (3 mode)
- **Strategi Teknikal** — pindai pasar memakai preset strategi (Triple Confirmation, Institutional Trend, Volatility Sniper, dll).
- **Fundamental** — saring berdasarkan PE, PBV, dividend yield, dan sektor.
- **Backtest** — pilih aset, jalankan semua strategi, lihat **ranking** hasilnya.

### 💼 Portofolio
Posisi aktif (invested + avg price, market value + lot, P&L), grafik pertumbuhan,
**Analitik** (win rate, max drawdown, alokasi, P&L bulanan), dan **Riwayat** transaksi.

### 🤖 Trade with AI *(direncanakan)*
Integrasi eksekusi otonom berbasis AI lewat **Model Context Protocol (MCP)** masih dalam
pengembangan. Tombolnya sudah ada di UI, fungsinya menyusul.

---

## 🏗️ Tech Stack

| Lapisan | Teknologi |
|---|---|
| **Frontend** | Next.js (App Router), React 19, Tailwind CSS v4, Lightweight Charts |
| **Backend** | FastAPI (Python), SQLAlchemy, Pydantic |
| **Database** | SQLite |
| **Data** | Yahoo Finance (`yfinance`), EOD (refresh ~16:00 WIB) |
| **AI (rencana)** | Model Context Protocol (MCP) |

**Tema EMETIQ:** latar `#FCFCFB`, accent oranye `#F26A1B`, font Plus Jakarta Sans + IBM Plex Mono.

---

## 🚀 Instalasi & Menjalankan

### Prasyarat
- Python 3.10+
- Node.js 18+

### Backend
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate        # Windows  (atau: source venv/bin/activate)
pip install -r requirements.txt
python main.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Buka `http://localhost:3000` lalu klik **Launch the App** (menuju `/overview`).
Pastikan backend berjalan agar data pasar termuat.

### Refresh / Scan data (opsional)
```bash
cd backend
.\venv\Scripts\python.exe services/watcher.py
```

---

## 🗺️ Status & Roadmap

**Sudah bertema EMETIQ terang:** Landing, Overview, Market, Screener, Portofolio.
**Masih tema lama (akan dimigrasi):** Broker Flow, halaman detail saham.

- [x] Backend, database, data EOD
- [x] Screener teknikal + fundamental + backtest (digabung jadi satu halaman)
- [x] Rebrand & migrasi UI ke tema terang EMETIQ (bertahap, mobile-friendly)
- [x] Portofolio personal (USER-only)
- [ ] Migrasi halaman tersisa (Broker Flow, detail saham)
- [ ] Fitur "Trade with AI" (eksekusi via MCP)
- [ ] Notifikasi & prediksi harga berbasis ML

---

## 🛡️ Catatan
Strategi kustom disimpan di `frontend/strategies_local/` dan masuk `.gitignore`,
jadi algoritma kamu tetap aman di komputer lokal.

EMETIQ menampilkan data EOD untuk pemantauan — **bukan rekomendasi beli/jual**. Risiko di tangan kamu.

© 2026 EMETIQ
