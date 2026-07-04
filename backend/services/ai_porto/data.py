"""Data deterministik untuk AI Porto — snapshot porto AI + kandidat saham.

Semua angka dari DB nyata; LLM hanya menalar di atasnya (tidak mengarang harga).
"""
from typing import Any, Dict, List

from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

import models
from services import trade_exec
from services.indicators import calculate_indicators_from_df, get_ohlcv_df_bulk
from services.advisor import data_provider as dp
from services.advisor.formatting import round_numbers
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


def _latest_close_bulk(db: Session, stock_ids: List[int]) -> Dict[int, float]:
    """1 query utk harga terakhir banyak saham (bukan 1 query per saham)."""
    if not stock_ids:
        return {}
    rows = (
        db.query(models.OHLCVDaily)
        .filter(models.OHLCVDaily.stock_id.in_(stock_ids))
        .order_by(models.OHLCVDaily.stock_id, desc(models.OHLCVDaily.date))
        .all()
    )
    out: Dict[int, float] = {}
    for r in rows:
        if r.stock_id not in out and r.close is not None:
            out[r.stock_id] = float(r.close)  # baris pertama per stock_id = tanggal terbaru
    return out


def _stocks_by_ticker(db: Session, tickers) -> Dict[str, models.Stock]:
    tickers = list(tickers)
    if not tickers:
        return {}
    return {s.ticker: s for s in db.query(models.Stock).filter(models.Stock.ticker.in_(tickers)).all()}


def portfolio_state(db: Session) -> Dict[str, Any]:
    """Snapshot bucket AI: holdings, kas, P&L, total value."""
    raw = trade_exec.holdings_for(db, AGENT)
    realized_total = sum(pos["realized"] for pos in raw.values())
    active = {tk: p for tk, p in raw.items() if p["shares"] > 0}

    # 1 query Stock + 1 query harga terakhir utk semua posisi (bukan 2 query/posisi)
    stocks = _stocks_by_ticker(db, active.keys())
    closes = _latest_close_bulk(db, [s.id for s in stocks.values()])

    holdings: List[Dict[str, Any]] = []
    invested = 0.0
    unrealized_total = 0.0

    for ticker, pos in active.items():
        stock = stocks.get(ticker)
        if not stock:
            continue
        curr = closes.get(stock.id) or pos["avg_price"]
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
        .options(joinedload(models.Signal.stock))
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

    missing = [tk for tk in sig_map if tk not in universe]
    if missing:
        missing_stocks = _stocks_by_ticker(db, missing)
        missing_closes = _latest_close_bulk(db, [s.id for s in missing_stocks.values()])
        for tk, stock in missing_stocks.items():
            universe[tk] = {
                "ticker": tk, "name": stock.name, "sector": stock.sector,
                "last_price": missing_closes.get(stock.id), "market_cap": stock.market_cap,
                "pe": stock.pe_ratio, "pbv": stock.pbv_ratio,
                "dividend_yield": stock.dividend_yield,
            }

    # 1 query Stock + 1 query bulk OHLCV utk seluruh universe (bukan 2 query/kandidat)
    stocks = _stocks_by_ticker(db, universe.keys())
    ohlcv_by_id = get_ohlcv_df_bulk(
        db, [s.id for s in stocks.values()], lookback_days=dp.SCREEN_INDICATOR_LOOKBACK_DAYS
    )

    out: List[Dict[str, Any]] = []
    for tk, c in universe.items():
        stock = stocks.get(tk)
        if not stock:
            continue
        df = ohlcv_by_id.get(stock.id)
        # Saham dengan data sangat sedikit bisa bikin lib indikator error — jangan
        # sampai satu saham tipis menggagalkan seluruh pipeline.
        try:
            inds = calculate_indicators_from_df(df)
        except Exception:
            inds = {}
        last = c.get("last_price") or (float(df["close"].iloc[-1]) if df is not None and not df.empty else None)
        c["rsi"] = inds.get("RSI_14")
        c["trend"] = dp.trend_of(inds, last)
        c["signal_strength"] = sig_map.get(tk, {}).get("strength")
        c["signal_type"] = sig_map.get(tk, {}).get("type")
        c["score"] = scoring.score_candidate(c)
        out.append(c)

    out.sort(key=lambda x: x["score"], reverse=True)
    # Bulatkan angka (rsi & fundamental) sebelum dipakai LLM/UI — skor dihitung
    # di atas presisi penuh, jadi urutan tak berubah.
    return round_numbers(out[:limit])


def candidates(db: Session, limit: int = DEFAULT_CANDIDATES) -> Dict[str, Any]:
    """Universe kandidat mentah (dipertahankan untuk kompatibilitas)."""
    return {"screen": dp.screen(db, limit=limit), "signals": _signals(db, DEFAULT_SIGNALS)}
