"""Data deterministik untuk AI Porto — snapshot porto AI + kandidat saham.

Semua angka dari DB nyata; LLM hanya menalar di atasnya (tidak mengarang harga).
"""
from typing import Any, Dict, List

from sqlalchemy import desc
from sqlalchemy.orm import Session

import models
from services import trade_exec
from services.advisor import data_provider as dp

AGENT = "AI"
DEFAULT_CANDIDATES = 20
DEFAULT_SIGNALS = 15


def _latest_close(db: Session, stock_id: int):
    row = (
        db.query(models.OHLCVDaily)
        .filter(models.OHLCVDaily.stock_id == stock_id)
        .order_by(desc(models.OHLCVDaily.date))
        .first()
    )
    return float(row.close) if row and row.close is not None else None


def portfolio_state(db: Session) -> Dict[str, Any]:
    """Snapshot bucket AI: holdings, kas, P&L, total value."""
    raw = trade_exec.holdings_for(db, AGENT)

    holdings: List[Dict[str, Any]] = []
    invested = 0.0
    unrealized_total = 0.0
    realized_total = 0.0

    for ticker, pos in raw.items():
        realized_total += pos["realized"]
        if pos["shares"] <= 0:
            continue
        stock = db.query(models.Stock).filter(models.Stock.ticker == ticker).first()
        if not stock:
            continue
        curr = _latest_close(db, stock.id) or pos["avg_price"]
        cost_basis = pos["shares"] * pos["avg_price"]
        unrealized = (curr - pos["avg_price"]) * pos["shares"]
        invested += cost_basis
        unrealized_total += unrealized
        holdings.append({
            "ticker": ticker,
            "lots": pos["shares"] // 100,
            "shares": pos["shares"],
            "avg_price": round(pos["avg_price"], 2),
            "current_price": round(curr, 2),
            "cost_basis": round(cost_basis, 2),
            "unrealized_pnl": round(unrealized, 2),
            "unrealized_pct": round(unrealized / cost_basis * 100, 2) if cost_basis else None,
        })

    holdings.sort(key=lambda h: h["cost_basis"], reverse=True)
    cash = trade_exec.INITIAL_MODAL - invested + realized_total
    total_value = trade_exec.INITIAL_MODAL + realized_total + unrealized_total

    return {
        "cash": round(cash, 2),
        "invested": round(invested, 2),
        "unrealized": round(unrealized_total, 2),
        "realized": round(realized_total, 2),
        "total_value": round(total_value, 2),
        "position_count": len(holdings),
        "holdings": holdings,
    }


def _signals(db: Session, limit: int) -> List[Dict[str, Any]]:
    """Sinyal terkuat dari watcher (dedup per ticker), sebagai ide bagi AI."""
    rows = (
        db.query(models.Signal)
        .order_by(desc(models.Signal.strength))
        .limit(limit * 4)
        .all()
    )
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for s in rows:
        tk = s.stock.ticker
        if tk in seen:
            continue
        seen.add(tk)
        out.append({"ticker": tk, "type": s.type, "strength": s.strength, "strategy": s.strategy_id})
        if len(out) >= limit:
            break
    return out


def candidates(db: Session, limit: int = DEFAULT_CANDIDATES) -> Dict[str, Any]:
    """Universe kandidat: screening likuid (fundamental+harga) + sinyal watcher."""
    screen = dp.screen(db, limit=limit)
    return {"screen": screen, "signals": _signals(db, DEFAULT_SIGNALS)}
