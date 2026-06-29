import os
import json
from datetime import date, datetime
from typing import Dict

from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session
from sqlalchemy import desc
import pandas as pd
import ta as ta_lib

import models
from database import SessionLocal, engine
import services.backtester as bt_svc
from services.watcher import check_strategy_active

# Pastikan semua tabel (termasuk agent_position_targets) sudah ada di DB
models.Base.metadata.create_all(bind=engine)

mcp = FastMCP("IDXAnalyst")

ALL_STRATEGIES = [
    "triple-confirmation", "volatility-sniper", "institutional-trend",
    "exhaustion-play", "trend-accelerator", "pure-momentum",
    "defensive-bull", "stoch-rsi-hybrid", "rsi-reversion", "ma-cross"
]


def _build_indicator_df(db: Session, stock_id: int) -> pd.DataFrame:
    rows = db.query(models.OHLCVDaily).filter(
        models.OHLCVDaily.stock_id == stock_id
    ).order_by(models.OHLCVDaily.date).all()

    if not rows or len(rows) < 50:
        return pd.DataFrame()

    df = pd.DataFrame([{
        "close": r.close, "high": r.high, "low": r.low, "volume": r.volume
    } for r in rows])

    close = df["close"]
    df["rsi"] = ta_lib.momentum.RSIIndicator(close).rsi()
    df["ma20"] = ta_lib.trend.SMAIndicator(close, window=20).sma_indicator()
    df["ma50"] = ta_lib.trend.SMAIndicator(close, window=50).sma_indicator()
    df["ma200"] = ta_lib.trend.SMAIndicator(close, window=200).sma_indicator()
    df["ema12"] = ta_lib.trend.EMAIndicator(close, window=12).ema_indicator()
    df["ema26"] = ta_lib.trend.EMAIndicator(close, window=26).ema_indicator()
    macd = ta_lib.trend.MACD(close)
    df["macd_line"] = macd.macd()
    df["macd_sig"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()
    bb = ta_lib.volatility.BollingerBands(close)
    df["bb_low"] = bb.bollinger_lband()
    df["bb_high"] = bb.bollinger_hband()
    stoch = ta_lib.momentum.StochasticOscillator(df["high"], df["low"], close)
    df["stoch_k"] = stoch.stoch()
    df["vol_ma20"] = ta_lib.trend.SMAIndicator(df["volume"], window=20).sma_indicator()

    return df


def _get_agent_holdings(db: Session, agent_name: str) -> Dict[str, dict]:
    """Rekonstruksi posisi aktif agent dari TradeLog. Return {ticker: {shares, avg_price, realized}}."""
    all_trades = db.query(models.TradeLog).order_by(models.TradeLog.date).all()
    holdings: Dict[str, dict] = {}
    for t in all_trades:
        raw_type = t.trade_type.upper()
        if agent_name == "CLAUDE" and "CLAUDE" not in raw_type:
            continue
        if agent_name == "GEMINI" and "GEMINI" not in raw_type:
            continue
        if agent_name == "USER" and ("CLAUDE" in raw_type or "GEMINI" in raw_type):
            continue
        ticker = t.stock.ticker
        if ticker not in holdings:
            holdings[ticker] = {"shares": 0, "avg_price": 0.0, "realized": 0.0}
        data = holdings[ticker]
        qty = t.quantity * 100
        if t.action == "BUY":
            total_cost = data["shares"] * data["avg_price"] + qty * t.price
            data["shares"] += qty
            data["avg_price"] = total_cost / data["shares"] if data["shares"] > 0 else 0.0
        else:
            data["realized"] += (t.price - data["avg_price"]) * qty
            data["shares"] -= qty
    return holdings


@mcp.tool()
def list_available_stocks() -> str:
    """List all stocks in the database with basic fundamentals."""
    db = SessionLocal()
    try:
        stocks = db.query(models.Stock).filter(models.Stock.ticker != "^JKSE").all()
        result = [
            {
                "ticker": s.ticker,
                "name": s.name,
                "sector": s.sector,
                "pe_ratio": s.pe_ratio,
                "pbv_ratio": s.pbv_ratio,
                "dividend_yield": s.dividend_yield,
            }
            for s in stocks
        ]
        return json.dumps(result)
    finally:
        db.close()


@mcp.tool()
def analyze_stock(ticker: str) -> str:
    """
    Analyze a single stock: current price, all technical indicators, and active strategy signals.
    Use this BEFORE executing a trade to understand the current market condition.
    """
    db = SessionLocal()
    ticker = ticker.upper()
    try:
        stock = db.query(models.Stock).filter(models.Stock.ticker == ticker).first()
        if not stock:
            return f"Stock {ticker} not found."

        df = _build_indicator_df(db, stock.id)
        if df.empty:
            return f"Insufficient data for {ticker} (need at least 50 candles)."

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        active_signals = [s for s in ALL_STRATEGIES if check_strategy_active(df, s)]

        result = {
            "ticker": ticker,
            "name": stock.name,
            "sector": stock.sector,
            "fundamentals": {
                "pe_ratio": stock.pe_ratio,
                "pbv_ratio": stock.pbv_ratio,
                "dividend_yield": stock.dividend_yield,
            },
            "price": {
                "current": float(curr["close"]),
                "change_pct": round(float((curr["close"] - prev["close"]) / prev["close"] * 100), 2),
            },
            "indicators": {
                "rsi": round(float(curr["rsi"]), 2),
                "macd_hist": round(float(curr["macd_hist"]), 4),
                "macd_line": round(float(curr["macd_line"]), 4),
                "ma20": round(float(curr["ma20"]), 2),
                "ma50": round(float(curr["ma50"]), 2),
                "ma200": round(float(curr["ma200"]), 2),
                "bb_low": round(float(curr["bb_low"]), 2),
                "bb_high": round(float(curr["bb_high"]), 2),
                "stoch_k": round(float(curr["stoch_k"]), 2),
                "vol_surge": round(float(curr["volume"] / curr["vol_ma20"]) if curr["vol_ma20"] > 0 else 1.0, 2),
            },
            "active_signals": active_signals,
            "signal_count": len(active_signals),
        }
        return json.dumps(result, indent=2)
    finally:
        db.close()


@mcp.tool()
def execute_ai_trade(ticker: str, action: str, quantity_lots: int, agent_name: str, notes: str = "") -> str:
    """
    Execute a trade as an AI Agent.
    - ticker: stock ticker (e.g. BBRI, TLKM)
    - action: BUY or SELL
    - quantity_lots: number of lots (1 lot = 100 shares)
    - agent_name: CLAUDE or GEMINI
    - notes: reasoning or strategy used
    Trade will appear in the agent's portfolio on the frontend.
    After a full SELL, position target is automatically deactivated.
    """
    db = SessionLocal()
    ticker = ticker.upper()
    agent_name = agent_name.upper()

    VALID_AGENTS = {"CLAUDE", "GEMINI", "USER"}
    if agent_name not in VALID_AGENTS:
        db.close()
        return f"ERROR: Invalid agent_name '{agent_name}'. Must be one of: CLAUDE, GEMINI, USER."

    stock = db.query(models.Stock).filter(models.Stock.ticker == ticker).first()
    if not stock:
        db.close()
        return f"ERROR: Stock {ticker} not found in database."

    latest = (
        db.query(models.OHLCVDaily)
        .filter(models.OHLCVDaily.stock_id == stock.id)
        .order_by(desc(models.OHLCVDaily.date))
        .first()
    )
    if not latest:
        db.close()
        return f"ERROR: No market price data available for {ticker}."

    price = latest.close

    if action.upper() == "SELL":
        holdings = _get_agent_holdings(db, agent_name)
        held_shares = holdings.get(ticker, {}).get("shares", 0)
        needed = quantity_lots * 100
        if held_shares < needed:
            db.close()
            return f"ERROR: {agent_name} only holds {held_shares // 100} lots of {ticker} (requested {quantity_lots} lots SELL)."

    if action.upper() == "BUY":
        holdings = _get_agent_holdings(db, agent_name)
        invested = sum(
            pos["shares"] * pos["avg_price"]
            for pos in holdings.values()
            if pos["shares"] > 0
        )
        realized = sum(pos["realized"] for pos in holdings.values())
        INITIAL_MODAL = 15_000_000
        available_cash = INITIAL_MODAL - invested + realized
        trade_cost = price * quantity_lots * 100
        if trade_cost > available_cash:
            db.close()
            return (
                f"ERROR: Insufficient funds. Trade cost Rp {trade_cost:,.0f} "
                f"but {agent_name} only has Rp {available_cash:,.0f} available."
            )
        # 25% max position rule
        if trade_cost > INITIAL_MODAL * 0.25:
            db.close()
            return (
                f"ERROR: Position too large. Rp {trade_cost:,.0f} exceeds 25% limit "
                f"(max Rp {INITIAL_MODAL * 0.25:,.0f})."
            )

    new_trade = models.TradeLog(
        stock_id=stock.id,
        action=action.upper(),
        date=date.today(),
        price=price,
        quantity=quantity_lots,
        trade_type=f"AUTO_{agent_name}",
        notes=f"[{agent_name} AI] {notes}",
    )

    try:
        db.add(new_trade)
        db.commit()
        total_value = price * quantity_lots * 100

        # Jika SELL, cek apakah posisi sudah habis — jika ya, nonaktifkan target
        if action.upper() == "SELL":
            holdings = _get_agent_holdings(db, agent_name)
            remaining_shares = holdings.get(ticker, {}).get("shares", 0)
            if remaining_shares <= 0:
                target = db.query(models.AgentPositionTarget).filter(
                    models.AgentPositionTarget.agent_name == agent_name,
                    models.AgentPositionTarget.ticker == ticker,
                    models.AgentPositionTarget.is_active == 1,
                ).first()
                if target:
                    target.is_active = 0
                    target.updated_at = datetime.utcnow()
                    db.commit()

        return (
            f"SUCCESS: {agent_name} executed {action} {quantity_lots} lots of {ticker} "
            f"@ Rp {price:,.0f} — Total Rp {total_value:,.0f}"
        )
    except Exception as e:
        db.rollback()
        return f"ERROR: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def ai_smart_trade_scan_and_execute(agent_name: str, max_trades: int = 3) -> str:
    """
    Scan the entire market and auto-execute trades for the specified agent.
    For each stock, finds the best-performing strategy via backtest and executes
    if that strategy's signal is active today.
    Checks available cash before buying. Also sells positions where exit signal triggers.
    - agent_name: CLAUDE or GEMINI
    - max_trades: cap on executions per run (default 3)
    """
    db = SessionLocal()
    agent_name = agent_name.upper()
    INITIAL_MODAL = 15_000_000
    MAX_POSITION_PCT = 0.25  # max 25% of modal per position

    stocks = db.query(models.Stock).filter(models.Stock.ticker != "^JKSE").all()
    executed = []
    sold = []

    # --- Build current holdings for this agent ---
    all_trades = db.query(models.TradeLog).order_by(models.TradeLog.date).all()
    holdings: Dict[str, dict] = {}
    for t in all_trades:
        raw_type = t.trade_type.upper()
        if agent_name == "CLAUDE" and "CLAUDE" not in raw_type: continue
        if agent_name == "GEMINI" and "GEMINI" not in raw_type: continue
        if agent_name == "USER": continue

        ticker = t.stock.ticker
        if ticker not in holdings:
            holdings[ticker] = {"shares": 0, "avg_price": 0.0, "realized": 0.0}
        data = holdings[ticker]
        qty = t.quantity * 100
        if t.action == "BUY":
            total_cost = data["shares"] * data["avg_price"] + qty * t.price
            data["shares"] += qty
            data["avg_price"] = total_cost / data["shares"] if data["shares"] > 0 else 0.0
        else:
            data["realized"] += (t.price - data["avg_price"]) * qty
            data["shares"] -= qty

    total_invested = sum(d["avg_price"] * d["shares"] for d in holdings.values() if d["shares"] > 0)
    total_realized = sum(d["realized"] for d in holdings.values())
    liquid_cash = INITIAL_MODAL - total_invested + total_realized

    # --- SELL PHASE: check exit signals for existing positions ---
    for ticker, data in holdings.items():
        if data["shares"] <= 0:
            continue
        stock = db.query(models.Stock).filter(models.Stock.ticker == ticker).first()
        if not stock:
            continue
        df = _build_indicator_df(db, stock.id)
        if df.empty:
            continue

        # Find the strategy that was used for this holding (approximate: best strategy now)
        best_strat = None
        best_wr = 0.0
        for strat_id in ALL_STRATEGIES:
            res = bt_svc.run_backtest(db, stock.ticker, strat_id)
            wr = res.get("metrics", {}).get("win_rate", 0.0)
            if wr > best_wr:
                best_wr = wr
                best_strat = strat_id

        if best_strat:
            from services.watcher import check_strategy_exit
            curr = df.iloc[-1]
            curr_price = float(curr["close"])
            stop_loss_pct = -0.07  # 7% stop loss
            unrealized_pct = (curr_price - data["avg_price"]) / data["avg_price"]

            should_sell = check_strategy_exit(df, best_strat) or unrealized_pct <= stop_loss_pct
            if should_sell:
                lots = data["shares"] // 100
                reason = "Stop loss triggered" if unrealized_pct <= stop_loss_pct else f"Exit signal: {best_strat}"
                pnl = (curr_price - data["avg_price"]) * data["shares"]
                execute_ai_trade(ticker, "SELL", lots, agent_name, reason)
                liquid_cash += curr_price * data["shares"]
                sold.append(f"SELL {ticker} {lots} lot @ Rp {curr_price:,.0f} | P&L: Rp {pnl:,.0f} | {reason}")

    # --- BUY PHASE: scan for entry signals ---
    for stock in stocks:
        if len(executed) >= max_trades:
            break
        if liquid_cash < 500_000:  # minimum kas
            break
        if holdings.get(stock.ticker, {}).get("shares", 0) > 0:
            continue  # already holding, skip

        best_win_rate = 0.0
        best_strat_id = None
        for strat_id in ALL_STRATEGIES:
            res = bt_svc.run_backtest(db, stock.ticker, strat_id)
            wr = res.get("metrics", {}).get("win_rate", 0.0)
            if wr > best_win_rate:
                best_win_rate = wr
                best_strat_id = strat_id

        if not best_strat_id or best_win_rate <= 55:
            continue

        df = _build_indicator_df(db, stock.id)
        if df.empty:
            continue

        if check_strategy_active(df, best_strat_id):
            curr_price = float(df.iloc[-1]["close"])
            max_spend = min(liquid_cash * MAX_POSITION_PCT, INITIAL_MODAL * MAX_POSITION_PCT)
            lots = max(1, int(max_spend // (curr_price * 100)))
            cost = lots * curr_price * 100

            if cost > liquid_cash:
                lots = max(1, int(liquid_cash // (curr_price * 100)))
                cost = lots * curr_price * 100

            if lots < 1 or cost > liquid_cash:
                continue

            execute_ai_trade(
                stock.ticker, "BUY", lots, agent_name,
                f"Strategy: {best_strat_id} (WR: {best_win_rate:.1f}%) | Signal active"
            )
            liquid_cash -= cost
            executed.append(
                f"BUY {stock.ticker} {lots} lot @ Rp {curr_price:,.0f} | Cost: Rp {cost:,.0f} | {best_strat_id} WR:{best_win_rate:.0f}%"
            )

    db.close()

    lines = []
    if sold:
        lines.append(f"SELLS ({len(sold)}):")
        lines += [f"  - {s}" for s in sold]
    if executed:
        lines.append(f"BUYS ({len(executed)}):")
        lines += [f"  - {e}" for e in executed]
    if not sold and not executed:
        return f"SCAN COMPLETE: {agent_name} — no signals triggered. Liquid cash: Rp {liquid_cash:,.0f}"

    return "SCAN COMPLETE:\n" + "\n".join(lines)


@mcp.tool()
def get_portfolio_summary(agent_name: str) -> str:
    """
    Get full portfolio summary for a specific agent: open positions, unrealized P&L, realized P&L.
    - agent_name: CLAUDE, GEMINI, or USER
    """
    db = SessionLocal()
    agent_name = agent_name.upper()

    try:
        trades = db.query(models.TradeLog).order_by(models.TradeLog.date).all()
        holdings: Dict[str, dict] = {}

        for t in trades:
            raw_type = t.trade_type.upper()
            if agent_name == "CLAUDE" and "CLAUDE" not in raw_type:
                continue
            if agent_name == "GEMINI" and "GEMINI" not in raw_type:
                continue
            if agent_name == "USER" and ("CLAUDE" in raw_type or "GEMINI" in raw_type):
                continue

            ticker = t.stock.ticker
            if ticker not in holdings:
                holdings[ticker] = {"shares": 0, "avg_price": 0.0, "realized_pnl": 0.0}

            data = holdings[ticker]
            qty = t.quantity * 100
            if t.action == "BUY":
                total_cost = (data["shares"] * data["avg_price"]) + (qty * t.price)
                data["shares"] += qty
                data["avg_price"] = total_cost / data["shares"] if data["shares"] > 0 else 0.0
            else:
                data["realized_pnl"] += (t.price - data["avg_price"]) * qty
                data["shares"] -= qty

        positions = []
        total_unrealized = 0.0
        total_realized = 0.0

        for ticker, data in holdings.items():
            if data["shares"] <= 0 and data["realized_pnl"] == 0.0:
                continue

            stock = db.query(models.Stock).filter(models.Stock.ticker == ticker).first()
            latest = (
                db.query(models.OHLCVDaily)
                .filter(models.OHLCVDaily.stock_id == stock.id)
                .order_by(desc(models.OHLCVDaily.date))
                .first()
            )
            current_price = latest.close if latest else data["avg_price"]
            unrealized = (current_price - data["avg_price"]) * data["shares"]
            market_value = current_price * data["shares"]

            total_unrealized += unrealized
            total_realized += data["realized_pnl"]

            unrealized_pct = 0.0
            if data["shares"] > 0 and data["avg_price"] > 0:
                unrealized_pct = round(unrealized / (data["avg_price"] * data["shares"]) * 100, 2)

            positions.append({
                "ticker": ticker,
                "name": stock.name,
                "lots": data["shares"] // 100,
                "shares": data["shares"],
                "avg_buy_price": round(data["avg_price"], 2),
                "current_price": current_price,
                "market_value": round(market_value, 2),
                "unrealized_pnl": round(unrealized, 2),
                "unrealized_pct": unrealized_pct,
                "realized_pnl": round(data["realized_pnl"], 2),
            })

        INITIAL_MODAL = 15_000_000
        total_invested = sum(
            p["avg_buy_price"] * p["shares"] for p in positions if p["shares"] > 0
        )
        liquid_cash = INITIAL_MODAL - total_invested + total_realized
        total_value = liquid_cash + sum(p["market_value"] for p in positions if p["shares"] > 0)

        result = {
            "agent": agent_name,
            "summary": {
                "initial_modal": INITIAL_MODAL,
                "liquid_cash": round(liquid_cash, 2),
                "total_invested": round(total_invested, 2),
                "total_value": round(total_value, 2),
                "open_positions": len([p for p in positions if p["shares"] > 0]),
                "total_unrealized_pnl": round(total_unrealized, 2),
                "total_realized_pnl": round(total_realized, 2),
                "total_pnl": round(total_unrealized + total_realized, 2),
            },
            "positions": [p for p in positions if p["shares"] > 0],
            "closed_positions": [p for p in positions if p["shares"] <= 0 and p["realized_pnl"] != 0],
        }
        return json.dumps(result, indent=2)
    finally:
        db.close()


@mcp.tool()
def get_trade_history(agent_name: str, limit: int = 20) -> str:
    """
    Get recent trade history for a specific agent.
    - agent_name: CLAUDE, GEMINI, or USER
    - limit: number of trades to return (default 20)
    """
    db = SessionLocal()
    agent_name = agent_name.upper()

    try:
        all_trades = (
            db.query(models.TradeLog)
            .order_by(desc(models.TradeLog.date), desc(models.TradeLog.id))
            .limit(limit * 4)
            .all()
        )

        result = []
        for t in all_trades:
            raw_type = t.trade_type.upper()
            if agent_name == "CLAUDE" and "CLAUDE" not in raw_type:
                continue
            if agent_name == "GEMINI" and "GEMINI" not in raw_type:
                continue
            if agent_name == "USER" and ("CLAUDE" in raw_type or "GEMINI" in raw_type):
                continue

            result.append({
                "date": str(t.date),
                "ticker": t.stock.ticker,
                "action": t.action,
                "price": t.price,
                "quantity_lots": t.quantity,
                "total_value": t.price * t.quantity * 100,
                "notes": t.notes,
            })

            if len(result) >= limit:
                break

        return json.dumps(result, indent=2)
    finally:
        db.close()


@mcp.tool()
def set_position_target(
    agent_name: str,
    ticker: str,
    take_profit_price: float = None,
    cut_loss_price: float = None,
    decision: str = "HOLD",
    notes: str = "",
) -> str:
    """
    Set or update take profit / cut loss targets for an active position.
    Call this after opening a new position, or whenever target needs to be revised.
    - agent_name: CLAUDE or GEMINI
    - ticker: stock ticker
    - take_profit_price: harga target untuk ambil profit (opsional)
    - cut_loss_price: harga batas cut loss (opsional)
    - decision: stance saat ini — HOLD, BUY_MORE, WAIT, TAKE_PROFIT, atau CUT_LOSS
    - notes: alasan / reasoning untuk target ini
    """
    db = SessionLocal()
    ticker = ticker.upper()
    agent_name = agent_name.upper()
    try:
        existing = db.query(models.AgentPositionTarget).filter(
            models.AgentPositionTarget.agent_name == agent_name,
            models.AgentPositionTarget.ticker == ticker,
            models.AgentPositionTarget.is_active == 1,
        ).first()

        if existing:
            if take_profit_price is not None:
                existing.take_profit_price = take_profit_price
            if cut_loss_price is not None:
                existing.cut_loss_price = cut_loss_price
            existing.decision = decision
            existing.notes = notes
            existing.updated_at = datetime.utcnow()
            db.commit()
            return (
                f"SUCCESS: Target {agent_name}/{ticker} diperbarui | "
                f"TP: {take_profit_price}, CL: {cut_loss_price}, Decision: {decision}"
            )
        else:
            new_target = models.AgentPositionTarget(
                agent_name=agent_name,
                ticker=ticker,
                take_profit_price=take_profit_price,
                cut_loss_price=cut_loss_price,
                decision=decision,
                notes=notes,
                is_active=1,
            )
            db.add(new_target)
            db.commit()
            return (
                f"SUCCESS: Target {agent_name}/{ticker} disimpan | "
                f"TP: {take_profit_price}, CL: {cut_loss_price}, Decision: {decision}"
            )
    except Exception as e:
        db.rollback()
        return f"ERROR: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def get_agent_context(agent_name: str) -> str:
    """
    Load konteks lengkap sesi trading: posisi aktif + target harga + alert mendesak.
    SELALU panggil tool ini PERTAMA KALI di awal setiap sesi trading sebelum aksi apapun.
    Menampilkan setiap posisi terbuka beserta take profit, cut loss, dan decision terakhir.
    - agent_name: CLAUDE or GEMINI
    """
    db = SessionLocal()
    agent_name = agent_name.upper()
    INITIAL_MODAL = 15_000_000
    try:
        holdings = _get_agent_holdings(db, agent_name)

        targets = db.query(models.AgentPositionTarget).filter(
            models.AgentPositionTarget.agent_name == agent_name,
            models.AgentPositionTarget.is_active == 1,
        ).all()
        targets_map = {t.ticker: t for t in targets}

        context_positions = []
        urgent_alerts = []

        for ticker, data in holdings.items():
            if data["shares"] <= 0:
                continue

            stock = db.query(models.Stock).filter(models.Stock.ticker == ticker).first()
            if not stock:
                continue
            latest = (
                db.query(models.OHLCVDaily)
                .filter(models.OHLCVDaily.stock_id == stock.id)
                .order_by(desc(models.OHLCVDaily.date))
                .first()
            )
            current_price = float(latest.close) if latest else data["avg_price"]
            unrealized_pct = round(
                (current_price - data["avg_price"]) / data["avg_price"] * 100, 2
            )

            target = targets_map.get(ticker)
            tp = target.take_profit_price if target else None
            cl = target.cut_loss_price if target else None
            decision = target.decision if target else "NO_TARGET"
            target_notes = target.notes if target else ""

            position_alerts = []
            if tp and current_price >= tp:
                msg = f"TAKE PROFIT TERCAPAI — harga {current_price:,.0f} >= target {tp:,.0f}"
                position_alerts.append(msg)
                urgent_alerts.append(f"{ticker}: {msg}")
            if cl and current_price <= cl:
                msg = f"CUT LOSS TRIGGERED — harga {current_price:,.0f} <= batas {cl:,.0f}"
                position_alerts.append(msg)
                urgent_alerts.append(f"{ticker}: {msg}")
            if unrealized_pct <= -7.0:
                msg = f"STOP LOSS -7% TERCAPAI — unrealized {unrealized_pct:.1f}%"
                position_alerts.append(msg)
                urgent_alerts.append(f"{ticker}: {msg}")
            if not tp and not cl:
                position_alerts.append("PERINGATAN: Belum ada target TP/CL — set dengan set_position_target()")

            context_positions.append({
                "ticker": ticker,
                "name": stock.name,
                "lots": data["shares"] // 100,
                "avg_buy_price": round(data["avg_price"], 2),
                "current_price": current_price,
                "unrealized_pct": unrealized_pct,
                "target": {
                    "take_profit_price": tp,
                    "cut_loss_price": cl,
                    "decision": decision,
                    "notes": target_notes,
                },
                "alerts": position_alerts,
            })

        total_invested = sum(d["avg_price"] * d["shares"] for d in holdings.values() if d["shares"] > 0)
        total_realized = sum(d["realized"] for d in holdings.values())
        liquid_cash = INITIAL_MODAL - total_invested + total_realized

        result = {
            "agent": agent_name,
            "liquid_cash": round(liquid_cash, 2),
            "open_positions_count": len(context_positions),
            "urgent_alerts": urgent_alerts,
            "positions": context_positions,
            "instructions": (
                "1) Baca semua posisi dan alertnya. "
                "2) Jika ada ALERT mendesak (TP/CL/Stop Loss), prioritaskan eksekusi dulu. "
                "3) Posisi tanpa target: set target dengan set_position_target() setelah analisa. "
                "4) Baru kemudian lanjut scan peluang baru."
            ),
        }
        return json.dumps(result, indent=2, ensure_ascii=False)
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run()
