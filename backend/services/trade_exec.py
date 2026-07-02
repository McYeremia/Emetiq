"""Eksekusi trade & perhitungan holding bersama.

Dipakai oleh trade manual (`routers/trades.py`) DAN AI Porto (`services/ai_porto`),
agar aturan dana/holding tidak terduplikasi. Semua porto memakai modal dummy yang sama.

Bucket ("agent"):
- USER   -> trade manual milik satu user (di-scope `user_id`).
- GEMINI -> trade_type AUTO_GEMINI (global, user_id NULL).
- CLAUDE -> trade_type AUTO_CLAUDE (global).
- AI     -> trade_type AUTO_AI     (global) — porto yang dikelola AI Porto.
"""
from typing import Dict, Optional
from datetime import date

from sqlalchemy import desc
from sqlalchemy.orm import Session

import models

INITIAL_MODAL = 15_000_000  # modal dummy per bucket

# agent -> trade_type untuk bucket global (bukan USER)
TRADE_TYPE_OF = {"GEMINI": "AUTO_GEMINI", "CLAUDE": "AUTO_CLAUDE", "AI": "AUTO_AI"}


class TradeError(Exception):
    """Trade ditolak. `status` = kode HTTP yang cocok."""
    status = 400


class StockNotFound(TradeError):
    status = 404


class TradeRejected(TradeError):
    status = 400


def agent_of(trade_type: str) -> str:
    """Petakan trade_type -> bucket agent."""
    tt = (trade_type or "").upper()
    if "CLAUDE" in tt:
        return "CLAUDE"
    if "GEMINI" in tt:
        return "GEMINI"
    if tt == "AUTO_AI":
        return "AI"
    return "USER"


def _agent_trades(db: Session, agent_key: str, user_id: Optional[str]):
    """Query trade milik satu bucket, urut kronologis."""
    q = db.query(models.TradeLog)
    if agent_key == "USER":
        q = q.filter(models.TradeLog.user_id == user_id)
    else:
        q = q.filter(models.TradeLog.trade_type == TRADE_TYPE_OF[agent_key])
    return q.order_by(models.TradeLog.date, models.TradeLog.id).all()


def holdings_for(db: Session, agent_key: str, user_id: Optional[str] = None) -> Dict[str, dict]:
    """Replay trade -> {ticker: {shares, avg_price, realized}} untuk satu bucket."""
    positions: Dict[str, dict] = {}
    for t in _agent_trades(db, agent_key, user_id):
        ticker = t.stock.ticker
        pos = positions.setdefault(ticker, {"shares": 0, "avg_price": 0.0, "realized": 0.0})
        qty = t.quantity * 100
        if t.action == "BUY":
            total_cost = pos["shares"] * pos["avg_price"] + qty * t.price
            pos["shares"] += qty
            pos["avg_price"] = total_cost / pos["shares"] if pos["shares"] > 0 else 0.0
        else:  # SELL
            pos["realized"] += (t.price - pos["avg_price"]) * qty
            pos["shares"] -= qty
    return positions


def available_cash(db: Session, agent_key: str, user_id: Optional[str] = None) -> float:
    """Kas tersedia = modal - nilai diinvestasikan + realized P&L."""
    holdings = holdings_for(db, agent_key, user_id)
    invested = sum(p["shares"] * p["avg_price"] for p in holdings.values() if p["shares"] > 0)
    realized = sum(p["realized"] for p in holdings.values())
    return INITIAL_MODAL - invested + realized


def _latest_close(db: Session, stock_id: int) -> Optional[float]:
    row = (
        db.query(models.OHLCVDaily)
        .filter(models.OHLCVDaily.stock_id == stock_id)
        .order_by(desc(models.OHLCVDaily.date))
        .first()
    )
    return float(row.close) if row and row.close is not None else None


def execute_trade(
    db: Session,
    *,
    ticker: str,
    action: str,
    lots: int,
    trade_type: str,
    price: Optional[float] = None,
    user_id: Optional[str] = None,
    strategy_id: Optional[str] = "custom",
    notes: str = "",
) -> models.TradeLog:
    """Validasi dana/holding lalu catat satu TradeLog. Gagal -> TradeError."""
    ticker = ticker.upper()
    action = action.upper()
    if action not in ("BUY", "SELL"):
        raise TradeRejected(f"Aksi tidak dikenal: {action}")
    if not isinstance(lots, int) or lots <= 0:
        raise TradeRejected("Jumlah lot harus bilangan bulat > 0.")

    stock = db.query(models.Stock).filter(models.Stock.ticker == ticker).first()
    if not stock:
        raise StockNotFound(f"Saham {ticker} tidak ditemukan.")

    if not price or price <= 0:
        price = _latest_close(db, stock.id)
    if not price or price <= 0:
        raise TradeRejected(f"Harga {ticker} tidak tersedia.")

    agent_key = agent_of(trade_type)
    qty_shares = lots * 100

    if action == "SELL":
        held = holdings_for(db, agent_key, user_id).get(ticker, {}).get("shares", 0)
        if held < qty_shares:
            raise TradeRejected(
                f"Posisi tidak cukup: punya {held // 100} lot, butuh {lots} lot {ticker}."
            )
    else:  # BUY
        cash = available_cash(db, agent_key, user_id)
        cost = price * qty_shares
        if cost > cash:
            raise TradeRejected(
                f"Dana tidak cukup: butuh Rp {cost:,.0f}, tersedia Rp {cash:,.0f}."
            )

    trade = models.TradeLog(
        stock_id=stock.id,
        action=action,
        date=date.today(),
        price=price,
        quantity=lots,
        trade_type=trade_type.upper(),
        strategy_id=strategy_id,
        notes=notes,
        user_id=user_id,
    )
    db.add(trade)
    db.commit()
    return trade
