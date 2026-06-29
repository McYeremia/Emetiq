import pandas as pd
import sys
import os
import ta as ta_lib
from sqlalchemy.orm import Session

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import SessionLocal
import models

import math as _math

def _f(val, default: float = 0.0) -> float:
    """Konversi ke float, ganti NaN/inf dengan default agar JSON-safe."""
    try:
        v = float(val)
        return v if _math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _compute_strength(curr, strategy_id: str) -> int:
    """
    Multi-factor signal strength 0–100 (strategy-aware, quadratic scaling).

    Setiap strategi menggunakan indikator yang relevan:
    - Oversold strategies (rsi-reversion, exhaustion-play, volatility-sniper):
      RSI depth + stochastic + BB distance below lower band
    - Momentum strategies (triple-confirmation, stoch-rsi-hybrid):
      RSI + MACD magnitude + volume surge
    - Trend strategies (trend-accelerator, pure-momentum, institutional-trend,
      defensive-bull, ma-cross):
      MACD magnitude + volume surge

    Quadratic scaling: rsi_os(30) = 1 - (rsi/30)^2
      RSI=25 → 0.31,  RSI=20 → 0.56,  RSI=15 → 0.75,  RSI=10 → 0.89
    Sehingga sinyal yang benar-benar oversold dalam dapat menembus 80%.
    """
    try:
        rsi       = _f(curr.get('rsi'),       50.0)
        macd_hist = _f(curr.get('macd_hist'),  0.0)
        stoch_k   = _f(curr.get('stoch_k'),   50.0)
        close     = _f(curr.get('close'),       1.0)
        bb_low    = _f(curr.get('bb_low'),    close)
        vol       = _f(curr.get('volume'),      0.0)
        vol_ma20  = _f(curr.get('vol_ma20'),    1.0)

        def rsi_os(lim):
            return max(0.0, 1.0 - (rsi / lim) ** 2) if rsi < lim else 0.0

        def stoch_os(lim):
            return max(0.0, 1.0 - (stoch_k / lim) ** 2) if stoch_k < lim else 0.0

        def bb_below():
            if bb_low > 0 and close < bb_low:
                return min(1.0, (bb_low - close) / bb_low / 0.04)
            return 0.0

        def vol_s():
            return min(1.0, max(0.0, (vol / vol_ma20 - 1.0) / 2.0)) if vol_ma20 > 0 else 0.0

        def macd_s():
            # Normalize MACD relative to price; 0.15% of close = full score
            return min(1.0, macd_hist / close * 667) if macd_hist > 0 and close > 0 else 0.0

        if strategy_id == "rsi-reversion":
            s = rsi_os(30) * 70 + vol_s() * 30
        elif strategy_id == "exhaustion-play":
            s = rsi_os(25) * 40 + stoch_os(15) * 35 + bb_below() * 25
        elif strategy_id == "volatility-sniper":
            s = bb_below() * 45 + stoch_os(20) * 40 + vol_s() * 15
        elif strategy_id == "triple-confirmation":
            s = rsi_os(45) * 40 + macd_s() * 40 + vol_s() * 20
        elif strategy_id == "stoch-rsi-hybrid":
            rsi_conf = min(1.0, max(0.0, (rsi - 30) / 30)) if rsi > 30 else 0.0
            s = rsi_conf * 60 + vol_s() * 40
        elif strategy_id in ("trend-accelerator", "pure-momentum"):
            s = macd_s() * 55 + vol_s() * 45
        else:  # institutional-trend, defensive-bull, ma-cross
            s = macd_s() * 60 + vol_s() * 40

        return max(0, min(100, round(s)))
    except Exception:
        return 0


def check_strategy_active(df: pd.DataFrame, strategy_id: str) -> bool:
    if df.empty or len(df) < 2: return False
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    price = curr['close']

    try:
        if strategy_id == "triple-confirmation":
            return curr['rsi'] < 45 and curr['macd_hist'] > 0 and price > curr['ma20']
        if strategy_id == "volatility-sniper":
            return price < curr['bb_low'] and curr['stoch_k'] < 20
        if strategy_id == "institutional-trend":
            return price > curr['ma200'] and curr['ema12'] > curr['ema26'] and prev['ema12'] <= prev['ema26']
        if strategy_id == "exhaustion-play":
            return curr['rsi'] < 25 and price < curr['bb_low']
        if strategy_id == "trend-accelerator":
            return curr['macd_hist'] > 0 and price > curr['ma50'] and curr['volume'] > curr.get('vol_ma20', 0)
        if strategy_id == "pure-momentum":
            return curr['ema12'] > curr['ema26'] and curr['macd_line'] > curr['macd_sig']
        if strategy_id == "defensive-bull":
            return curr['ma50'] > curr['ma200'] and curr['rsi'] > 50
        if strategy_id == "stoch-rsi-hybrid":
            return curr['stoch_k'] > 20 and prev['stoch_k'] <= 20 and curr['rsi'] > 30
        if strategy_id == "rsi-reversion":
            return curr['rsi'] < 30
        if strategy_id == "ma-cross":
            return curr['ma20'] > curr['ma50'] and prev['ma20'] <= prev['ma50']
    except:
        return False
    return False

def screen_by_strategy(db: Session, strategy_id: str):
    from datetime import date as _date, timedelta
    from collections import defaultdict

    # Lookback kalender (hari) dan min rows per strategi
    # Strategi yang pakai MA200 butuh ~700 hari kalender; lainnya cukup 200
    CALENDAR_LOOKBACK = {
        "defensive-bull": 700, "institutional-trend": 700,
        "triple-confirmation": 200, "ma-cross": 200,
        "trend-accelerator": 200, "pure-momentum": 200,
        "volatility-sniper": 150, "exhaustion-play": 150,
        "stoch-rsi-hybrid": 150, "rsi-reversion": 150,
    }
    MIN_ROWS = {
        "defensive-bull": 210, "institutional-trend": 210,
        "triple-confirmation": 55, "ma-cross": 55,
        "trend-accelerator": 55, "pure-momentum": 55,
        "volatility-sniper": 30, "exhaustion-play": 30,
        "stoch-rsi-hybrid": 30, "rsi-reversion": 20,
    }

    calendar_days = CALENDAR_LOOKBACK.get(strategy_id, 200)
    min_rows = MIN_ROWS.get(strategy_id, 55)
    cutoff_date = _date.today() - timedelta(days=calendar_days)

    # SATU bulk query — jauh lebih cepat dari N query per saham
    all_rows = (
        db.query(models.OHLCVDaily, models.Stock)
        .join(models.Stock, models.OHLCVDaily.stock_id == models.Stock.id)
        .filter(
            models.OHLCVDaily.date >= cutoff_date,
            models.Stock.ticker != "^JKSE",
        )
        .order_by(models.OHLCVDaily.stock_id, models.OHLCVDaily.date)
        .all()
    )

    # Kelompokkan per saham di memory
    stock_ohlcv: dict = defaultdict(list)
    stock_meta: dict = {}
    for ohlcv, stock in all_rows:
        stock_ohlcv[stock.id].append({
            "close": ohlcv.close, "high": ohlcv.high,
            "low": ohlcv.low, "volume": ohlcv.volume,
        })
        if stock.id not in stock_meta:
            stock_meta[stock.id] = stock

    matches = []
    for stock_id, data in stock_ohlcv.items():
        if len(data) < min_rows:
            continue
        stock = stock_meta[stock_id]
        df = pd.DataFrame(data)
        close = df["close"]

        df["rsi"]      = ta_lib.momentum.RSIIndicator(close).rsi()
        df["ma20"]     = ta_lib.trend.SMAIndicator(close, window=20).sma_indicator()
        df["ma50"]     = ta_lib.trend.SMAIndicator(close, window=50).sma_indicator()
        df["ma200"]    = ta_lib.trend.SMAIndicator(close, window=200).sma_indicator()
        df["ema12"]    = ta_lib.trend.EMAIndicator(close, window=12).ema_indicator()
        df["ema26"]    = ta_lib.trend.EMAIndicator(close, window=26).ema_indicator()
        _macd          = ta_lib.trend.MACD(close)
        df["macd_line"] = _macd.macd()
        df["macd_sig"]  = _macd.macd_signal()
        df["macd_hist"] = _macd.macd_diff()
        _bb            = ta_lib.volatility.BollingerBands(close)
        df["bb_low"]   = _bb.bollinger_lband()
        df["bb_high"]  = _bb.bollinger_hband()
        _stoch         = ta_lib.momentum.StochasticOscillator(df["high"], df["low"], close)
        df["stoch_k"]  = _stoch.stoch()
        df["vol_ma20"] = ta_lib.trend.SMAIndicator(df["volume"], window=20).sma_indicator()

        if not check_strategy_active(df, strategy_id):
            continue

        curr = df.iloc[-1]
        try:
            atr = float(
                ta_lib.volatility.AverageTrueRange(df["high"], df["low"], close)
                .average_true_range().iloc[-1]
            )
        except Exception:
            atr = 0.0

        ma20  = _f(curr["ma20"],  1)
        ma50  = _f(curr["ma50"],  1)
        ma200 = _f(curr["ma200"], 1)
        bb_low = _f(curr["bb_low"], 1)
        vol_ma20 = _f(curr["vol_ma20"], 1)
        price = _f(curr["close"])

        matches.append({
            "ticker":    stock.ticker,
            "name":      stock.name,
            "Price":     price,
            "PBV":       _f(stock.pbv_ratio),
            "PE":        _f(stock.pe_ratio),
            "RSI":       _f(curr["rsi"]),
            "MACD_Hist": _f(curr["macd_hist"]),
            "MACD_Line": _f(curr["macd_line"]),
            "MA20_Dist": _f((price - ma20)  / ma20  * 100),
            "MA50_Dist": _f((price - ma50)  / ma50  * 100),
            "MA200_Dist": _f((price - ma200) / ma200 * 100),
            "BB_Dist":   _f((price - bb_low) / bb_low * 100),
            "Stoch_K":   _f(curr["stoch_k"]),
            "ATR":       atr,
            "Div_Yield": _f(stock.dividend_yield),
            "Vol_Surge": _f(curr["volume"] / vol_ma20) if vol_ma20 > 0 else 1.0,
        })

    return matches

def check_strategy_exit(df: pd.DataFrame, strategy_id: str) -> bool:
    """Returns True if the exit condition for the given strategy is met."""
    if df.empty or len(df) < 2: return False
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    price = curr['close']

    try:
        if strategy_id == "triple-confirmation":
            return curr['rsi'] > 70 or price < curr['ma20']
        if strategy_id == "volatility-sniper":
            return price > curr['bb_high']
        if strategy_id == "institutional-trend":
            return curr['ema12'] < curr['ema26']
        if strategy_id == "exhaustion-play":
            return curr['rsi'] > 60
        if strategy_id == "trend-accelerator":
            return curr['macd_hist'] < 0
        if strategy_id == "pure-momentum":
            return curr['macd_line'] < curr['macd_sig']
        if strategy_id == "defensive-bull":
            return curr['ma50'] < curr['ma200']
        if strategy_id == "stoch-rsi-hybrid":
            return curr['stoch_k'] > 80 or curr['rsi'] > 70
        if strategy_id == "rsi-reversion":
            return curr['rsi'] > 70
        if strategy_id == "ma-cross":
            return curr['ma20'] < curr['ma50']
    except:
        return False
    return False


def scan_market_signals():
    """Scan all stocks for active buy signals and save to Signal table."""
    from database import SessionLocal
    from sqlalchemy import func
    import models as mdl
    from datetime import datetime

    db = SessionLocal()
    count = 0
    try:
        # Hapus semua signal lama agar tidak menumpuk
        db.query(mdl.Signal).delete()
        db.commit()

        stocks = db.query(mdl.Stock).filter(mdl.Stock.ticker != "^JKSE").all()
        for stock in stocks:
            rows = db.query(mdl.OHLCVDaily).filter(
                mdl.OHLCVDaily.stock_id == stock.id
            ).order_by(mdl.OHLCVDaily.date).all()

            if not rows or len(rows) < 50:
                continue

            df = pd.DataFrame([{
                "close": r.close, "high": r.high, "low": r.low, "volume": r.volume
            } for r in rows])

            close = df['close']
            df['rsi'] = ta_lib.momentum.RSIIndicator(close).rsi()
            df['ma20'] = ta_lib.trend.SMAIndicator(close, window=20).sma_indicator()
            df['ma50'] = ta_lib.trend.SMAIndicator(close, window=50).sma_indicator()
            df['ma200'] = ta_lib.trend.SMAIndicator(close, window=200).sma_indicator()
            df['ema12'] = ta_lib.trend.EMAIndicator(close, window=12).ema_indicator()
            df['ema26'] = ta_lib.trend.EMAIndicator(close, window=26).ema_indicator()
            macd = ta_lib.trend.MACD(close)
            df['macd_line'] = macd.macd()
            df['macd_sig'] = macd.macd_signal()
            df['macd_hist'] = macd.macd_diff()
            bb = ta_lib.volatility.BollingerBands(close)
            df['bb_low'] = bb.bollinger_lband()
            df['bb_high'] = bb.bollinger_hband()
            stoch = ta_lib.momentum.StochasticOscillator(df['high'], df['low'], close)
            df['stoch_k'] = stoch.stoch()
            df['vol_ma20'] = ta_lib.trend.SMAIndicator(df['volume'], window=20).sma_indicator()

            curr = df.iloc[-1]
            active = [s for s in [
                "triple-confirmation", "volatility-sniper", "institutional-trend",
                "exhaustion-play", "trend-accelerator", "pure-momentum",
                "defensive-bull", "stoch-rsi-hybrid", "rsi-reversion", "ma-cross"
            ] if check_strategy_active(df, s)]

            for strategy_id in active:
                rsi_val  = _f(curr.get('rsi'), 0.0)
                strength = _compute_strength(curr, strategy_id)

                sig = mdl.Signal(
                    stock_id=stock.id,
                    strategy_id=strategy_id,
                    type="BUY",
                    price=float(curr['close']),
                    strength=strength,
                    description=f"{strategy_id} | RSI:{rsi_val:.1f} | MACD:{_f(curr.get('macd_hist'), 0):.4f}",
                    created_at=datetime.now(),
                )
                db.add(sig)
                count += 1

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Scan error: {e}")
    finally:
        db.close()

    return count
