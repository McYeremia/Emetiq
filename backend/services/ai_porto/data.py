"""Data deterministik untuk AI Porto — snapshot porto AI + kandidat saham.

Semua angka dari DB nyata; LLM hanya menalar di atasnya (tidak mengarang harga).
"""
from typing import Any, Dict, List

from sqlalchemy import desc
from sqlalchemy.orm import Session

import models
from services import trade_exec
from services.indicators import calculate_indicators
from services.advisor import data_provider as dp
from services.ai_porto import scoring

AGENT = "AI"
DEFAULT_CANDIDATES = 18
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


def price_of(db: Session, ticker: str):
    """(stock, harga close terakhir) untuk sebuah ticker; (None, None) bila tak ada."""
    stock = db.query(models.Stock).filter(models.Stock.ticker == ticker.upper()).first()
    if not stock:
        return None, None
    return stock, _latest_close(db, stock.id)


def scored_candidates(db: Session, limit: int = DEFAULT_CANDIDATES) -> List[Dict[str, Any]]:
    """Kandidat ber-skor (lever 4): screening + sinyal watcher, diperkaya teknikal, diberi skor."""
    sig_map = {s["ticker"]: s for s in _signals(db, DEFAULT_SIGNALS)}

    # Universe: hasil screening likuid + ticker yang punya sinyal (walau di luar top-cap).
    universe: Dict[str, Dict[str, Any]] = {}
    for c in dp.screen(db, limit=limit + 8):
        universe[c["ticker"]] = dict(c)
    for tk in sig_map:
        if tk not in universe:
            stock, px = price_of(db, tk)
            if stock is None:
                continue
            universe[tk] = {
                "ticker": tk, "name": stock.name, "sector": stock.sector,
                "last_price": px, "market_cap": stock.market_cap,
                "pe": stock.pe_ratio, "pbv": stock.pbv_ratio,
                "dividend_yield": stock.dividend_yield,
            }

    out: List[Dict[str, Any]] = []
    for tk, c in universe.items():
        stock = db.query(models.Stock).filter(models.Stock.ticker == tk).first()
        if not stock:
            continue
        # Saham dengan data sangat sedikit bisa bikin lib indikator error — jangan
        # sampai satu saham tipis menggagalkan seluruh pipeline.
        try:
            inds = calculate_indicators(db, stock)
        except Exception:
            inds = {}
        last = c.get("last_price") or _latest_close(db, stock.id)
        c["rsi"] = inds.get("RSI_14")
        c["trend"] = dp.trend_of(inds, last)
        c["signal_strength"] = sig_map.get(tk, {}).get("strength")
        c["signal_type"] = sig_map.get(tk, {}).get("type")
        c["score"] = scoring.score_candidate(c)
        out.append(c)

    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:limit]


def candidates(db: Session, limit: int = DEFAULT_CANDIDATES) -> Dict[str, Any]:
    """Universe kandidat mentah (dipertahankan untuk kompatibilitas)."""
    return {"screen": dp.screen(db, limit=limit), "signals": _signals(db, DEFAULT_SIGNALS)}
