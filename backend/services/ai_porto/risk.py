"""Risiko adaptif AI Porto: rezim, drawdown, dan auto exit TP/CL.

Semua deterministik (kode), tidak memanggil LLM. Ini lapisan yang menjamin porto
tetap disiplin apa pun kualitas keluaran model.
"""
import bisect
from typing import Any, Dict, List

from sqlalchemy.orm import Session, joinedload

import models
from services.trade_exec import INITIAL_MODAL
from services.ai_porto import config

AI_TRADE_TYPE = "AUTO_AI"


def _closes_by_stock(db: Session, stock_ids: List[int]) -> Dict[int, tuple]:
    """1 query utk semua stock_id -> (list tanggal terurut, list close sejajar).

    Dipakai `bisect` di `peak_equity` utk mencari "close pada/sebelum tanggal X"
    tanpa query per posisi per trade (dulu O(trade x posisi) round-trip DB).
    """
    if not stock_ids:
        return {}
    rows = (
        db.query(models.OHLCVDaily)
        .filter(models.OHLCVDaily.stock_id.in_(stock_ids))
        .order_by(models.OHLCVDaily.stock_id, models.OHLCVDaily.date)
        .all()
    )
    out: Dict[int, tuple] = {}
    dates: Dict[int, list] = {}
    closes: Dict[int, list] = {}
    for r in rows:
        dates.setdefault(r.stock_id, []).append(r.date)
        closes.setdefault(r.stock_id, []).append(float(r.close) if r.close is not None else None)
    for sid in dates:
        out[sid] = (dates[sid], closes[sid])
    return out


def peak_equity(db: Session, current_total: float) -> float:
    """Puncak equity historis bucket AI (approx, di titik-titik trade) vs nilai sekarang."""
    trades = (
        db.query(models.TradeLog)
        .options(joinedload(models.TradeLog.stock))
        .filter(models.TradeLog.trade_type == AI_TRADE_TYPE)
        .order_by(models.TradeLog.date, models.TradeLog.id)
        .all()
    )
    price_series = _closes_by_stock(db, [t.stock_id for t in trades])

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
                dates, closes = price_series.get(p["stock_id"], ([], []))
                idx = bisect.bisect_right(dates, t.date) - 1
                px = closes[idx] if idx >= 0 and closes[idx] is not None else None
                holdings_value += p["shares"] * (px or p["avg"])
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
