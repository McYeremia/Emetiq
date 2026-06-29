# 🚀 IDXAnalyst — Next-Gen AI Trading Terminal

IDXAnalyst adalah platform intelijen dan simulasi trading saham Indonesia (IDX) yang menggabungkan presisi **Quant Algorithms** dengan kekuatan **Agentic AI (Gemini & Claude)**. Dirancang sebagai "Battleground" strategi, platform ini memungkinkan Anda mengadu strategi manual melawan kecerdasan statistik AI.

![Landing Page](https://via.placeholder.com/800x400?text=IDXAnalyst+Terminal+Preview)

## 🌟 Fitur Utama

### 1. ⚔️ AI Portfolio Battleground
Bandingkan performa tiga entitas berbeda dalam satu dashboard:
*   **User Strategy:** Portofolio untuk eksekusi manual Anda.
*   **Gemini Core:** Eksekusi otomatis berbasis probabilitas oleh Gemini AI.
*   **Claude Core:** Analisis dan eksekusi otonom oleh Claude AI.

### 2. 🛡️ 10 Quant Intelligence Algorithms
Dilengkapi dengan 10 algoritma quant siap pakai yang telah di-backtest selama 5 tahun:
*   *Triple Confirmation (RSI + MACD + MA20)*
*   *Institutional Trend (MA200 + EMA Cross)*
*   *Volatility Sniper (Bollinger Bands + Stoch)*
*   *Dan 7 strategi pro lainnya.*

### 3. 🧬 Techno-Fundamental Intelligence
AI tidak hanya melihat grafik. Setiap sinyal teknikal divalidasi dengan data fundamental real-time:
*   **PE Ratio & PBV Tracking**
*   **Dividend Yield Analysis**
*   **Market Cap Classification**

### 4. 📊 Advanced Market Screener
Penyaring saham otomatis yang adaptif. Kolom data akan berubah secara dinamis sesuai dengan strategi yang Anda pilih untuk memberikan informasi yang paling relevan.

### 5. 🔌 MCP (Model Context Protocol) Integration
Terhubung langsung dengan Claude Desktop atau Gemini CLI, memungkinkan AI untuk:
*   Menganalisis saham melalui perintah suara/chat.
*   Membuka posisi otonom berdasarkan instruksi Anda.
*   Melaporkan status portofolio secara real-time.

---

## 🏗️ Tech Stack

*   **Frontend:** Next.js 15 (App Router), Tailwind CSS, Lightweight Charts (TradingView).
*   **Backend:** FastAPI (Python), SQLAlchemy, Pydantic.
*   **Database:** SQLite.
*   **Data Source:** Yahoo Finance API (yfinance).
*   **Intelligence:** Model Context Protocol (MCP), TA-Lib (Technical Analysis Library).

---

## 🚀 Instalasi & Persiapan

### 1. Prasyarat
*   Python 3.10+
*   Node.js 18+

### 2. Setup Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # atau .\venv\Scripts\activate di Windows
pip install -r requirements.txt
python main.py
```

### 3. Setup Frontend
```bash
cd frontend
npm install
npm run dev
```

### 4. Menjalankan AI Watcher (Background Scanner)
Untuk memicu AI memindai pasar secara manual:
```bash
cd backend
.\venv\Scripts\python.exe services/watcher.py
```

---

## 🤖 Panduan AI Agent (Gemini/Claude)

Anda dapat memerintahkan AI melalui terminal atau chat (jika MCP sudah terhubung):

*   **Analyze:** *"Gemini, analisis BBCA. Apakah strategi Triple Confirmation memberikan sinyal hari ini?"*
*   **Scan:** *"Gemini, jalankan `ai_smart_trade_scan_and_execute` untuk portofolio GEMINI."*
*   **Trade:** *"Claude, beli 20 lot GOTO sekarang karena RSI di bawah 30."*

---

## 🛡️ Security & Privacy
Seluruh strategi kustom Anda disimpan di folder `frontend/strategies_local/` yang secara otomatis masuk ke `.gitignore`. Rahasia dagang dan algoritma Anda tetap aman di komputer lokal Anda.

---

## 📈 Roadmap Pengembangan
- [x] Phase 1: Foundation (Backend & DB)
- [x] Phase 2: Professional UI/UX
- [x] Phase 3: Quant Backtest Engine
- [x] Phase 4: AI Battleground & Fundamental Integration
- [ ] Phase 5: Live Notifications & Email Alerts
- [ ] Phase 6: Machine Learning Price Prediction

© 2026 IDXAnalyst Terminal. Built for the next generation of data-driven traders.
