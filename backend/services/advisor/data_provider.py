"""Data deterministik untuk AI Advisor — TIDAK memanggil LLM.

Tiga builder: screen(), analyze(), portfolio(). Semua angka diambil dari DB nyata
(fundamental, OHLCV, indikator) sehingga LLM hanya menalar di atas angka yang sudah
pasti benar. Lihat spec bagian 4 ("Detail Pipeline").
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, nullslast

import models
from services.indicators import (
    INDICATOR_MAX_ROWS, calculate_indicators, calculate_indicators_from_df,
    calculate_screen_indicators_from_df, get_ohlcv_df_bulk,
)
from services import trade_exec
from services.advisor import config, scoring
from services.advisor.formatting import round_numbers

# Modal dummy dan replay holding punya SATU sumber kebenaran: services/trade_exec.py.
# Dulu nilainya diketik ulang di sini dengan komentar "samakan dengan routers/trades.py"
# — dua konstanta, satu makna, tanpa pagar. Mengubahnya di satu tempat membuat kas &
# total porto yang dilaporkan Advisor menyimpang dari yang dipakai eksekusi trade,
# tanpa galat apa pun. Bucket "USER" = trade manual milik satu user (di-scope user_id);
# ia TIDAK menyentuh bucket AI mana pun.
from services.trade_exec import INITIAL_MODAL

AGENT_USER = "USER"

# Lookback saat menghitung indikator utk BANYAK saham sekaligus (screening/kandidat).
# Nilai indikator terakhir (RSI/MA/MACD dst) praktis sama dgn histori penuh selama
# jendela ini > window terpanjang (MA_200) — dipakai demi kecepatan (hindari fetch
# 5 tahun histori x ratusan saham).
SCREEN_INDICATOR_LOOKBACK_DAYS = 400


# ── Helper kecil ─────────────────────────────────────────────────────────────

def rsi_band(rsi: Optional[float]) -> Optional[str]:
    if rsi is None:
        return None
    if rsi < 30:
        return "oversold"
    if rsi > 70:
        return "overbought"
    return "neutral"


def trend_of(indicators: dict, last_close: Optional[float]) -> Optional[str]:
    """Tren naik bila harga di atas MA50 (fallback MA20)."""
    if last_close is None:
        return None
    ma50 = indicators.get("MA_50")
    ma20 = indicators.get("MA_20")
    ref = ma50 if ma50 is not None else ma20
    if ref is None:
        return None
    return "up" if last_close >= ref else "down"


# ── Pipeline 1: Screening ────────────────────────────────────────────────────

def screen(
    db: Session,
    *,
    pe_max: Optional[float] = None,
    pbv_max: Optional[float] = None,
    div_min: Optional[float] = None,
    rsi: Optional[str] = None,
    trend: Optional[str] = None,
    sector: Optional[str] = None,
    price_max: Optional[float] = None,
    price_min: Optional[float] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Saring saham deterministik, lalu URUTKAN per skor kecocokan dengan kriteria.

    Dua hal yang dulu keliru dan sekarang tidak lagi:

    1. Indikator hanya dihitung bila user memfilter RSI/tren. Screening "PE di bawah
       15" mengirim seluruh kandidat ke LLM dengan `rsi=None, trend=None` — padahal
       prompt mewajibkan alasan teknikal. Sekarang SELALU dihitung. Ini tidak menambah
       egress sedikit pun: baris harganya toh sudah ditarik di bawah, dengan atau
       tanpa filter. Yang bertambah cuma ~0,4 detik CPU (lihat
       `calculate_screen_indicators_from_df`).

    2. Hasil diurutkan per kapitalisasi dan dipotong, sehingga 15 kursi yang sampai ke
       LLM selalu ditempati perusahaan terbesar. Sekarang kapitalisasi hanya MEMILIH
       working set (demi latency & egress); urutan akhir ditentukan `scoring`.
    """
    limit = limit or config.SCREEN_MAX_CANDIDATES
    filters = {"pe_max": pe_max, "pbv_max": pbv_max, "div_min": div_min}

    # 1) Filter fundamental DI SQL — dulu seluruh tabel Stock (~737 baris, semua
    #    kolom) ditarik ke memori lalu disaring di Python.
    q = db.query(models.Stock).filter(models.Stock.ticker != "^JKSE")
    if pe_max is not None:
        q = q.filter(models.Stock.pe_ratio.isnot(None),
                     models.Stock.pe_ratio > 0, models.Stock.pe_ratio <= pe_max)
    if pbv_max is not None:
        q = q.filter(models.Stock.pbv_ratio.isnot(None),
                     models.Stock.pbv_ratio > 0, models.Stock.pbv_ratio <= pbv_max)
    if div_min is not None:
        q = q.filter(models.Stock.dividend_yield.isnot(None),
                     models.Stock.dividend_yield >= div_min)
    if sector:
        # Sektor NULL tak pernah cocok — sama seperti perilaku lama `(s.sector or "")`.
        q = q.filter(func.lower(models.Stock.sector) == sector.lower())

    # `nullslast()` WAJIB: pada `ORDER BY ... DESC`, Postgres menaruh NULL PALING
    # DEPAN sedangkan SQLite paling belakang. Tanpa ini, saham tanpa market_cap akan
    # memborong seluruh working set di produksi tapi tak pernah muncul di tes.
    survivors = (
        q.order_by(nullslast(desc(models.Stock.market_cap)))
        .limit(config.SCREEN_WORKING_SET)
        .all()
    )

    # 1 query utk histori OHLCV semua survivor (bukan 1 query per saham) — hindari N+1
    ohlcv_by_id = get_ohlcv_df_bulk(
        db, [s.id for s in survivors], lookback_days=SCREEN_INDICATOR_LOOKBACK_DAYS
    )

    results: List[Dict[str, Any]] = []
    for s in survivors:
        df = ohlcv_by_id.get(s.id)
        last_close = float(df["close"].iloc[-1]) if df is not None and not df.empty else None
        # Satu saham berdata tipis tak boleh menjatuhkan seluruh balasan — lihat
        # catatan `_atr_terakhir` di services/indicators.py.
        try:
            inds = calculate_screen_indicators_from_df(df)
        except Exception:
            inds = {}

        if price_max is not None and (last_close is None or last_close > price_max):
            continue
        if price_min is not None and (last_close is None or last_close < price_min):
            continue

        if rsi is not None:
            if rsi_band(inds.get("RSI_14")) != rsi:
                continue
        if trend is not None:
            if trend_of(inds, last_close) != trend:
                continue

        kandidat = {
            "ticker": s.ticker,
            "name": s.name,
            "sector": s.sector,
            "last_price": last_close,
            "market_cap": s.market_cap,
            "pe": s.pe_ratio,
            "pbv": s.pbv_ratio,
            "dividend_yield": s.dividend_yield,
            "rsi": inds.get("RSI_14"),
            "trend": trend_of(inds, last_close) if inds else None,
        }
        # Skor dihitung di atas presisi penuh, SEBELUM pembulatan di bawah.
        kandidat["match_score"] = scoring.skor_kecocokan(kandidat, filters)
        results.append(kandidat)

    # Tak ada `break` di dalam perulangan: seluruh working set harus dinilai lebih
    # dulu, kalau tidak pemotongan kembali memilih per kapitalisasi seperti dulu.
    results.sort(key=lambda c: c["match_score"], reverse=True)

    # Bulatkan semua angka (indikator & fundamental) sebelum dipakai LLM/UI.
    return round_numbers(results[:limit])


# ── Pipeline 2: Analisa 1 saham ──────────────────────────────────────────────

def analyze(db: Session, ticker: str) -> Dict[str, Any]:
    ticker = ticker.upper()
    stock = db.query(models.Stock).filter(models.Stock.ticker == ticker).first()
    if not stock:
        return {"found": False, "ticker": ticker}

    inds = calculate_indicators(db, stock)
    rows = (
        db.query(models.OHLCVDaily)
        .filter(models.OHLCVDaily.stock_id == stock.id)
        .order_by(desc(models.OHLCVDaily.date))
        .limit(60)
        .all()
    )  # terbaru -> terlama
    closes = [float(r.close) for r in rows if r.close is not None]
    last_close = closes[0] if closes else None
    prev_close = closes[1] if len(closes) > 1 else None
    change_pct = (
        round((last_close - prev_close) / prev_close * 100, 2)
        if last_close is not None and prev_close not in (None, 0)
        else None
    )
    # Tertinggi/terendah 20 hari diambil dari kolom high/low, BUKAN dari close.
    # Sebelumnya keduanya dihitung dari `closes` — seperti mengukur tinggi badan
    # orang dari foto saat ia duduk. Angka ini disuntikkan ke prompt sintesis yang
    # menyarankan take-profit "berbasis support/resistance", jadi resistance yang
    # ditaksir terlalu rendah membuat target jual sistematis terlalu cepat.
    # Kolomnya sudah ikut ditarik query di atas — tak ada egress tambahan.
    highs = [float(r.high) for r in rows[:20] if r.high is not None]
    lows = [float(r.low) for r in rows[:20] if r.low is not None]
    high_20 = max(highs) if highs else None
    low_20 = min(lows) if lows else None

    # Bulatkan semua angka (indikator & fundamental) sebelum dipakai LLM/UI.
    return round_numbers({
        "found": True,
        "ticker": ticker,
        "name": stock.name,
        "sector": stock.sector,
        "last_price": last_close,
        "change_pct": change_pct,
        "high_20d": high_20,
        "low_20d": low_20,
        "bars_available": len(closes),
        "fundamentals": {
            "pe": stock.pe_ratio,
            "pbv": stock.pbv_ratio,
            "dividend_yield": stock.dividend_yield,
            "market_cap": stock.market_cap,
        },
        "indicators": inds,
        "rsi_band": rsi_band(inds.get("RSI_14")),
        "trend": trend_of(inds, last_close),
    })


# ── Pipeline 3: Portofolio ───────────────────────────────────────────────────

def portfolio(db: Session, user_id: str) -> Dict[str, Any]:
    """Snapshot holding milik satu user (di-scope berdasarkan user_id trade).

    Replay TradeLog dikerjakan `trade_exec.holdings_for`, BUKAN ditulis ulang di sini.
    Sebelumnya modul ini punya salinan logikanya sendiri — rumus biaya rata-rata,
    perlakuan `quantity * 100`, akumulasi realized — sehingga perbaikan di satu sisi
    tak pernah tercermin di sisi lain, dan tak ada tes yang menuntut keduanya sepakat.
    `trade_exec` memang dibuat untuk itu ("agar aturan dana/holding tidak terduplikasi").
    """
    raw = trade_exec.holdings_for(db, AGENT_USER, user_id)
    realized = sum(p["realized"] for p in raw.values())
    aktif = {tk: p for tk, p in raw.items() if p["shares"] > 0}

    # `holdings_for` memulangkan ticker, bukan stock_id — ambil sekali untuk semuanya.
    stocks = {
        s.ticker: s
        for s in db.query(models.Stock).filter(models.Stock.ticker.in_(list(aktif))).all()
    } if aktif else {}

    active: Dict[str, Dict[str, Any]] = {}
    for ticker, pos in aktif.items():
        stock = stocks.get(ticker)
        if stock is None:      # ticker hilang dari master — jangan jatuhkan seluruh balasan
            continue
        active[ticker] = {**pos, "stock_id": stock.id}
    # 1 query utk histori OHLCV semua posisi aktif (bukan 1 query per posisi).
    #
    # `max_rows`, BUKAN `lookback_days`: yang dibutuhkan cuma nilai indikator terakhir,
    # dan tanpa batas apa pun ini menarik SELURUH riwayat tiap posisi (~1.121 baris)
    # hanya untuk membaca ujungnya — sekitar 4x lipat egress yang terbuang setiap kali
    # ada yang minta evaluasi porto. Jendela berbasis TANGGAL tidak dipakai di sini
    # karena ia diam-diam mengosongkan saham suspensi yang terakhir berdagang berbulan
    # lalu — dan di portofolio, posisi yang disuspensi justru yang paling perlu
    # terlihat. Lihat peringatan di `services/indicators.get_ohlcv_df`.
    ohlcv_by_id = get_ohlcv_df_bulk(
        db, [p["stock_id"] for p in active.values()], max_rows=INDICATOR_MAX_ROWS
    )

    prelim: List[Dict[str, Any]] = []
    invested = 0.0
    unrealized_total = 0.0
    for ticker, pos in active.items():
        df = ohlcv_by_id.get(pos["stock_id"])
        last_close = (float(df["close"].iloc[-1]) if df is not None and not df.empty else None) or pos["avg_price"]
        cost_basis = pos["shares"] * pos["avg_price"]
        unrealized = (last_close - pos["avg_price"]) * pos["shares"]
        invested += cost_basis
        unrealized_total += unrealized
        prelim.append({"ticker": ticker, "pos": pos, "df": df, "last_close": last_close,
                       "cost_basis": cost_basis, "unrealized": unrealized})

    prelim.sort(key=lambda h: h["cost_basis"], reverse=True)
    # Jumlah posisi SEBENARNYA dicatat sebelum pemotongan. Dulu `position_count`
    # dihitung setelahnya, sehingga porto 22 posisi dilaporkan "20" — sementara uang
    # dari 2 posisi sisanya tetap ikut menghitung kas & total. LLM lalu diminta menilai
    # konsentrasi dan alokasi kas atas porto yang ia kira lebih kecil dari kenyataan,
    # tanpa satu pun peringatan bahwa daftarnya dipotong.
    jumlah_posisi = len(prelim)
    prelim = prelim[: config.PORTFOLIO_MAX_POSITIONS]

    holdings: List[Dict[str, Any]] = []
    for h in prelim:
        pos, last_close, cost_basis, unrealized = h["pos"], h["last_close"], h["cost_basis"], h["unrealized"]
        inds = calculate_indicators_from_df(h["df"])
        holdings.append({
            "ticker": h["ticker"],
            # `//`, bukan `/`: lot tak pernah pecahan, dan angka ini ikut masuk ke prompt
            # yang sudah repot-repot meminta angka rapi (STYLE_RULE).
            "lots": pos["shares"] // 100,
            "shares": pos["shares"],
            "avg_price": round(pos["avg_price"], 2),
            "current_price": round(last_close, 2),
            "cost_basis": round(cost_basis, 2),
            "unrealized_pnl": round(unrealized, 2),
            "unrealized_pct": round(unrealized / cost_basis * 100, 2) if cost_basis else None,
            "rsi": inds.get("RSI_14"),
            "rsi_band": rsi_band(inds.get("RSI_14")),
            "trend": trend_of(inds, last_close),
        })

    cash = INITIAL_MODAL - invested + realized
    total_value = INITIAL_MODAL + realized + unrealized_total
    # bobot tiap posisi terhadap total nilai portofolio
    for h in holdings:
        market_val = h["current_price"] * h["shares"]
        h["weight_pct"] = round(market_val / total_value * 100, 2) if total_value else None

    hasil = {
        "cash": round(cash, 2),
        "invested": round(invested, 2),
        "unrealized": round(unrealized_total, 2),
        "realized": round(realized, 2),
        "total_value": round(total_value, 2),
        "position_count": jumlah_posisi,        # sebenarnya, sebelum pemotongan
        "positions_shown": len(holdings),       # yang benar-benar terlihat LLM
        "holdings": holdings,
    }
    if len(holdings) < jumlah_posisi:
        # Dikirim ke prompt supaya LLM tahu daftarnya tidak lengkap dan tidak menarik
        # kesimpulan konsentrasi/alokasi kas seolah-olah ia melihat seluruh porto.
        hasil["catatan_pemotongan"] = (
            f"Porto ini punya {jumlah_posisi} posisi, tapi hanya {len(holdings)} terbesar "
            f"(per nilai beli) yang dirinci di sini. Kas dan total nilai sudah "
            f"memperhitungkan SELURUH {jumlah_posisi} posisi."
        )
    return hasil
