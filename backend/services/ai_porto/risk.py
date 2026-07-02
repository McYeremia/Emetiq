"""Risiko adaptif AI Porto: rezim, drawdown, dan auto exit TP/CL.

Semua deterministik (kode), tidak memanggil LLM. Ini lapisan yang menjamin porto
tetap disiplin apa pun kualitas keluaran model.
"""
from typing import Any, Dict, List

from sqlalchemy import desc
from sqlalchemy.orm import Session

import models
from services.trade_exec import INITIAL_MODAL
from services.ai_porto import config

AI_TRADE_TYPE = "AUTO_AI"


def _close_on_or_before(db: Session, stock_id: int, on_date):
    row = (
        db.query(models.OHLCVDaily)
        .filter(models.OHLCVDaily.stock_id == stock_id, models.OHLCVDaily.date <= on_date)
        .order_by(desc(models.OHLCVDaily.date))
        .first()
    )
    return float(row.close) if row and row.close is not None else None


def peak_equity(db: Session, current_total: float) -> float:
    """Puncak equity historis bucket AI (approx, di titik-titik trade) vs nilai sekarang."""
    trades = (
        db.query(models.TradeLog)
        .filter(models.TradeLog.trade_type == AI_TRADE_TYPE)
        .order_by(models.TradeLog.date, models.TradeLog.id)
        .all()
    )
    cash = float(INITIAL_MODAL)
    positions: Dict[str, dict] = {}
    peak = float(INITIAL_MODAL)

    for t in trades:
        ticker = t.stock.ticker
        qty = t.quantity * 100
        pos = positions.setdefault(ticker, {"shares": 0, "avg": 0.0, "stock_id": t.stock_id})
        if t.action == "BUY":
            cash -= qty * t.price
            total = pos["shares"] * pos["avg"] + qty * t.price
            pos["shares"] += qty
            pos["avg"] = total / pos["shares"] if pos["shares"] > 0 else 0.0
        else:  # SELL
            cash += qty * t.price
            pos["shares"] -= qty

        holdings_value = 0.0
        for p in positions.values():
            if p["shares"] > 0:
                px = _close_on_or_before(db, p["stock_id"], t.date) or p["avg"]
                holdings_value += p["shares"] * px
        peak = max(peak, cash + holdings_value)

    return max(peak, current_total)


def compute_regime(total_value: float, peak: float) -> str:
    """Tentukan rezim risiko dari return vs modal & drawdown dari puncak."""
    ret = (total_value - INITIAL_MODAL) / INITIAL_MODAL
    drawdown = (peak - total_value) / peak if peak > 0 else 0.0
    if ret <= config.DEF_RETURN or drawdown >= config.DEF_MAX_DD:
        return "DEFENSIVE"
    if ret >= config.AGG_RETURN and drawdown < config.AGG_MAX_DD:
        return "AGGRESSIVE"
    return "NORMAL"


def guardrails(regime: str) -> Dict[str, Any]:
    return config.REGIMES.get(regime, config.REGIMES["NORMAL"])


def auto_exit_orders(state: Dict[str, Any], guard: Dict[str, Any]) -> List[Dict[str, Any]]:
    """SELL otomatis untuk holdings yang kena take-profit / cut-loss."""
    tp = guard["take_profit"] * 100
    cl = guard["cut_loss"] * 100
    orders: List[Dict[str, Any]] = []
    for h in state.get("holdings", []):
        pct = h.get("unrealized_pct")
        lots = h.get("lots", 0)
        if pct is None or lots <= 0:
            continue
        if pct >= tp:
            orders.append({"ticker": h["ticker"], "lots": lots, "reason": f"take-profit +{pct:.1f}%"})
        elif pct <= -cl:
            orders.append({"ticker": h["ticker"], "lots": lots, "reason": f"cut-loss {pct:.1f}%"})
    return orders
