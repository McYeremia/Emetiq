# IDXAnalyst — Design Spec
**Date:** 2026-04-26  
**Status:** Approved

---

## Overview

IDXAnalyst adalah web app personal untuk analisis dan backtesting saham Indonesia (IDX80). App ini memungkinkan user untuk melihat chart candlestick harian, menjalankan automated backtest berbasis strategi indikator, melakukan manual paper trading, dan mendapatkan analisis AI dari Claude Code via MCP — semuanya tanpa biaya tambahan di luar Claude Pro yang sudah ada.

**Scope:** 80 saham IDX80 (saham berkapitalisasi besar Indonesia)  
**Data:** End-of-day (EOD) via yfinance, suffix `.JK`  
**AI:** Claude Code sebagai MCP server (hybrid — web tetap functional tanpa Claude aktif)  
**Deployment:** Lokal dulu, lalu free hosting (Vercel + Railway/Supabase)

---

## Architecture

```
[yfinance API]
      ↓ (fetch EOD tiap hari)
[FastAPI Backend] ←→ [SQLite DB (SQLAlchemy ORM)]
      ↓ REST API + MCP Server
[Next.js Frontend]
  ├── TradingView Lightweight Charts
  ├── Backtest UI
  └── AI Analysis Panel (disabled saat Claude Code tidak aktif)
      ↑
[Claude Code] → MCP tools → call FastAPI endpoints
```

**Key decision:** FastAPI berfungsi ganda sebagai REST API dan MCP server. SQLite untuk development lokal, migrasi ke PostgreSQL (Supabase) saat deploy dengan ubah 1 baris config di SQLAlchemy.

---

## Tech Stack

| Layer | Tech | Versi |
|-------|------|-------|
| Frontend | Next.js + React | 15 |
| Charts | TradingView Lightweight Charts | latest (open source) |
| Backend | FastAPI (Python) | latest |
| ORM | SQLAlchemy | 2.x |
| Database | SQLite (lokal) → PostgreSQL (production) | - |
| Data Source | yfinance | latest |
| Indikator | pandas-ta | latest |
| AI Engine | Claude Code via MCP | - |
| MCP Library | mcp (Python) | latest |

---

## Database Schema

### `stocks`
| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| id | INTEGER PK | |
| ticker | TEXT UNIQUE | e.g. "BBCA" |
| name | TEXT | e.g. "Bank Central Asia" |
| sector | TEXT | e.g. "Finance" |
| market_cap_cat | TEXT | large/mid |
| last_updated | DATETIME | timestamp update terakhir |

### `ohlcv_daily`
| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| id | INTEGER PK | |
| stock_id | INTEGER FK → stocks | |
| date | DATE | |
| open | REAL | |
| high | REAL | |
| low | REAL | |
| close | REAL | |
| volume | INTEGER | |
| adj_close | REAL | |

### `indicators_cache`
| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| id | INTEGER PK | |
| stock_id | INTEGER FK → stocks | |
| date | DATE | |
| indicator_type | TEXT | e.g. "RSI_14", "EMA_50" |
| value | REAL | |
| calculated_at | DATETIME | |

### `strategies`
| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| id | INTEGER PK | |
| name | TEXT | nama strategi |
| conditions | JSON | kondisi entry/exit |
| parameters | JSON | stop loss %, take profit % |
| created_at | DATETIME | |

### `backtest_runs`
| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| id | INTEGER PK | |
| strategy_id | INTEGER FK → strategies | |
| stock_id | INTEGER FK → stocks | satu saham per run (NOT NULL untuk saat ini) |
| date_from | DATE | |
| date_to | DATE | |
| total_trades | INTEGER | |
| win_rate | REAL | 0.0–1.0 |
| profit_factor | REAL | |
| max_drawdown | REAL | |
| sharpe_ratio | REAL | |
| total_return | REAL | |
| equity_curve | JSON | array nilai portofolio per hari |
| trades_detail | JSON | array semua trades |
| created_at | DATETIME | |

### `trade_logs`
| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| id | INTEGER PK | |
| stock_id | INTEGER FK → stocks | |
| action | TEXT | "BUY" / "SELL" |
| date | DATE | tanggal transaksi |
| price | REAL | harga per saham |
| quantity | INTEGER | jumlah lot (1 lot = 100 saham) |
| trade_type | TEXT | "MANUAL" / "AUTO" |
| backtest_run_id | INTEGER FK nullable | untuk AUTO trades |
| notes | TEXT | opsional |
| created_at | DATETIME | |

---

## Backend API Endpoints

### Stocks & Data
```
GET  /stocks                           List IDX80 dengan harga terakhir + sinyal
GET  /stocks/{ticker}/ohlcv            Historical candles (query: from, to) — daily only
GET  /stocks/{ticker}/indicators       Nilai semua indikator terkini
POST /stocks/refresh                   Fetch data baru dari yfinance (semua IDX80)
POST /stocks/{ticker}/refresh          Fetch data baru untuk 1 saham saja
```

### Backtest
```
POST /backtest/run                     Jalankan automated backtest
GET  /backtest/{id}                    Hasil backtest (metrics + equity curve + trades)
GET  /backtest/history                 List semua backtest runs
DELETE /backtest/{id}                  Hapus backtest run
```

### Trades (Manual Paper Trading)
```
GET  /trades                           Semua trade log + P&L summary (query: ticker)
POST /trades                           Tambah entry BUY/SELL
DELETE /trades/{id}                    Hapus entry
GET  /trades/portfolio                 Posisi open + unrealized P&L saat ini
```

### Strategies
```
GET  /strategies                       List saved strategies
POST /strategies                       Simpan strategy baru
PUT  /strategies/{id}                  Update strategy
DELETE /strategies/{id}                Hapus strategy
```

### AI Bridge
```
POST /ai/analysis-request              Web kirim request analisis ke queue
GET  /ai/analysis-request/pending      Claude Code poll (ambil request pending)
POST /ai/analysis-result               Claude Code submit hasil analisis
GET  /ai/analysis/{ticker}             Frontend ambil hasil analisis terbaru per saham
```

---

## Backtesting Engine

### A) Manual Paper Trading
- User klik tanggal di chart → pilih Buy/Sell
- Input: harga (auto-fill closing price hari itu), jumlah lot, notes
- Disimpan ke `trade_logs` dengan `trade_type = MANUAL`
- P&L kalkulasi:
  - **Realized P&L** = (sell_price - buy_price) × quantity × 100
  - **Unrealized P&L** = (current_price - buy_price) × quantity × 100
  - **Win Rate** = profitable closed trades / total closed trades

### B) Automated Backtest Engine
Strategy definition format (JSON):
```json
{
  "entry": [
    { "indicator": "RSI_14", "operator": "<", "value": 30 },
    { "indicator": "price", "operator": "above", "reference": "EMA_50" }
  ],
  "exit": [
    { "indicator": "RSI_14", "operator": ">", "value": 70 }
  ],
  "stop_loss_pct": 5.0,
  "take_profit_pct": 15.0,
  "initial_capital": 10000000
}
```

Engine loop:
1. Load OHLCV + hitung semua indikator yang dibutuhkan untuk date range
2. Iterate candle per candle secara kronologis
3. Jika tidak ada posisi open → cek entry conditions → beli di closing price
4. Jika ada posisi open → cek exit conditions + stop loss + take profit → jual
5. Kumpulkan semua trades → hitung metrics
6. Simpan equity curve (nilai portofolio per hari) sebagai JSON array

**Output Metrics:**
| Metrik | Formula |
|--------|---------|
| Win Rate | profitable trades / total trades |
| Profit Factor | gross profit / gross loss |
| Max Drawdown | peak-to-trough equity drop terbesar |
| Sharpe Ratio | (avg daily return - 0) / std dev daily return × √252 |
| Total Return | (final equity - initial) / initial × 100% |

---

## Frontend Structure

```
frontend/
├── app/
│   ├── page.tsx                   Dashboard: IDX80 grid + sinyal
│   ├── stocks/[ticker]/page.tsx   Chart + indikator + add trade
│   ├── backtest/page.tsx          Strategy builder + run + hasil
│   ├── trades/page.tsx            Manual trade log + P&L
│   ├── strategies/page.tsx        Saved strategies list + compare
│   └── ai/page.tsx                AI analysis panel
├── components/
│   ├── StockChart.tsx             TradingView Lightweight Charts wrapper
│   ├── IndicatorOverlay.tsx       Toggle overlay indikator
│   ├── TradeMarker.tsx            Marker buy/sell di chart
│   ├── StrategyBuilder.tsx        Form kondisi entry/exit
│   ├── BacktestResults.tsx        Equity curve + metrics + trade table
│   ├── TradeLog.tsx               Tabel trade + P&L
│   ├── StockSearch.tsx            Search + filter IDX80
│   └── AIPanel.tsx                Claude analysis display + status
└── lib/
    └── api.ts                     Fetch wrapper ke FastAPI
```

**Halaman:**
- **Dashboard** — grid IDX80, harga terakhir, % change, sinyal (hijau/merah/netral), filter sektor
- **Chart Page** — candlestick + overlay indikator, tombol Add Trade, AI panel sidebar
- **Backtest** — pilih saham + date range + strategy → Run → equity curve + metrics + trades
- **Trades** — log semua manual trades, P&L per saham, total portfolio P&L
- **Strategies** — list saved strategies, compare side-by-side
- **AI Panel** — status Claude aktif/tidak, queue analisis, hasil tersimpan per saham

---

## AI Integration (MCP Hybrid)

### Setup (sekali)
Tambah ke Claude Code MCP settings (`~/.claude/settings.json`):
```json
{
  "mcpServers": {
    "idxanalyst": {
      "command": "python",
      "args": ["backend/mcp_server.py"],
      "cwd": "C:/10. Belajar/01. Analysis Saham/IDXAnalyst"
    }
  }
}
```

### MCP Tools
| Tool | Parameter | Return |
|------|-----------|--------|
| `get_stock_data` | ticker, days | OHLCV + semua indikator |
| `get_all_signals` | - | Snapshot semua IDX80 + sinyal |
| `get_backtest_result` | id | Metrics + equity curve + trades |
| `run_quick_analysis` | ticker | Data siap analisis (ringkas) |
| `get_trade_portfolio` | - | Posisi open + realized P&L |

### Flow Harian
```
1. User klik "Analyze BBCA" di web
2. Web POST /ai/analysis-request {ticker: "BBCA"}
3. User buka Claude Code, ketik "analisis BBCA.JK"
4. Claude → get_stock_data("BBCA", 90) → analisis → POST /ai/analysis-result
5. Web auto-refresh → tampilkan hasil + timestamp
```

### Fallback (Claude tidak aktif)
AI Panel menampilkan:
> *"Claude tidak aktif. Buka Claude Code dan ketik 'analisis [ticker]' untuk memulai analisis."*
Hasil analisis sebelumnya tetap tampil dengan timestamp kapan dianalisis.

---

## Phase Plan

### Phase 1 — Foundation
- Setup FastAPI + SQLAlchemy + SQLite
- `data/idx80.json` dengan 80 saham IDX80 + sektor
- Data pipeline yfinance: fetch 5 tahun historis semua IDX80
- Daily update endpoint
- Indikator: MA(20,50,200), EMA(12,26), RSI(14), MACD(12,26,9), BB(20), Stochastic(14), ATR(14), Volume MA(20)
- Endpoints: `/stocks`, `/stocks/{ticker}/ohlcv`, `/stocks/{ticker}/indicators`, `/stocks/refresh`

### Phase 2 — Frontend: Chart & Browse
- Setup Next.js 15
- Dashboard IDX80: grid + filter sektor + sinyal warna
- Chart page: TradingView Lightweight Charts + toggle indikator overlay
- Stock search + watchlist sidebar (in-memory, belum persistent ke DB)

### Phase 3 — Backtesting
- Manual paper trading: klik chart → add trade → P&L otomatis
- Trade log page: posisi open + realized/unrealized P&L
- Strategy Builder: form kondisi entry/exit + stop loss/take profit
- Automated backtest engine
- Equity curve chart + drawdown chart + metrics table + trade list

### Phase 4 — AI Integration
- `mcp_server.py`: MCP server dengan 5 tools
- Setup instruksi di CLAUDE.md project
- AI Panel di web: request queue + result display
- Natural language strategy: Claude parse teks → strategy JSON

### Phase 5 — Polish & Deploy
- Watchlist DB-backed (simpan ke database + browser notification saat sinyal terpenuhi)
- Save & compare multiple strategies
- Alert: kondisi indikator → notifikasi browser (Web Notifications API)
- Migrasi SQLite → PostgreSQL (Supabase) via SQLAlchemy config
- Deploy: Vercel (frontend) + Railway (backend)

---

## Constraints & Decisions

| Keputusan | Pilihan | Alasan |
|-----------|---------|--------|
| Data source | yfinance EOD | Gratis, cukup untuk swing trading |
| Database | SQLite → PostgreSQL | Zero setup lokal, easy migration |
| AI | Claude Code MCP hybrid | Gratis (sudah Pro), tidak butuh API key |
| Scope | IDX80 saja | 80 saham manageable, bisa expand nanti |
| Timeframe | Daily candles | EOD data, cocok untuk swing/position trading |
| Redis | Tidak di Phase 1-3 | Premature optimization, tambah nanti kalau perlu |
| Auth | Tidak ada | Personal tool, tidak perlu multi-user |

---

## Out of Scope (saat ini)
- Intraday / real-time data
- Multi-user / authentication
- True live trading (bukan simulasi)
- Lebih dari IDX80 (900+ emiten) — bisa expand di Phase 5+
- Mobile app
- Email/SMS alerts (hanya browser notification)
