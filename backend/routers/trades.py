import bisect
from collections import defaultdict
from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func
from pydantic import BaseModel
import models
from auth import CurrentUser, get_current_user
from database import get_db
from services.trade_exec import INITIAL_MODAL, agent_of, execute_trade, TradeError

router = APIRouter(prefix="/trades", tags=["trades"])

# Trade AI bersifat global (user_id NULL); trade USER milik pemiliknya. Helper di bawah
# membatasi himpunan trade yang "terlihat" oleh seorang user: trade miliknya + trade AI.
AI_TRADE_TYPES = ["AUTO_GEMINI", "AUTO_CLAUDE", "AUTO_AI"]

# Semua bucket porto yang ditampilkan berdampingan.
BUCKETS = ["USER", "GEMINI", "CLAUDE", "AI"]


def _visible_trades(db: Session, user_id: str):
    """Query trade yang relevan bagi user: miliknya (USER) + trade AI global.

    joinedload(stock) menghindari N+1: tanpa ini, tiap akses ``t.stock.ticker``
    memicu satu query terpisah — mahal karena Postgres Supabase remote.
    """
    return db.query(models.TradeLog).options(joinedload(models.TradeLog.stock)).filter(
        or_(models.TradeLog.user_id == user_id,
            models.TradeLog.trade_type.in_(AI_TRADE_TYPES))
    )


def _latest_prices(db: Session, stock_ids) -> Dict[int, tuple]:
    """Harga penutupan terakhir per stock_id dalam 2 query (bukan N).

    Return: {stock_id: (close, date)}. Portable SQLite & Postgres (tanpa DISTINCT ON).
    """
    ids = list({sid for sid in stock_ids if sid is not None})
    if not ids:
        return {}
    sub = (
        db.query(models.OHLCVDaily.stock_id, func.max(models.OHLCVDaily.date).label("md"))
        .filter(models.OHLCVDaily.stock_id.in_(ids))
        .group_by(models.OHLCVDaily.stock_id)
        .subquery()
    )
    rows = (
        db.query(models.OHLCVDaily.stock_id, models.OHLCVDaily.close, models.OHLCVDaily.date)
        .join(sub, and_(models.OHLCVDaily.stock_id == sub.c.stock_id,
                        models.OHLCVDaily.date == sub.c.md))
        .all()
    )
    return {sid: (close, d) for sid, close, d in rows}

class TradeRequest(BaseModel):
    ticker: str
    action: str
    quantity: int
    price: Optional[float] = None
    trade_type: str = "MANUAL"
    strategy_id: Optional[str] = "custom"
    notes: Optional[str] = ""


@router.get("/portfolio")
def get_portfolio(db: Session = Depends(get_db),
                  user: CurrentUser = Depends(get_current_user)):
    all_trades = _visible_trades(db, user.id).order_by(models.TradeLog.date).all()

    raw_portfolios = {k: {} for k in BUCKETS}
    ticker_to_stock_id: Dict[str, int] = {}

    for t in all_trades:
        p_key = agent_of(t.trade_type)

        ticker = t.stock.ticker
        ticker_to_stock_id[ticker] = t.stock_id
        if ticker not in raw_portfolios[p_key]:
            raw_portfolios[p_key][ticker] = {"shares": 0, "avg_price": 0.0, "realized_pnl": 0.0, "strategy": "", "notes": ""}

        data = raw_portfolios[p_key][ticker]
        qty = t.quantity * 100
        if t.action == "BUY":
            total_cost = (data["shares"] * data["avg_price"]) + (qty * t.price)
            data["shares"] += qty
            data["avg_price"] = total_cost / data["shares"] if data["shares"] > 0 else 0
            data["strategy"] = t.strategy_id
            data["notes"] = t.notes
        else:
            data["realized_pnl"] += (t.price - data["avg_price"]) * qty
            data["shares"] -= qty

    # Harga terakhir semua saham yang masih dipegang, di-batch (2 query total).
    held_ids = [
        ticker_to_stock_id[tk]
        for key in BUCKETS
        for tk, d in raw_portfolios[key].items()
        if d["shares"] > 0
    ]
    latest_prices = _latest_prices(db, held_ids)

    result = {}
    for key in BUCKETS:
        summary_list = []
        invested = 0.0
        total_realized = 0.0
        total_unrealized = 0.0

        for ticker, data in raw_portfolios[key].items():
            total_realized += data["realized_pnl"]

            if data["shares"] > 0:
                close, ldate = latest_prices.get(ticker_to_stock_id[ticker], (None, None))
                curr_price = close if close is not None else data["avg_price"]
                last_date = str(ldate) if ldate else None

                cost_basis = data["shares"] * data["avg_price"]
                unrealized = (curr_price - data["avg_price"]) * data["shares"]

                invested += cost_basis
                total_unrealized += unrealized

                summary_list.append({
                    "ticker": ticker,
                    "shares": data["shares"],
                    "avg_price": round(data["avg_price"], 2),
                    "current_price": round(curr_price, 2),
                    "last_date": last_date,
                    "cost_basis": round(cost_basis, 2),
                    "unrealized_pnl": round(unrealized, 2),
                    "strategy": data["strategy"],
                    "notes": data["notes"]
                })

        liquid = INITIAL_MODAL - invested + total_realized
        total_value = INITIAL_MODAL + total_realized + total_unrealized

        result[key] = {
            "modal": round(liquid, 2),
            "invested": round(invested, 2),
            "unrealized": round(total_unrealized, 2),
            "realized": round(total_realized, 2),
            "total_value": round(total_value, 2),
            "assets": summary_list
        }

    return result


@router.get("/growth")
def get_portfolio_growth(db: Session = Depends(get_db),
                         user: CurrentUser = Depends(get_current_user)):
    """Returns equity curve snapshots per agent for growth chart."""
    all_trades = _visible_trades(db, user.id).order_by(models.TradeLog.date).all()

    # Preload seluruh deret harga (date, close) untuk saham yang pernah ditransaksikan,
    # dalam SATU query. Sebelumnya endpoint ini melakukan 1 query OHLCV per posisi per
    # trade (O(trades × posisi)) — ratusan/ribuan round-trip ke Postgres remote.
    stock_ids = {t.stock_id for t in all_trades}
    series_dates: Dict[int, list] = defaultdict(list)
    series_close: Dict[int, list] = defaultdict(list)
    if stock_ids:
        rows = (
            db.query(models.OHLCVDaily.stock_id, models.OHLCVDaily.date, models.OHLCVDaily.close)
            .filter(models.OHLCVDaily.stock_id.in_(stock_ids))
            .order_by(models.OHLCVDaily.stock_id, models.OHLCVDaily.date)
            .all()
        )
        for sid, d, c in rows:
            series_dates[sid].append(d)
            series_close[sid].append(c)

    def price_asof(sid: int, d) -> Optional[float]:
        dates = series_dates.get(sid)
        if not dates:
            return None
        i = bisect.bisect_right(dates, d) - 1
        return series_close[sid][i] if i >= 0 else None

    result = {}

    for agent_key in BUCKETS:
        positions: Dict[str, dict] = {}
        cash = float(INITIAL_MODAL)
        date_values: Dict[str, float] = {}

        for t in all_trades:
            trade_agent = agent_of(t.trade_type)

            if trade_agent != agent_key:
                continue

            ticker = t.stock.ticker
            qty = t.quantity * 100

            if t.action == "BUY":
                cash -= qty * t.price
                if ticker not in positions:
                    positions[ticker] = {"shares": 0, "avg_price": 0.0, "stock_id": t.stock_id}
                total_shares = positions[ticker]["shares"] + qty
                total_cost = positions[ticker]["shares"] * positions[ticker]["avg_price"] + qty * t.price
                positions[ticker]["shares"] = total_shares
                positions[ticker]["avg_price"] = total_cost / total_shares
            elif t.action == "SELL" and ticker in positions:
                cash += qty * t.price
                positions[ticker]["shares"] -= qty
                if positions[ticker]["shares"] <= 0:
                    del positions[ticker]

            holdings_value = 0.0
            for tk, pos in positions.items():
                if pos["shares"] > 0:
                    price = price_asof(pos["stock_id"], t.date)
                    if price is None:
                        price = pos["avg_price"]
                    holdings_value += pos["shares"] * price

            date_str = str(t.date)
            date_values[date_str] = round(cash + holdings_value, 0)

        result[agent_key] = [
            {"date": d, "value": v}
            for d, v in sorted(date_values.items())
        ]

    return result


@router.get("/history")
def get_trade_history(agent: str = "USER", db: Session = Depends(get_db),
                      user: CurrentUser = Depends(get_current_user)):
    """Returns all trade logs for a given agent with P&L on sell trades."""
    all_trades = _visible_trades(db, user.id).order_by(models.TradeLog.date, models.TradeLog.created_at).all()

    # Track positions per agent to calculate P&L on sells
    positions: Dict[str, Dict[str, dict]] = {k: {} for k in BUCKETS}
    agent_result = []

    for t in all_trades:
        trade_agent = agent_of(t.trade_type)

        ticker = t.stock.ticker
        qty = t.quantity * 100
        pos = positions[trade_agent]

        pnl = None
        pnl_pct = None

        if t.action == "BUY":
            if ticker not in pos:
                pos[ticker] = {"shares": 0, "avg_price": 0.0}
            total_shares = pos[ticker]["shares"] + qty
            total_cost = pos[ticker]["shares"] * pos[ticker]["avg_price"] + qty * t.price
            pos[ticker]["shares"] = total_shares
            pos[ticker]["avg_price"] = total_cost / total_shares
        elif t.action == "SELL" and ticker in pos and pos[ticker]["avg_price"] > 0:
            avg_buy = pos[ticker]["avg_price"]
            pnl = (t.price - avg_buy) * qty
            pnl_pct = ((t.price - avg_buy) / avg_buy) * 100
            pos[ticker]["shares"] -= qty
            if pos[ticker]["shares"] <= 0:
                del pos[ticker]

        if trade_agent == agent.upper():
            agent_result.append({
                "id": t.id,
                "ticker": ticker,
                "action": t.action,
                "date": str(t.date),
                "price": t.price,
                "quantity": t.quantity,
                "total_value": round(t.price * qty, 2),
                "pnl": round(pnl, 2) if pnl is not None else None,
                "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
                "strategy": t.strategy_id or "MANUAL",
                "notes": t.notes or "",
            })

    # Return most recent first
    return sorted(agent_result, key=lambda x: (x["date"], x["id"]), reverse=True)


@router.get("/{trade_id}")
def get_trade_detail(trade_id: int, db: Session = Depends(get_db),
                     user: CurrentUser = Depends(get_current_user)):
    trade = db.query(models.TradeLog).filter(models.TradeLog.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    # Trade manual milik user lain tidak boleh dilihat (trade AI global = user_id NULL boleh).
    if trade.user_id is not None and trade.user_id != user.id:
        raise HTTPException(status_code=404, detail="Trade not found")

    agent = agent_of(trade.trade_type)

    stock = trade.stock
    ticker = stock.ticker
    qty_shares = trade.quantity * 100

    # Hitung avg_buy_price dan P&L dengan replay trade sebelumnya (di-scope ke user + AI)
    prior_trades = (
        _visible_trades(db, user.id)
        .filter(
            (models.TradeLog.date < trade.date) |
            ((models.TradeLog.date == trade.date) & (models.TradeLog.id <= trade.id))
        )
        .order_by(models.TradeLog.date, models.TradeLog.id)
        .all()
    )

    pos: dict = {}
    pnl = pnl_pct = avg_buy_at_trade = None

    for t in prior_trades:
        t_agent = agent_of(t.trade_type)
        if t_agent != agent:
            continue

        t_ticker = t.stock.ticker
        t_qty = t.quantity * 100

        if t.action == "BUY":
            if t_ticker not in pos:
                pos[t_ticker] = {"shares": 0, "avg_price": 0.0}
            total_shares = pos[t_ticker]["shares"] + t_qty
            total_cost = pos[t_ticker]["shares"] * pos[t_ticker]["avg_price"] + t_qty * t.price
            pos[t_ticker]["shares"] = total_shares
            pos[t_ticker]["avg_price"] = total_cost / total_shares
            if t.id == trade.id:
                avg_buy_at_trade = t.price
        elif t.action == "SELL":
            if t_ticker in pos and pos[t_ticker]["avg_price"] > 0:
                if t.id == trade.id:
                    avg_buy_at_trade = pos[t_ticker]["avg_price"]
                    pnl = (t.price - pos[t_ticker]["avg_price"]) * t_qty
                    pnl_pct = ((t.price - pos[t_ticker]["avg_price"]) / pos[t_ticker]["avg_price"]) * 100
                pos[t_ticker]["shares"] -= t_qty
                if pos[t_ticker]["shares"] <= 0:
                    del pos[t_ticker]

    # OHLCV 90 hari sekitar tanggal trade untuk chart konteks
    from datetime import timedelta
    date_from = trade.date - timedelta(days=90)
    date_to   = trade.date + timedelta(days=14)
    ohlcv_rows = (
        db.query(models.OHLCVDaily)
        .filter(
            models.OHLCVDaily.stock_id == stock.id,
            models.OHLCVDaily.date >= date_from,
            models.OHLCVDaily.date <= date_to,
        )
        .order_by(models.OHLCVDaily.date)
        .all()
    )

    return {
        "id": trade.id,
        "ticker": ticker,
        "name": stock.name,
        "sector": stock.sector or "",
        "agent": agent,
        "action": trade.action,
        "date": str(trade.date),
        "price": trade.price,
        "quantity_lots": trade.quantity,
        "quantity_shares": qty_shares,
        "total_value": round(trade.price * qty_shares, 2),
        "avg_buy_price": round(avg_buy_at_trade, 2) if avg_buy_at_trade else None,
        "pnl": round(pnl, 2) if pnl is not None else None,
        "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
        "strategy": trade.strategy_id or "MANUAL",
        "notes": trade.notes or "",
        "ohlcv": [
            {"date": str(r.date), "open": r.open, "high": r.high,
             "low": r.low, "close": r.close, "volume": r.volume}
            for r in ohlcv_rows
        ],
    }


@router.post("")
def create_trade(req: TradeRequest, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(get_current_user)):
    trade_type_upper = req.trade_type.upper()
    # Trade AI (AUTO_*) tetap global (user_id NULL); trade manual menjadi milik user ini.
    owner_id = None if trade_type_upper in AI_TRADE_TYPES else user.id
    try:
        execute_trade(
            db,
            ticker=req.ticker,
            action=req.action,
            lots=req.quantity,
            trade_type=trade_type_upper,
            price=req.price,
            user_id=owner_id,
            strategy_id=req.strategy_id,
            notes=req.notes or "",
        )
    except TradeError as e:
        raise HTTPException(status_code=e.status, detail=str(e))
    return {"status": "ok"}
