from datetime import date, timedelta
from typing import Dict, List

import pandas as pd
import ta as ta_lib
from sqlalchemy.orm import Session
import models

def get_ohlcv_df(db: Session, stock_id: int, max_rows: int = None) -> pd.DataFrame:
    """OHLCV satu saham sebagai DataFrame, urut menaik.

    `max_rows=None` (bawaan) mengambil SELURUH riwayat — backtester bergantung
    pada itu, jadi jangan diberi batas.

    Isi `max_rows` bila yang dibutuhkan cuma nilai indikator TERAKHIR. Rata-rata
    satu saham punya ~1.121 baris, dan menariknya utuh dari Postgres remote hanya
    untuk membaca satu baris terakhir adalah egress yang terbuang.

    Batasnya JUMLAH BARIS, bukan rentang tanggal. Jendela berbasis tanggal
    (mis. "700 hari terakhir") tampak setara, tapi menghapus data ~131 saham
    suspensi yang terakhir berdagang berbulan lalu: jendelanya kosong, indikatornya
    hilang, dan tak ada galat yang muncul. `routers/stocks.py:list_stocks` sudah
    menolak batas tanggal untuk alasan yang persis sama.
    """
    q = db.query(models.OHLCVDaily).filter(models.OHLCVDaily.stock_id == stock_id)
    if max_rows is not None:
        # ambil N terbaru lalu balik urutannya — indikator butuh urutan menaik
        rows = q.order_by(models.OHLCVDaily.date.desc()).limit(max_rows).all()
        rows.reverse()
    else:
        rows = q.order_by(models.OHLCVDaily.date).all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([{
        "date": r.date, "open": r.open, "high": r.high,
        "low": r.low, "close": r.close, "volume": float(r.volume or 0)
    } for r in rows]).set_index("date")
    return df


def get_ohlcv_df_bulk(db: Session, stock_ids: List[int], lookback_days: int = None) -> Dict[int, pd.DataFrame]:
    """Ambil OHLCV banyak saham sekaligus (1 query, bukan N query) — hindari N+1.

    `lookback_days=None` ambil semua histori; kalau diisi, hanya baris >= (hari ini -
    lookback_days). Untuk indikator (MA/RSI/MACD dst) nilai TERAKHIR praktis sama
    dengan histori penuh selama window cukup panjang (>200 hari bursa), jadi aman
    dipakai saat memproses banyak saham (screening/kandidat) demi kecepatan.
    """
    if not stock_ids:
        return {}
    q = db.query(models.OHLCVDaily).filter(models.OHLCVDaily.stock_id.in_(stock_ids))
    if lookback_days is not None:
        q = q.filter(models.OHLCVDaily.date >= date.today() - timedelta(days=lookback_days))
    rows = q.order_by(models.OHLCVDaily.stock_id, models.OHLCVDaily.date).all()

    grouped: Dict[int, list] = {}
    for r in rows:
        grouped.setdefault(r.stock_id, []).append(r)

    out: Dict[int, pd.DataFrame] = {}
    for sid, rs in grouped.items():
        out[sid] = pd.DataFrame([{
            "date": r.date, "open": r.open, "high": r.high,
            "low": r.low, "close": r.close, "volume": float(r.volume or 0)
        } for r in rs]).set_index("date")
    return out


def _last(series):
    if series is None:
        return None
    s = series.dropna()
    return round(float(s.iloc[-1]), 4) if not s.empty else None


def _atr_terakhir(high, low, close, window: int = 14):
    """ATR terakhir, atau None bila deretnya lebih pendek dari jendelanya.

    `ta` 0.11.0 tidak seragam di titik ini. Semua indikator lain di bawah
    memulangkan NaN untuk deret pendek — dan `_last()` mengubah NaN jadi None —
    tapi `AverageTrueRange` menulis ke `atr[window - 1]` tanpa memeriksa panjang
    deret, jadi ia melempar `IndexError`.

    Efeknya di endpoint ganjil: 0 baris AMAN (dijaga `df.empty` di awal
    `calculate_indicators_from_df`), sedangkan 1-13 baris membuat
    `GET /stocks/{ticker}/indicators` membalas 500 — saham yang baru melantai
    persis berada di rentang itu. Jalur AI Advisor
    (`services/advisor/data_provider.py`) memanggil fungsi indikator ini di dalam
    perulangan tanpa penangkap galat, jadi satu saham tipis di hasil screener
    cukup untuk menjatuhkan seluruh balasan.

    Penjaganya `tests/test_indicators_deret_pendek.py`.
    """
    if len(close) < window:
        return None
    atr = ta_lib.volatility.AverageTrueRange(high=high, low=low, close=close, window=window)
    return _last(atr.average_true_range())


def calculate_indicators_from_df(df: pd.DataFrame) -> dict:
    """Hitung indikator dari df OHLCV yang sudah di-fetch (dipakai jalur batch)."""
    if df is None or df.empty:
        return {}

    close, high, low, volume = df["close"], df["high"], df["low"], df["volume"]
    r: dict = {}

    r["MA_20"]       = _last(ta_lib.trend.SMAIndicator(close=close, window=20).sma_indicator())
    r["MA_50"]       = _last(ta_lib.trend.SMAIndicator(close=close, window=50).sma_indicator())
    r["MA_200"]      = _last(ta_lib.trend.SMAIndicator(close=close, window=200).sma_indicator())
    r["EMA_12"]      = _last(ta_lib.trend.EMAIndicator(close=close, window=12).ema_indicator())
    r["EMA_26"]      = _last(ta_lib.trend.EMAIndicator(close=close, window=26).ema_indicator())
    r["RSI_14"]      = _last(ta_lib.momentum.RSIIndicator(close=close, window=14).rsi())
    r["ATR_14"]      = _atr_terakhir(high, low, close, window=14)
    r["VOLUME_MA_20"] = _last(ta_lib.trend.SMAIndicator(close=volume, window=20).sma_indicator())

    macd = ta_lib.trend.MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    r["MACD_LINE"]   = _last(macd.macd())
    r["MACD_SIGNAL"] = _last(macd.macd_signal())
    r["MACD_HIST"]   = _last(macd.macd_diff())

    bb = ta_lib.volatility.BollingerBands(close=close, window=20, window_dev=2)
    r["BB_UPPER"]  = _last(bb.bollinger_hband())
    r["BB_MIDDLE"] = _last(bb.bollinger_mavg())
    r["BB_LOWER"]  = _last(bb.bollinger_lband())

    stoch = ta_lib.momentum.StochasticOscillator(high=high, low=low, close=close, window=14, smooth_window=3)
    r["STOCH_K"] = _last(stoch.stoch())
    r["STOCH_D"] = _last(stoch.stoch_signal())

    return r


# Berapa baris terakhir yang cukup untuk menghitung SEMUA indikator di sini.
#
# 200 adalah syarat keras MA_200, window terpanjang yang dihitung. 300 memberi
# 100 baris tambahan supaya EMA (yang rekursif sejak batang pertama) sudah jauh
# konvergen: pada EMA_26, pengaruh batang pertama setelah 300 langkah tinggal
# sekitar 1e-10 — tak pernah sampai ke desimal yang ditampilkan.
#
# Diverifikasi 3 Sep 2026 pada 10 saham besar: hasil dengan 300 baris identik
# dengan riwayat penuh, termasuk MA_200 sampai 4 desimal.
INDICATOR_MAX_ROWS = 300


def calculate_indicators(db: Session, stock: models.Stock,
                         max_rows: int = INDICATOR_MAX_ROWS) -> dict:
    """Indikator terakhir satu saham. Lihat catatan di `get_ohlcv_df`."""
    return calculate_indicators_from_df(get_ohlcv_df(db, stock.id, max_rows))
