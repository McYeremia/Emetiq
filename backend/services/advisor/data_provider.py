"""Data deterministik untuk AI Advisor — TIDAK memanggil LLM.

Tiga builder: screen(), analyze(), portfolio(). Semua angka diambil dari DB nyata
(fundamental, OHLCV, indikator, prediksi ML) sehingga LLM hanya menalar di atas angka
yang sudah pasti benar. Lihat spec bagian 4 ("Detail Pipeline").
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

import models
from services.indicators import calculate_indicators
import services.ml_predictor as ml
from services.advisor import config

INITIAL_MODAL = 15_000_000  # samakan dengan routers/trades.py
USER_TRADE_TYPES_EXCLUDED = {"AUTO_GEMINI", "AUTO_CLAUDE"}  # sisanya = milik user


# ── Helper kecil ─────────────────────────────────────────────────────────────

def _latest_ohlcv(db: Session, stock_id: int):
    return (
        db.query(models.OHLCVDaily)
        .filter(models.OHLCVDaily.stock_id == stock_id)
        .order_by(desc(models.OHLCVDaily.date))
        .first()
    )


def _latest_close(db: Session, stock_id: int) -> Optional[float]:
    row = _latest_ohlcv(db, stock_id)
    return float(row.close) if row and row.close is not None else None


def rsi_band(rsi: Optional[float]) -> Optional[str]:
    if rsi is None:
        return None
    if rsi < 30:
        return "oversold"
    if rsi > 70:
        return "overbought"
    return "neutral"


def trend_of(indicators: dict, last_close: Optional[float]) -> Optional[str]:
    """Tren naik bila harga di atas MA50 (fallback MA20)."""
    if last_close is None:
        return None
    ma50 = indicators.get("MA_50")
    ma20 = indicators.get("MA_20")
    ref = ma50 if ma50 is not None else ma20
    if ref is None:
        return None
    return "up" if last_close >= ref else "down"


# ── Pipeline 1: Screening ────────────────────────────────────────────────────

def screen(
    db: Session,
    *,
    pe_max: Optional[float] = None,
    pbv_max: Optional[float] = None,
    div_min: Optional[float] = None,
    rsi: Optional[str] = None,
    trend: Optional[str] = None,
    sector: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Saring saham deterministik. Filter fundamental dulu (murah), baru indikator."""
    limit = limit or config.SCREEN_MAX_CANDIDATES

    q = db.query(models.Stock).filter(models.Stock.ticker != "^JKSE")
    stocks = q.all()

    # 1) Filter fundamental (kolom Stock, tanpa baca OHLCV) — murah
    def passes_fundamental(s: models.Stock) -> bool:
        if pe_max is not None and (s.pe_ratio is None or s.pe_ratio <= 0 or s.pe_ratio > pe_max):
            return False
        if pbv_max is not None and (s.pbv_ratio is None or s.pbv_ratio <= 0 or s.pbv_ratio > pbv_max):
            return False
        if div_min is not None and (s.dividend_yield is None or s.dividend_yield < div_min):
            return False
        if sector and (s.sector or "").lower() != sector.lower():
            return False
        return True

    survivors = [s for s in stocks if passes_fundamental(s)]
    # Batasi jumlah yang dihitung indikatornya (urut market cap desc) demi latency
    survivors.sort(key=lambda s: (s.market_cap or 0), reverse=True)
    survivors = survivors[: config.SCREEN_WORKING_SET]

    needs_indicators = rsi is not None or trend is not None
    results: List[Dict[str, Any]] = []

    for s in survivors:
        last_close = _latest_close(db, s.id)
        inds = calculate_indicators(db, s) if needs_indicators else {}

        if rsi is not None:
            if rsi_band(inds.get("RSI_14")) != rsi:
                continue
        if trend is not None:
            if trend_of(inds, last_close) != trend:
                continue

        results.append({
            "ticker": s.ticker,
            "name": s.name,
            "sector": s.sector,
            "last_price": last_close,
            "market_cap": s.market_cap,
            "pe": s.pe_ratio,
            "pbv": s.pbv_ratio,
            "dividend_yield": s.dividend_yield,
            "rsi": inds.get("RSI_14"),
            "trend": trend_of(inds, last_close) if inds else None,
        })
        if len(results) >= limit:
            break

    return results


# ── Pipeline 2: Analisa 1 saham ──────────────────────────────────────────────

def analyze(db: Session, ticker: str) -> Dict[str, Any]:
    ticker = ticker.upper()
    stock = db.query(models.Stock).filter(models.Stock.ticker == ticker).first()
    if not stock:
        return {"found": False, "ticker": ticker}

    inds = calculate_indicators(db, stock)
    rows = (
        db.query(models.OHLCVDaily)
        .filter(models.OHLCVDaily.stock_id == stock.id)
        .order_by(desc(models.OHLCVDaily.date))
        .limit(60)
        .all()
    )  # terbaru -> terlama
    closes = [float(r.close) for r in rows if r.close is not None]
    last_close = closes[0] if closes else None
    prev_close = closes[1] if len(closes) > 1 else None
    change_pct = (
        round((last_close - prev_close) / prev_close * 100, 2)
        if last_close is not None and prev_close not in (None, 0)
        else None
    )
    window = closes[:20]
    high_20 = max(window) if window else None
    low_20 = min(window) if window else None

    pred = ml.read_prediction(ticker, db)
    if pred.get("status") != "ok":
        pred = None

    return {
        "found": True,
        "ticker": ticker,
        "name": stock.name,
        "sector": stock.sector,
        "last_price": last_close,
        "change_pct": change_pct,
        "high_20d": high_20,
        "low_20d": low_20,
        "bars_available": len(closes),
        "fundamentals": {
            "pe": stock.pe_ratio,
            "pbv": stock.pbv_ratio,
            "dividend_yield": stock.dividend_yield,
            "market_cap": stock.market_cap,
        },
        "indicators": inds,
        "rsi_band": rsi_band(inds.get("RSI_14")),
        "trend": trend_of(inds, last_close),
        "ml_prediction": pred,
    }


# ── Pipeline 3: Portofolio ───────────────────────────────────────────────────

def portfolio(db: Session, user_key: str = "USER") -> Dict[str, Any]:
    """Snapshot holding milik user (default: trade MANUAL = 'USER')."""
    trades = (
        db.query(models.TradeLog)
        .order_by(models.TradeLog.date)
        .all()
    )

    positions: Dict[str, Dict[str, Any]] = {}
    realized = 0.0
    for t in trades:
        if t.trade_type in USER_TRADE_TYPES_EXCLUDED:
            continue  # bukan milik user
        ticker = t.stock.ticker
        pos = positions.setdefault(ticker, {"shares": 0, "avg_price": 0.0, "stock_id": t.stock_id})
        qty = t.quantity * 100
        if t.action == "BUY":
            total_cost = pos["shares"] * pos["avg_price"] + qty * t.price
            pos["shares"] += qty
            pos["avg_price"] = total_cost / pos["shares"] if pos["shares"] > 0 else 0.0
        else:  # SELL
            realized += (t.price - pos["avg_price"]) * qty
            pos["shares"] -= qty

    holdings: List[Dict[str, Any]] = []
    invested = 0.0
    unrealized_total = 0.0
    for ticker, pos in positions.items():
        if pos["shares"] <= 0:
            continue
        stock = db.query(models.Stock).filter(models.Stock.ticker == ticker).first()
        if not stock:
            continue
        last_close = _latest_close(db, stock.id) or pos["avg_price"]
        cost_basis = pos["shares"] * pos["avg_price"]
        unrealized = (last_close - pos["avg_price"]) * pos["shares"]
        invested += cost_basis
        unrealized_total += unrealized

        inds = calculate_indicators(db, stock)
        holdings.append({
            "ticker": ticker,
            "lots": pos["shares"] / 100,
            "shares": pos["shares"],
            "avg_price": round(pos["avg_price"], 2),
            "current_price": round(last_close, 2),
            "cost_basis": round(cost_basis, 2),
            "unrealized_pnl": round(unrealized, 2),
            "unrealized_pct": round(unrealized / cost_basis * 100, 2) if cost_basis else None,
            "rsi": inds.get("RSI_14"),
            "rsi_band": rsi_band(inds.get("RSI_14")),
            "trend": trend_of(inds, last_close),
        })

    holdings.sort(key=lambda h: h["cost_basis"], reverse=True)
    holdings = holdings[: config.PORTFOLIO_MAX_POSITIONS]

    cash = INITIAL_MODAL - invested + realized
    total_value = INITIAL_MODAL + realized + unrealized_total
    # bobot tiap posisi terhadap total nilai portofolio
    for h in holdings:
        market_val = h["current_price"] * h["shares"]
        h["weight_pct"] = round(market_val / total_value * 100, 2) if total_value else None

    return {
        "cash": round(cash, 2),
        "invested": round(invested, 2),
        "unrealized": round(unrealized_total, 2),
        "realized": round(realized, 2),
        "total_value": round(total_value, 2),
        "position_count": len(holdings),
        "holdings": holdings,
    }
