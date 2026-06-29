import pandas as pd
import numpy as np
import ta as ta_lib
from typing import List, Dict, Any
from sqlalchemy.orm import Session
import models
import services.indicators as ind_svc

def run_backtest(db: Session, stock_ticker: str, strategy_id: str, initial_capital: float = 10_000_000):
    stock = db.query(models.Stock).filter(models.Stock.ticker == stock_ticker).first()
    if not stock: return {"error": "Stock not found"}

    # Minimum data per strategi (beberapa tidak butuh MA200)
    MIN_DATA = {
        "defensive-bull": 200, "institutional-trend": 200,
        "triple-confirmation": 60, "ma-cross": 60,
        "trend-accelerator": 60, "pure-momentum": 60,
        "volatility-sniper": 40, "exhaustion-play": 40,
        "stoch-rsi-hybrid": 40, "rsi-reversion": 40,
    }
    min_required = MIN_DATA.get(strategy_id, 60)

    df = ind_svc.get_ohlcv_df(db, stock.id)
    if df.empty or len(df) < min_required:
        return {"error": f"Insufficient data: {len(df) if not df.empty else 0} hari tersedia, butuh minimal {min_required} hari untuk strategi {strategy_id}"}

    close = df['close']
    high = df['high']
    low = df['low']
    vol = df['volume']
    
    # CALCULATE ALL 15 INDICATORS
    # Trend
    df['ma20'] = ta_lib.trend.SMAIndicator(close, window=20).sma_indicator()
    df['ma50'] = ta_lib.trend.SMAIndicator(close, window=50).sma_indicator()
    df['ma200'] = ta_lib.trend.SMAIndicator(close, window=200).sma_indicator()
    df['ema12'] = ta_lib.trend.EMAIndicator(close, window=12).ema_indicator()
    df['ema26'] = ta_lib.trend.EMAIndicator(close, window=26).ema_indicator()
    
    # Momentum
    df['rsi'] = ta_lib.momentum.RSIIndicator(close).rsi()
    stoch = ta_lib.momentum.StochasticOscillator(high, low, close)
    df['stoch_k'] = stoch.stoch()
    df['stoch_d'] = stoch.stoch_signal()
    
    macd = ta_lib.trend.MACD(close)
    df['macd_line'] = macd.macd()
    df['macd_sig'] = macd.macd_signal()
    df['macd_hist'] = macd.macd_diff()
    
    # Volatility
    bb = ta_lib.volatility.BollingerBands(close)
    df['bb_low'] = bb.bollinger_lband()
    df['bb_high'] = bb.bollinger_hband()
    df['atr'] = ta_lib.volatility.AverageTrueRange(high, low, close).average_true_range()
    
    # Volume
    df['vol_ma20'] = ta_lib.trend.SMAIndicator(vol, window=20).sma_indicator()
    
    cash = initial_capital
    position = 0
    entry_price = 0
    entry_date = None
    trades = []
    equity_curve = []

    for i in range(50, len(df)):
        date = df.index[i]
        curr = df.iloc[i]
        prev = df.iloc[i-1]
        price = curr['close']
        
        buy_signal = False
        sell_signal = False

        # --- ADVANCED STRATEGY LOGIC ---
        
        if strategy_id == "triple-confirmation":
            buy_signal = curr['rsi'] < 45 and curr['macd_hist'] > 0 and price > curr['ma20']
            sell_signal = curr['rsi'] > 70 or price < curr['ma20']

        elif strategy_id == "volatility-sniper":
            buy_signal = price < curr['bb_low'] and curr['stoch_k'] < 20
            sell_signal = price > curr['bb_high']

        elif strategy_id == "institutional-trend":
            buy_signal = price > curr['ma200'] and curr['ema12'] > curr['ema26'] and prev['ema12'] <= prev['ema26']
            sell_signal = curr['ema12'] < curr['ema26']

        elif strategy_id == "exhaustion-play":
            buy_signal = curr['rsi'] < 25 and price < curr['bb_low'] and curr['stoch_k'] < 15
            sell_signal = curr['rsi'] > 60

        elif strategy_id == "trend-accelerator":
            buy_signal = curr['macd_hist'] > 0 and price > curr['ma50'] and curr['volume'] > curr['vol_ma20']
            sell_signal = curr['macd_hist'] < 0

        elif strategy_id == "pure-momentum":
            buy_signal = curr['ema12'] > curr['ema26'] and curr['macd_line'] > curr['macd_sig']
            sell_signal = curr['macd_line'] < curr['macd_sig']

        elif strategy_id == "defensive-bull":
            buy_signal = curr['ma50'] > curr['ma200'] and curr['rsi'] > 50
            sell_signal = curr['ma50'] < curr['ma200']

        elif strategy_id == "stoch-rsi-hybrid":
            buy_signal = curr['stoch_k'] > 20 and prev['stoch_k'] <= 20 and curr['rsi'] > 30
            sell_signal = curr['stoch_k'] > 80 or curr['rsi'] > 70
            
        # Default simple fallbacks for old IDs
        elif strategy_id == "rsi-reversion":
            buy_signal = curr['rsi'] < 30
            sell_signal = curr['rsi'] > 70
        elif strategy_id == "ma-cross":
            buy_signal = curr['ma20'] > curr['ma50'] and prev['ma20'] <= prev['ma50']
            sell_signal = curr['ma20'] < curr['ma50']

        # EXECUTION ENGINE
        if position == 0 and buy_signal:
            shares = (cash // (price * 100)) * 100
            if shares > 0:
                entry_price = price
                entry_date = date
                position = shares
                cash -= (position * entry_price)
                trades.append({
                    "date": str(date),
                    "type": "BUY",
                    "price": float(entry_price),
                    "lots": int(position // 100),
                    "shares": int(position),
                    "total_value": float(position * entry_price),
                    "capital_after": float(cash),
                })

        elif position > 0 and (sell_signal or (price - entry_price) / entry_price < -0.07):
            pnl = (price - entry_price) * position
            cash += position * price
            hold_days = (date - entry_date).days if entry_date is not None else 0
            reason = "stop-loss" if (price - entry_price) / entry_price < -0.07 else "signal"
            trades.append({
                "date": str(date),
                "type": "SELL",
                "price": float(price),
                "lots": int(position // 100),
                "shares": int(position),
                "total_value": float(position * price),
                "capital_after": float(cash),
                "hold_days": hold_days,
                "exit_reason": reason,
                "pnl": float(pnl),
                "pnl_pct": float((price - entry_price) / entry_price * 100),
            })
            position = 0
            entry_date = None

        equity_curve.append({"date": str(date), "value": float(cash + (position * price))})

    closed_trades = [t for t in trades if "pnl" in t]
    if not closed_trades: return {"error": "No trades executed for this strategy"}

    wins = [t for t in closed_trades if t['pnl'] > 0]
    win_rate = (len(wins) / len(closed_trades)) * 100
    total_return = ((equity_curve[-1]['value'] - initial_capital) / initial_capital) * 100
    max_dd = 0.0
    peak = initial_capital
    for pt in equity_curve:
        if pt['value'] > peak:
            peak = pt['value']
        dd = (peak - pt['value']) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # Downsample equity_curve to max 500 points for performance
    step = max(1, len(equity_curve) // 500)
    sampled_curve = equity_curve[::step]
    if equity_curve[-1] != sampled_curve[-1]:
        sampled_curve.append(equity_curve[-1])

    return {
        "strategy_id": strategy_id,
        "ticker": stock_ticker,
        "metrics": {
            "win_rate": round(win_rate, 2),
            "total_return_pct": round(total_return, 2),
            "total_trades": len(closed_trades),
            "wins": len(wins),
            "losses": len(closed_trades) - len(wins),
            "max_drawdown_pct": round(max_dd, 2),
            "initial_capital": initial_capital,
            "final_value": round(equity_curve[-1]['value'], 2),
        },
        "equity_curve": sampled_curve,
        "trades": trades,  # semua trade: BUY + SELL
    }
