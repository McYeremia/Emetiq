from datetime import date, timedelta
from typing import Dict, List

import pandas as pd
import ta as ta_lib
from sqlalchemy.orm import Session
import models

def get_ohlcv_df(db: Session, stock_id: int) -> pd.DataFrame:
    rows = (
        db.query(models.OHLCVDaily)
        .filter(models.OHLCVDaily.stock_id == stock_id)
        .order_by(models.OHLCVDaily.date)
        .all()
    )
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
    r["ATR_14"]      = _last(ta_lib.volatility.AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range())
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


def calculate_indicators(db: Session, stock: models.Stock) -> dict:
    return calculate_indicators_from_df(get_ohlcv_df(db, stock.id))
