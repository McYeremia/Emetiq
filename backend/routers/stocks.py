import threading
from datetime import date, timedelta
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func
import yfinance as yf

import models
import services.data_fetcher as fetcher
import services.indicators as ind_svc
from database import get_db

router = APIRouter(prefix="/stocks", tags=["stocks"])

_sync_lock = threading.Lock()
_sync_state: dict = {
    "is_running": False,
    "phase": "",          # "fetch" | "save" | "done" | "error"
    "phase_label": "",
    "total": 0,
    "done": 0,
    "current": "",
    "errors": 0,
    "message": "",
}


@router.get("")
def list_stocks(db: Session = Depends(get_db)):
    stocks = db.query(models.Stock).order_by(models.Stock.ticker).all()

    # Latest OHLCV per stock
    latest_subq = (
        db.query(
            models.OHLCVDaily.stock_id,
            func.max(models.OHLCVDaily.date).label("max_date"),
        )
        .group_by(models.OHLCVDaily.stock_id)
        .subquery()
    )
    latest_rows = (
        db.query(models.OHLCVDaily)
        .join(latest_subq, (models.OHLCVDaily.stock_id == latest_subq.c.stock_id)
              & (models.OHLCVDaily.date == latest_subq.c.max_date))
        .all()
    )
    latest_map = {row.stock_id: row for row in latest_rows}

    # Second-latest OHLCV per stock (for daily change)
    prev_subq = (
        db.query(
            models.OHLCVDaily.stock_id,
            func.max(models.OHLCVDaily.date).label("prev_date"),
        )
        .join(latest_subq, (models.OHLCVDaily.stock_id == latest_subq.c.stock_id)
              & (models.OHLCVDaily.date < latest_subq.c.max_date))
        .group_by(models.OHLCVDaily.stock_id)
        .subquery()
    )
    prev_rows = (
        db.query(models.OHLCVDaily)
        .join(prev_subq, (models.OHLCVDaily.stock_id == prev_subq.c.stock_id)
              & (models.OHLCVDaily.date == prev_subq.c.prev_date))
        .all()
    )
    prev_map = {row.stock_id: row for row in prev_rows}

    result = []
    for stock in stocks:
        latest = latest_map.get(stock.id)
        prev = prev_map.get(stock.id)
        last_price = latest.close if latest else None
        prev_close = prev.close if prev else None
        if last_price and prev_close and prev_close > 0:
            change_pct = round((last_price - prev_close) / prev_close * 100, 2)
        else:
            change_pct = None
        result.append({
            "ticker": stock.ticker,
            "name": stock.name,
            "sector": stock.sector,
            "last_price": last_price,
            "prev_close": prev_close,
            "change_pct": change_pct,
            "last_date": str(latest.date) if latest else None,
            "market_cap": stock.market_cap,
            "pe_ratio": stock.pe_ratio,
            "pbv_ratio": stock.pbv_ratio,
            "dividend_yield": stock.dividend_yield
        })
    return result


# Static paths must come BEFORE parameterized /{ticker} routes
@router.get("/ihsg")
def get_ihsg(db: Session = Depends(get_db)):
    """Returns IHSG composite index latest price and daily change — from local DB."""
    stock = db.query(models.Stock).filter(models.Stock.ticker == "^JKSE").first()
    if stock:
        rows = (
            db.query(models.OHLCVDaily)
            .filter(models.OHLCVDaily.stock_id == stock.id)
            .order_by(desc(models.OHLCVDaily.date))
            .limit(2)
            .all()
        )
        if len(rows) >= 2:
            latest, prev = rows[0], rows[1]
            change     = latest.close - prev.close
            change_pct = (change / prev.close * 100) if prev.close > 0 else 0
            return {
                "price":      round(latest.close, 2),
                "change":     round(change, 2),
                "change_pct": round(change_pct, 2),
                "date":       str(latest.date),
            }

    # Fallback: fetch live from Yahoo Finance if ^JKSE not in DB
    try:
        df = fetcher.fetch_ohlcv("^JKSE", period="5d")
        if df is None or df.empty or len(df) < 2:
            return {"price": None, "change": None, "change_pct": None, "date": None}

        def to_f(val):
            return float(val.iloc[0]) if hasattr(val, "iloc") else float(val)

        latest_close = to_f(df["Close"].iloc[-1])
        prev_close   = to_f(df["Close"].iloc[-2])
        change       = latest_close - prev_close
        change_pct   = (change / prev_close * 100) if prev_close > 0 else 0
        latest_idx   = df.index[-1]
        date_str     = latest_idx.strftime("%Y-%m-%d") if hasattr(latest_idx, "strftime") else str(latest_idx)
        return {
            "price":      round(latest_close, 2),
            "change":     round(change, 2),
            "change_pct": round(change_pct, 2),
            "date":       date_str,
        }
    except Exception:
        return {"price": None, "change": None, "change_pct": None, "date": None}


@router.get("/signals")
def get_ai_signals(db: Session = Depends(get_db)):
    # joinedload menghindari N+1 (dulu tiap s.stock jadi query terpisah — 400+
    # round-trip ke pooler bikin endpoint hang belasan detik).
    signals = (
        db.query(models.Signal)
        .options(joinedload(models.Signal.stock))
        .order_by(desc(models.Signal.created_at))
        .all()
    )
    grouped: dict = {}
    for s in signals:
        ticker = s.stock.ticker
        if ticker not in grouped:
            grouped[ticker] = {
                "ticker": ticker,
                "name": s.stock.name,
                "type": s.type,
                "strategies": [],
                "max_strength": 0,
                "date": s.created_at.strftime("%Y-%m-%d %H:%M"),
                "market_cap": s.stock.market_cap,
            }
        grouped[ticker]["strategies"].append(s.strategy_id)
        if s.strength > grouped[ticker]["max_strength"]:
            grouped[ticker]["max_strength"] = s.strength
    return [
        g for g in sorted(grouped.values(), key=lambda x: x["max_strength"], reverse=True)
        if g["max_strength"] >= 80
    ]


@router.get("/sync-status")
def get_sync_status():
    with _sync_lock:
        return dict(_sync_state)


def _fetch_only(ticker: str, start_date: date | None) -> tuple:
    """Hanya fetch HTTP dari Yahoo Finance — tanpa sentuh DB sama sekali."""
    try:
        if start_date is not None:
            df = fetcher.fetch_ohlcv(ticker, start=start_date)
        else:
            df = fetcher.fetch_ohlcv(ticker, period="5y")
        return ticker, df, None
    except Exception as e:
        return ticker, None, str(e)


def _set_sync(updates: dict):
    with _sync_lock:
        _sync_state.update(updates)


def _do_refresh_all():
    """Sync semua saham — dijalankan di background task dengan session sendiri."""
    from database import SessionLocal
    db = SessionLocal()
    try:
        _set_sync({
            "is_running": True, "phase": "init", "phase_label": "Inisialisasi...",
            "total": 0, "done": 0, "current": "", "errors": 0, "message": "",
        })

        fetcher.seed_stocks(db)
        stocks = db.query(models.Stock).all()
        total = len(stocks)

        latest_map: dict[int, date] = dict(
            db.query(models.OHLCVDaily.stock_id, func.max(models.OHLCVDaily.date))
            .group_by(models.OHLCVDaily.stock_id)
            .all()
        )

        fetch_tasks = []
        for stock in stocks:
            ld = latest_map.get(stock.id)
            start = ld if ld is not None and ld <= date.today() else None
            fetch_tasks.append((stock, start))

        # Fase 1: Fetch HTTP paralel
        _set_sync({"phase": "fetch", "phase_label": "Mengambil data dari Yahoo Finance", "total": total, "done": 0})

        fetched: dict[int, tuple] = {}
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(_fetch_only, stock.ticker, start): stock
                for stock, start in fetch_tasks
            }
            for future in as_completed(futures):
                stock = futures[future]
                _, df, err = future.result()
                fetched[stock.id] = (df, err)
                with _sync_lock:
                    _sync_state["done"] += 1
                    _sync_state["current"] = stock.ticker
                    if err:
                        _sync_state["errors"] += 1

        # Fase 2: Write DB sequential
        _set_sync({"phase": "save", "phase_label": "Menyimpan ke database", "total": total, "done": 0})

        for stock in stocks:
            df, err = fetched.get(stock.id, (None, "fetch not found"))
            with _sync_lock:
                _sync_state["current"] = stock.ticker
            if not err and df is not None and not df.empty:
                try:
                    fetcher.save_ohlcv(db, stock, df)
                except Exception:
                    with _sync_lock:
                        _sync_state["errors"] += 1
            with _sync_lock:
                _sync_state["done"] += 1

        _set_sync({"is_running": False, "phase": "done", "phase_label": "Selesai", "current": "", "message": f"{total} saham diperbarui"})
        print(f"LOG: Background sync selesai — {total} saham diproses.")
    except Exception as e:
        _set_sync({"is_running": False, "phase": "error", "phase_label": "Error", "message": str(e)})
    finally:
        db.close()


@router.post("/refresh")
def refresh_all(background_tasks: BackgroundTasks):
    with _sync_lock:
        if _sync_state["is_running"]:
            return {"status": "already_running", "message": "Sync sedang berjalan"}
    background_tasks.add_task(_do_refresh_all)
    return {"status": "started", "message": "Sync dimulai di background"}


@router.post("/scan")
def trigger_scan(db: Session = Depends(get_db)):
    import services.watcher as watcher
    print("LOG: Triggering AI Market Scan via API...")
    count = watcher.scan_market_signals()
    return {"status": "ok", "message": f"Scan complete. Found {count} signals."}


# Parameterized routes after static ones
@router.post("/{ticker}")
def add_custom_stock(ticker: str, db: Session = Depends(get_db)):
    ticker = ticker.upper()
    existing = db.query(models.Stock).filter(models.Stock.ticker == ticker).first()
    if existing:
        return {"status": "exists", "ticker": ticker}

    try:
        yf_ticker = yf.Ticker(f"{ticker}.JK")
        info = yf_ticker.info

        if not info or 'longName' not in info:
            yf_ticker = yf.Ticker(ticker)
            info = yf_ticker.info

        if not info or 'longName' not in info:
            raise HTTPException(status_code=404, detail="Stock not found on Yahoo Finance")

        new_stock = models.Stock(
            ticker=ticker,
            name=info.get('longName', ticker),
            sector=info.get('sector', 'Unknown'),
            market_cap_cat="custom"
        )
        db.add(new_stock)
        db.commit()
        db.refresh(new_stock)

        df = fetcher.fetch_ohlcv(ticker)
        fetcher.save_ohlcv(db, new_stock, df)

        return {"status": "added", "ticker": ticker, "name": new_stock.name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{ticker}/ohlcv")
def get_ohlcv(
    ticker: str,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    stock = db.query(models.Stock).filter(models.Stock.ticker == ticker.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker.upper()} not found")

    query = db.query(models.OHLCVDaily).filter(models.OHLCVDaily.stock_id == stock.id)
    if from_date:
        query = query.filter(models.OHLCVDaily.date >= from_date)
    if to_date:
        query = query.filter(models.OHLCVDaily.date <= to_date)

    rows = query.order_by(models.OHLCVDaily.date).all()
    return {
        "ticker": stock.ticker,
        "name": stock.name,
        "data": [
            {"date": str(r.date), "open": r.open, "high": r.high,
             "low": r.low, "close": r.close, "volume": r.volume}
            for r in rows
        ],
    }


@router.get("/{ticker}/indicators")
def get_indicators(ticker: str, db: Session = Depends(get_db)):
    stock = db.query(models.Stock).filter(models.Stock.ticker == ticker.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker.upper()} not found")
    return {"ticker": stock.ticker, "indicators": ind_svc.calculate_indicators(db, stock)}


@router.post("/{ticker}/refresh")
def refresh_stock(ticker: str, db: Session = Depends(get_db)):
    stock = db.query(models.Stock).filter(models.Stock.ticker == ticker.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker.upper()} not found")
    try:
        df = fetcher.fetch_ohlcv(stock.ticker)
        count = fetcher.save_ohlcv(db, stock, df)
        return {"ticker": stock.ticker, "status": "ok", "new_rows": count}
    except Exception as e:
        return {"ticker": stock.ticker, "status": "error", "error": str(e)}
