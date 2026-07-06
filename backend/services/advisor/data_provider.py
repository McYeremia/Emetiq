"""Data deterministik untuk AI Advisor — TIDAK memanggil LLM.

Tiga builder: screen(), analyze(), portfolio(). Semua angka diambil dari DB nyata
(fundamental, OHLCV, indikator, prediksi ML) sehingga LLM hanya menalar di atas angka
yang sudah pasti benar. Lihat spec bagian 4 ("Detail Pipeline").
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

import models
from services.indicators import calculate_indicators, calculate_indicators_from_df, get_ohlcv_df_bulk
from services.advisor import config
from services.advisor.formatting import round_numbers

INITIAL_MODAL = 15_000_000  # samakan dengan routers/trades.py

# Lookback saat menghitung indikator utk BANYAK saham sekaligus (screening/kandidat).
# Nilai indikator terakhir (RSI/MA/MACD dst) praktis sama dgn histori penuh selama
# jendela ini > window terpanjang (MA_200) — dipakai demi kecepatan (hindari fetch
# 5 tahun histori x ratusan saham).
SCREEN_INDICATOR_LOOKBACK_DAYS = 400


# ── Helper kecil ─────────────────────────────────────────────────────────────

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
    price_max: Optional[float] = None,
    price_min: Optional[float] = None,
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

    # 1 query utk histori OHLCV semua survivor (bukan 1 query per saham) — hindari N+1
    ohlcv_by_id = get_ohlcv_df_bulk(
        db, [s.id for s in survivors], lookback_days=SCREEN_INDICATOR_LOOKBACK_DAYS
    )

    for s in survivors:
        df = ohlcv_by_id.get(s.id)
        last_close = float(df["close"].iloc[-1]) if df is not None and not df.empty else None
        inds = calculate_indicators_from_df(df) if needs_indicators else {}

        if price_max is not None and (last_close is None or last_close > price_max):
            continue
        if price_min is not None and (last_close is None or last_close < price_min):
            continue

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

    # Bulatkan semua angka (indikator & fundamental) sebelum dipakai LLM/UI.
    return round_numbers(results)


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

    # Bulatkan semua angka (indikator & fundamental) sebelum dipakai LLM/UI.
    return round_numbers({
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
    })


# ── Pipeline 3: Portofolio ───────────────────────────────────────────────────

def portfolio(db: Session, user_id: str) -> Dict[str, Any]:
    """Snapshot holding milik satu user (di-scope berdasarkan user_id trade)."""
    trades = (
        db.query(models.TradeLog)
        .options(joinedload(models.TradeLog.stock))
        .filter(models.TradeLog.user_id == user_id)
        .order_by(models.TradeLog.date)
        .all()
    )

    positions: Dict[str, Dict[str, Any]] = {}
    realized = 0.0
    for t in trades:
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

    active = {tk: p for tk, p in positions.items() if p["shares"] > 0}
    # 1 query utk histori OHLCV semua posisi aktif (bukan 1 query per posisi)
    ohlcv_by_id = get_ohlcv_df_bulk(db, [p["stock_id"] for p in active.values()])

    prelim: List[Dict[str, Any]] = []
    invested = 0.0
    unrealized_total = 0.0
    for ticker, pos in active.items():
        df = ohlcv_by_id.get(pos["stock_id"])
        last_close = (float(df["close"].iloc[-1]) if df is not None and not df.empty else None) or pos["avg_price"]
        cost_basis = pos["shares"] * pos["avg_price"]
        unrealized = (last_close - pos["avg_price"]) * pos["shares"]
        invested += cost_basis
        unrealized_total += unrealized
        prelim.append({"ticker": ticker, "pos": pos, "df": df, "last_close": last_close,
                       "cost_basis": cost_basis, "unrealized": unrealized})

    prelim.sort(key=lambda h: h["cost_basis"], reverse=True)
    prelim = prelim[: config.PORTFOLIO_MAX_POSITIONS]

    holdings: List[Dict[str, Any]] = []
    for h in prelim:
        pos, last_close, cost_basis, unrealized = h["pos"], h["last_close"], h["cost_basis"], h["unrealized"]
        inds = calculate_indicators_from_df(h["df"])
        holdings.append({
            "ticker": h["ticker"],
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
