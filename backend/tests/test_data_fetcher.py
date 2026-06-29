import pytest
import pandas as pd
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
import models
from services.data_fetcher import load_idx80, seed_stocks, fetch_ohlcv, save_ohlcv

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

def _mock_df(days=5):
    idx = pd.date_range(end=date.today(), periods=days, freq="D")
    return pd.DataFrame({
        "Open": [9000.0] * days, "High": [9100.0] * days,
        "Low": [8900.0] * days, "Close": [9050.0] * days,
        "Volume": [10_000_000] * days,
    }, index=idx)

def test_load_idx80_returns_80_stocks():
    stocks = load_idx80()
    assert len(stocks) == 80
    assert all("ticker" in s and "name" in s and "sector" in s for s in stocks)

def test_seed_stocks_inserts_all(db):
    seed_stocks(db)
    assert db.query(models.Stock).count() == 80

def test_seed_stocks_idempotent(db):
    seed_stocks(db)
    seed_stocks(db)
    assert db.query(models.Stock).count() == 80

def test_fetch_ohlcv_appends_jk_suffix(mocker):
    mock = mocker.patch("services.data_fetcher.yf.download", return_value=_mock_df())
    fetch_ohlcv("BBCA")
    args, kwargs = mock.call_args
    assert args[0] == "BBCA.JK"

def test_save_ohlcv_persists_rows(db):
    stock = models.Stock(ticker="BBCA", name="Bank Central Asia", sector="Finance", market_cap_cat="large")
    db.add(stock); db.commit()
    count = save_ohlcv(db, stock, _mock_df(days=5))
    assert count == 5
    assert db.query(models.OHLCVDaily).count() == 5

def test_save_ohlcv_skips_duplicates(db):
    stock = models.Stock(ticker="BBCA", name="Bank Central Asia", sector="Finance", market_cap_cat="large")
    db.add(stock); db.commit()
    df = _mock_df(days=5)
    save_ohlcv(db, stock, df)
    count2 = save_ohlcv(db, stock, df)
    assert count2 == 0
    assert db.query(models.OHLCVDaily).count() == 5
