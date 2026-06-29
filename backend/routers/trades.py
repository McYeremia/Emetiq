from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import date
from pydantic import BaseModel
import models
from database import get_db

router = APIRouter(prefix="/trades", tags=["trades"])

INITIAL_MODAL = 15_000_000

class TradeRequest(BaseModel):
    ticker: str
    action: str
    quantity: int
    price: Optional[float] = None
    trade_type: str = "MANUAL"
    strategy_id: Optional[str] = "custom"
    notes: Optional[str] = ""


@router.get("/portfolio")
def get_portfolio(db: Session = Depends(get_db)):
    all_trades = db.query(models.TradeLog).order_by(models.TradeLog.date).all()

    raw_portfolios = {"USER": {}, "GEMINI": {}, "CLAUDE": {}}

    for t in all_trades:
        if t.trade_type == "AUTO_GEMINI": p_key = "GEMINI"
        elif t.trade_type == "AUTO_CLAUDE": p_key = "CLAUDE"
        else: p_key = "USER"

        ticker = t.stock.ticker
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

    result = {}
    for key in ["USER", "GEMINI", "CLAUDE"]:
        summary_list = []
        invested = 0.0
        total_realized = 0.0
        total_unrealized = 0.0

        for ticker, data in raw_portfolios[key].items():
            total_realized += data["realized_pnl"]

            if data["shares"] > 0:
                stock = db.query(models.Stock).filter(models.Stock.ticker == ticker).first()
                latest = db.query(models.OHLCVDaily).filter(models.OHLCVDaily.stock_id == stock.id).order_by(desc(models.OHLCVDaily.date)).first()
                curr_price = latest.close if latest else data["avg_price"]
                last_date = str(latest.date) if latest else None

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
def get_portfolio_growth(db: Session = Depends(get_db)):
    """Returns equity curve snapshots per agent for growth chart."""
    all_trades = db.query(models.TradeLog).order_by(models.TradeLog.date).all()
    result = {}

    for agent_key in ["USER", "GEMINI", "CLAUDE"]:
        positions: Dict[str, dict] = {}
        cash = float(INITIAL_MODAL)
        date_values: Dict[str, float] = {}

        for t in all_trades:
            if t.trade_type == "AUTO_GEMINI": trade_agent = "GEMINI"
            elif t.trade_type == "AUTO_CLAUDE": trade_agent = "CLAUDE"
            else: trade_agent = "USER"

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
                    closest = (
                        db.query(models.OHLCVDaily)
                        .filter(models.OHLCVDaily.stock_id == pos["stock_id"])
                        .filter(models.OHLCVDaily.date <= t.date)
                        .order_by(desc(models.OHLCVDaily.date))
                        .first()
                    )
                    price = closest.close if closest else pos["avg_price"]
                    holdings_value += pos["shares"] * price

            date_str = str(t.date)
            date_values[date_str] = round(cash + holdings_value, 0)

        result[agent_key] = [
            {"date": d, "value": v}
            for d, v in sorted(date_values.items())
        ]

    return result


@router.get("/history")
def get_trade_history(agent: str = "USER", db: Session = Depends(get_db)):
    """Returns all trade logs for a given agent with P&L on sell trades."""
    all_trades = db.query(models.TradeLog).order_by(models.TradeLog.date, models.TradeLog.created_at).all()

    # Track positions per agent to calculate P&L on sells
    positions: Dict[str, Dict[str, dict]] = {"USER": {}, "GEMINI": {}, "CLAUDE": {}}
    agent_result = []

    for t in all_trades:
        if t.trade_type == "AUTO_GEMINI": trade_agent = "GEMINI"
        elif t.trade_type == "AUTO_CLAUDE": trade_agent = "CLAUDE"
        else: trade_agent = "USER"

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
def get_trade_detail(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(models.TradeLog).filter(models.TradeLog.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    if trade.trade_type == "AUTO_GEMINI": agent = "GEMINI"
    elif trade.trade_type == "AUTO_CLAUDE": agent = "CLAUDE"
    else: agent = "USER"

    stock = trade.stock
    ticker = stock.ticker
    qty_shares = trade.quantity * 100

    # Hitung avg_buy_price dan P&L dengan replay semua trade sebelumnya
    prior_trades = (
        db.query(models.TradeLog)
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
        if t.trade_type == "AUTO_GEMINI": t_agent = "GEMINI"
        elif t.trade_type == "AUTO_CLAUDE": t_agent = "CLAUDE"
        else: t_agent = "USER"
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
def create_trade(req: TradeRequest, db: Session = Depends(get_db)):
    stock = db.query(models.Stock).filter(models.Stock.ticker == req.ticker.upper()).first()
    if not stock: raise HTTPException(status_code=404, detail="Stock not found")

    price = req.price or 0
    if price == 0:
        latest = db.query(models.OHLCVDaily).filter(models.OHLCVDaily.stock_id == stock.id).order_by(desc(models.OHLCVDaily.date)).first()
        price = latest.close if latest else 0

    # Determine agent from trade_type
    trade_type_upper = req.trade_type.upper()
    if "CLAUDE" in trade_type_upper:
        agent_key = "CLAUDE"
    elif "GEMINI" in trade_type_upper:
        agent_key = "GEMINI"
    else:
        agent_key = "USER"

    if req.action.upper() == "SELL":
        # Replay trades to check holdings
        all_prev = db.query(models.TradeLog).order_by(models.TradeLog.date).all()
        holdings: dict = {}
        for t in all_prev:
            t_type = t.trade_type.upper()
            if "CLAUDE" in t_type:
                t_agent = "CLAUDE"
            elif "GEMINI" in t_type:
                t_agent = "GEMINI"
            else:
                t_agent = "USER"
            if t_agent != agent_key:
                continue
            tk = t.stock.ticker
            if tk not in holdings:
                holdings[tk] = {"shares": 0, "avg_price": 0.0}
            qty = t.quantity * 100
            if t.action == "BUY":
                total = holdings[tk]["shares"] * holdings[tk]["avg_price"] + qty * t.price
                holdings[tk]["shares"] += qty
                holdings[tk]["avg_price"] = total / holdings[tk]["shares"] if holdings[tk]["shares"] > 0 else 0.0
            else:
                holdings[tk]["shares"] -= qty
        held = holdings.get(req.ticker.upper(), {}).get("shares", 0)
        needed = req.quantity * 100
        if held < needed:
            raise HTTPException(status_code=400, detail=f"Insufficient position: hold {held // 100} lots, need {req.quantity} lots.")

    elif req.action.upper() == "BUY":
        all_prev = db.query(models.TradeLog).order_by(models.TradeLog.date).all()
        holdings_buy: dict = {}
        for t in all_prev:
            t_type = t.trade_type.upper()
            if "CLAUDE" in t_type:
                t_agent = "CLAUDE"
            elif "GEMINI" in t_type:
                t_agent = "GEMINI"
            else:
                t_agent = "USER"
            if t_agent != agent_key:
                continue
            tk = t.stock.ticker
            if tk not in holdings_buy:
                holdings_buy[tk] = {"shares": 0, "avg_price": 0.0, "realized": 0.0}
            qty = t.quantity * 100
            if t.action == "BUY":
                total = holdings_buy[tk]["shares"] * holdings_buy[tk]["avg_price"] + qty * t.price
                holdings_buy[tk]["shares"] += qty
                holdings_buy[tk]["avg_price"] = total / holdings_buy[tk]["shares"] if holdings_buy[tk]["shares"] > 0 else 0.0
            else:
                holdings_buy[tk]["realized"] += (t.price - holdings_buy[tk]["avg_price"]) * qty
                holdings_buy[tk]["shares"] -= qty
        invested = sum(pos["shares"] * pos["avg_price"] for pos in holdings_buy.values() if pos["shares"] > 0)
        realized = sum(pos["realized"] for pos in holdings_buy.values())
        available_cash = INITIAL_MODAL - invested + realized
        trade_cost = price * req.quantity * 100
        if trade_cost > available_cash:
            raise HTTPException(status_code=400, detail=f"Insufficient funds: need Rp {trade_cost:,.0f}, available Rp {available_cash:,.0f}.")

    new_trade = models.TradeLog(
        stock_id=stock.id, action=req.action.upper(), date=date.today(),
        price=price, quantity=req.quantity, trade_type=req.trade_type.upper(),
        strategy_id=req.strategy_id, notes=req.notes
    )
    db.add(new_trade)
    db.commit()
    return {"status": "ok"}
