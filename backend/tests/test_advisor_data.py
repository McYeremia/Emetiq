"""Tes deterministik untuk services/advisor/data_provider.py (TANPA LLM).

Menjamin akurasi angka: filter screening, perhitungan analisa, dan agregasi
portofolio harus benar sebelum LLM menalar di atasnya.
"""
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
import models
from services.advisor import data_provider as dp


def _add_stock(s, ticker, name, sector, pe, pbv, div, mcap):
    st = models.Stock(ticker=ticker, name=name, sector=sector,
                      pe_ratio=pe, pbv_ratio=pbv, dividend_yield=div, market_cap=mcap)
    s.add(st)
    s.flush()
    return st


def _add_series(s, stock, start, step, n=60):
    d0 = date(2026, 1, 1)
    for i in range(n):
        price = start + step * i
        s.add(models.OHLCVDaily(
            stock_id=stock.id, date=d0 + timedelta(days=i),
            open=price, high=price * 1.01, low=price * 0.99, close=price, volume=1_000_000,
        ))


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()

    bbri = _add_stock(s, "BBRI", "Bank BRI", "Finance", pe=9.0, pbv=2.0, div=4.0, mcap=800_000_000_000_000)
    tlkm = _add_stock(s, "TLKM", "Telkom", "Telco", pe=18.0, pbv=3.0, div=5.0, mcap=400_000_000_000_000)
    goto = _add_stock(s, "GOTO", "GoTo", "Tech", pe=None, pbv=2.0, div=0.0, mcap=100_000_000_000_000)

    _add_series(s, bbri, start=4000, step=10)    # uptrend
    _add_series(s, tlkm, start=5000, step=-10)    # downtrend
    _add_series(s, goto, start=100, step=1)       # uptrend
    s.commit()
    yield s
    s.close()


# ── Screening ────────────────────────────────────────────────────────────────

def test_screen_pe_filter(db):
    res = dp.screen(db, pe_max=10)
    tickers = {r["ticker"] for r in res}
    assert tickers == {"BBRI"}              # TLKM pe=18 keluar, GOTO pe=None keluar


def test_screen_dividend_filter(db):
    res = dp.screen(db, div_min=4.5)
    tickers = {r["ticker"] for r in res}
    assert tickers == {"TLKM"}              # hanya TLKM div>=4.5


def test_screen_sector_filter(db):
    res = dp.screen(db, sector="Tech")
    assert [r["ticker"] for r in res] == ["GOTO"]


def test_screen_trend_filter(db):
    res = dp.screen(db, trend="up")
    tickers = {r["ticker"] for r in res}
    assert "BBRI" in tickers and "GOTO" in tickers
    assert "TLKM" not in tickers            # downtrend tersaring


def test_screen_empty_when_impossible(db):
    assert dp.screen(db, pe_max=1) == []    # tak ada yang PE<=1


# ── Analisa 1 saham ──────────────────────────────────────────────────────────

def test_analyze_found_numbers(db):
    a = dp.analyze(db, "bbri")              # case-insensitive
    assert a["found"] is True
    assert a["ticker"] == "BBRI"
    assert a["last_price"] == 4590          # 4000 + 10*59
    assert a["fundamentals"]["pe"] == 9.0
    assert a["indicators"]["RSI_14"] is not None
    assert a["trend"] == "up"


def test_analyze_not_found(db):
    a = dp.analyze(db, "ZZZZ")
    assert a["found"] is False


# ── Portofolio ───────────────────────────────────────────────────────────────

def test_portfolio_aggregation(db):
    bbri = db.query(models.Stock).filter_by(ticker="BBRI").first()
    db.add(models.TradeLog(stock_id=bbri.id, action="BUY", date=date(2026, 2, 1),
                           price=4000, quantity=5, trade_type="MANUAL", user_id="u1"))
    db.add(models.TradeLog(stock_id=bbri.id, action="BUY", date=date(2026, 2, 2),
                           price=4200, quantity=5, trade_type="MANUAL", user_id="u1"))
    db.commit()

    p = dp.portfolio(db, "u1")
    assert p["position_count"] == 1
    h = p["holdings"][0]
    assert h["ticker"] == "BBRI"
    assert h["shares"] == 1000
    assert h["avg_price"] == 4100.0         # (5*100*4000 + 5*100*4200) / 1000
    assert p["invested"] == 4_100_000.0
    assert p["cash"] == 10_900_000.0        # 15jt - 4.1jt + 0 realized
    # current close 4590 -> unrealized (4590-4100)*1000 = 490_000
    assert h["unrealized_pnl"] == 490_000.0


def test_portfolio_excludes_bot_trades(db):
    bbri = db.query(models.Stock).filter_by(ticker="BBRI").first()
    db.add(models.TradeLog(stock_id=bbri.id, action="BUY", date=date(2026, 2, 1),
                           price=4000, quantity=5, trade_type="AUTO_GEMINI"))
    db.commit()
    p = dp.portfolio(db, "u1")
    assert p["position_count"] == 0          # trade bot tidak masuk portofolio user
