import os
import sys
import yfinance as yf
import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
import models

def fetch_ohlcv(ticker: str, period: str = "5y", start: date = None) -> pd.DataFrame:
    """
    Fetch historical data from Yahoo Finance.
    If `start` is given, fetch from that date onwards (incremental).
    """
    symbol = ticker if ticker.startswith("^") else f"{ticker}.JK"

    try:
        # Redirect stderr untuk suppress pesan "Failed download" dari yfinance
        devnull = open(os.devnull, 'w')
        old_stderr = sys.stderr
        sys.stderr = devnull
        try:
            if start:
                end = datetime.now().date() + timedelta(days=1)
                df = yf.download(symbol, start=str(start), end=str(end), interval="1d", progress=False)
            else:
                df = yf.download(symbol, period=period, interval="1d", progress=False)
        finally:
            sys.stderr = old_stderr
            devnull.close()
        return df
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return pd.DataFrame()

def save_ohlcv(db: Session, stock: models.Stock, df: pd.DataFrame) -> int:
    """
    Save OHLCV data to database, avoiding duplicates.
    """
    if df.empty:
        return 0

    def get_val(val):
        if isinstance(val, pd.Series):
            return float(val.iloc[0])
        return float(val)

    cutoff = date.today() - timedelta(days=5)

    # 1 query untuk semua existing dates — hindari N SELECT queries
    existing_rows = {
        r.date: r
        for r in db.query(models.OHLCVDaily)
        .filter(models.OHLCVDaily.stock_id == stock.id)
        .all()
    }

    count = 0
    for index, row in df.iterrows():
        try:
            d = index.date() if hasattr(index, 'date') else index

            open_  = get_val(row["Open"])
            high   = get_val(row["High"])
            low    = get_val(row["Low"])
            close  = get_val(row["Close"])
            volume = int(get_val(row["Volume"]))
            adj    = get_val(row["Adj Close"]) if "Adj Close" in row else close

            exists = existing_rows.get(d)
            if exists:
                # Upsert untuk 5 hari terakhir — harga bisa berubah jika
                # sebelumnya di-fetch sebelum market close
                if d >= cutoff:
                    exists.open      = open_
                    exists.high      = high
                    exists.low       = low
                    exists.close     = close
                    exists.volume    = volume
                    exists.adj_close = adj
            else:
                new_row = models.OHLCVDaily(
                    stock_id=stock.id, date=d,
                    open=open_, high=high, low=low,
                    close=close, volume=volume, adj_close=adj
                )
                db.add(new_row)
                existing_rows[d] = new_row
                count += 1
        except Exception:
            continue

    db.commit()
    stock.last_updated = datetime.now()
    db.commit()

    return count

def update_stock_fundamentals(db: Session, stock: models.Stock):
    """
    Fetch and update fundamental data for a stock.
    """
    symbol = stock.ticker if stock.ticker.startswith("^") else f"{stock.ticker}.JK"
    try:
        yf_ticker = yf.Ticker(symbol)
        info = yf_ticker.info
        
        stock.market_cap = info.get('marketCap')
        stock.pe_ratio = info.get('trailingPE')
        stock.pbv_ratio = info.get('priceToBook')
        stock.dividend_yield = info.get('dividendYield')
        stock.forward_pe = info.get('forwardPE')
        
        db.commit()
        return True
    except Exception as e:
        print(f"Error fundamental {stock.ticker}: {e}")
        return False

def seed_stocks(db: Session):
    """
    Initial seed for IDX80 if table is empty.
    """
    if db.query(models.Stock).count() > 0:
        return

    # Sederhanakan daftar awal, nanti akan ditambah via bulk script
    initial_stocks = [
        {"ticker": "BBCA", "name": "Bank Central Asia Tbk.", "sector": "Finance"},
        {"ticker": "BBRI", "name": "Bank Rakyat Indonesia (Persero) Tbk.", "sector": "Finance"},
        {"ticker": "TLKM", "name": "Telkom Indonesia (Persero) Tbk.", "sector": "Infrastruktur"},
        {"ticker": "ASII", "name": "Astra International Tbk.", "sector": "Industri"},
    ]
    
    for s in initial_stocks:
        new_stock = models.Stock(
            ticker=s["ticker"],
            name=s["name"],
            sector=s["sector"],
            market_cap_cat="major"
        )
        db.add(new_stock)
    db.commit()
