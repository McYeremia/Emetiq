# EMETIQ — Monitoring & Analisis Saham IDX

EMETIQ adalah aplikasi web untuk **memantau dan menganalisis saham IDX** memakai data
**EOD (End-of-Day)** dari database lokal. Proyek ini sedang **migrasi** dari konsep lama
*"IDXAnalyst AI Battle"* (paper-trading CLAUDE vs GEMINI vs USER) menjadi aplikasi
**monitoring pribadi** bertema terang dengan brand **EMETIQ**.

Saat bekerja di repo ini, perlakukan diri sebagai **asisten coding** untuk codebase EMETIQ
(bukan sebagai trading agent). Fitur trading-by-AI masih direncanakan, belum aktif.

## Arsitektur
- **Frontend** (`frontend/`): Next.js (App Router), React 19, Tailwind v4, `lightweight-charts`.
- **Backend** (`backend/`): FastAPI + SQLAlchemy + SQLite. Data EOD dari Yahoo Finance (`yfinance`), refresh ~16:00 WIB.
- **MCP** server `IDXAnalyst`: menyediakan tool trading (lihat bagian akhir) untuk fitur **"Trade with AI"** yang direncanakan.

## Menjalankan
```bash
# Backend
cd backend
python -m venv venv && .\venv\Scripts\activate   # (Windows) atau source venv/bin/activate
pip install -r requirements.txt
python main.py

# Frontend
cd frontend
npm install
npm run dev
```

## Tema EMETIQ (light)
- Background `#FCFCFB`, teks `#14140F`, accent oranye `#F26A1B`, hairline `#ECEBE6`.
- Naik/turun: hijau `#138A50` / merah `#D23B3B`.
- Font: **Plus Jakarta Sans** (sans) + **IBM Plex Mono** (angka). Di-inject per halaman via `<link>` (di-hoist React 19 ke `<head>`).
- Tidak memakai em-dash (`—`) pada teks UI yang tampil ke user; pakai hyphen biasa.

## Status migrasi UI (per halaman)
Sudah bertema EMETIQ terang:
- `app/page.tsx` — landing. Tombol "Launch the App" → `/overview`.
- `app/overview/page.tsx` — **halaman masuk** aplikasi: IHSG hari ini + Watchlist (kiri), Top Gainer + Top Loser (kanan).
- `app/dashboard/page.tsx` — **Market**: list saham, filter cepat indeks (IDX30/LQ45/SRI-KEHATI/JII/ISSI), sort, infinite scroll, IHSG line chart (hijau/merah, tanpa zoom, ~2 bulan).
- `app/screener/page.tsx` — 3 tab: **Strategi Teknikal**, **Fundamental**, **Backtest**.
- `app/portfolio/page.tsx` — **USER-only**; tab Portofolio / Analitik / Riwayat.

Belum dimigrasi (masih tema gelap IDXAnalyst): `/broker-flow`, detail saham `/stocks/[ticker]`.

## Konvensi penting
- **Nav bersama**: `components/EmetiqNav.tsx` → `<EmetiqNav active="overview|market|screener|portfolio" />`. Punya menu hamburger di mobile.
- **Header gelap lama** `components/Header.tsx` `return null` pada rute yang sudah dimigrasi. **Saat memigrasi halaman baru, tambahkan rutenya** ke null-check itu dan ke `ITEMS` di `EmetiqNav` bila perlu.
- **Screener** memakai state berbasis URL (`?tab=`, `?strat=`) dengan `useRouter`/`useSearchParams`, dibungkus `<Suspense>` agar tombol back/forward browser benar. Jangan kembalikan ke `useState` untuk tab/strat.
- **Backtest digabung** ke screener (tab Backtest, ranking saja, tanpa equity curve). `app/backtest/page.tsx` hanya `redirect('/screener?tab=backtest')`.
- **Portofolio** de-battle: hanya USER (`getPortfolio().USER`). Halaman detail transaksi sudah dihapus.
- Index membership untuk filter Market di-hardcode di `lib/indices.ts` (statis, perlu update saat IDX rebalance).
- Komponen chart: `StockChart` (`light`, `chartType`, `interactive`, `lineColor`) dan `EquityChart` (`light`).
- **Sebelum menulis kode frontend, baca `frontend/AGENTS.md`** — versi Next.js di repo ini punya breaking changes; cek dokumen di `node_modules/next/dist/docs/` bila ragu.

## Fitur AI Trading (rencana / legacy MCP)
Server MCP `IDXAnalyst` masih menyediakan tool berikut (dipakai untuk fitur "Trade with AI" yang akan datang; agen `USER`/`GEMINI`/`CLAUDE` masih ada di data backend):
`get_agent_context`, `list_available_stocks`, `analyze_stock`, `get_portfolio_summary`,
`get_trade_history`, `execute_ai_trade`, `set_position_target`.
