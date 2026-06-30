"""Tes services/data_fetcher.

Catatan: `load_idx80` sudah dihapus dari produksi — seluruh universe saham kini
di-seed lewat script bulk (scripts/import_all_stocks.py dkk), sementara
`seed_stocks()` hanya mengisi sekumpulan kecil saham awal secara idempotent.
"""
import pytest
import pandas as pd
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
import models
from services.data_fetcher import seed_stocks, fetch_ohlcv, save_ohlcv


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _mock_df(days=5):
    idx = pd.date_range(end=date.today(), periods=days, freq="D")
    return pd.DataFrame({
        "Open": [9000.0] * days, "High": [9100.0] * days,
        "Low": [8900.0] * days, "Close": [9050.0] * days,
        "Volume": [10_000_000] * days,
    }, index=idx)


# ── seed_stocks ──────────────────────────────────────────────────────────────

def test_seed_stocks_inserts_initial_set(db):
    seed_stocks(db)
    tickers = {s.ticker for s in db.query(models.Stock).all()}
    # Sekumpulan inti yang selalu di-seed (boleh bertambah, tak boleh hilang)
    assert {"BBCA", "BBRI", "TLKM", "ASII"} <= tickers


def test_seed_stocks_idempotent(db):
    seed_stocks(db)
    n1 = db.query(models.Stock).count()
    seed_stocks(db)
    n2 = db.query(models.Stock).count()
    assert n1 == n2 and n1 > 0


# ── fetch_ohlcv ──────────────────────────────────────────────────────────────

def test_fetch_ohlcv_appends_jk_suffix(mocker):
    mock = mocker.patch("services.data_fetcher.yf.download", return_value=_mock_df())
    fetch_ohlcv("BBCA")
    args, kwargs = mock.call_args
    assert args[0] == "BBCA.JK"


def test_fetch_ohlcv_keeps_index_symbol(mocker):
    mock = mocker.patch("services.data_fetcher.yf.download", return_value=_mock_df())
    fetch_ohlcv("^JKSE")
    args, kwargs = mock.call_args
    assert args[0] == "^JKSE"            # ticker indeks tidak diberi .JK


# ── save_ohlcv ───────────────────────────────────────────────────────────────

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
