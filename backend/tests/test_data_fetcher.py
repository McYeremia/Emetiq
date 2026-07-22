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


# ── save_ohlcv: menolak data cacat ───────────────────────────────────────────
#
# 21 Juli 2026: satu fetch buruk menulis NaN ke OHLC 605 saham sementara Volume
# tetap benar — pola khas auto_adjust mengalikan OHLC dengan rasio adjclose yang
# null. `float('nan')` tidak melempar apa pun dan Postgres menerima NaN sebagai
# float sah, jadi `close = Column(..., nullable=False)` pun lolos. Harga di web
# hilang tanpa satu alarm berbunyi.

def _df_nan(days=2):
    df = _mock_df(days)
    for kolom in ["Open", "High", "Low", "Close"]:
        df[kolom] = float("nan")
    return df                                    # Volume sengaja tetap waras


def test_save_ohlcv_menolak_baris_ohlc_nan(db):
    stock = models.Stock(ticker="AALI", name="Astra Agro", sector="Agri", market_cap_cat="large")
    db.add(stock); db.commit()

    count = save_ohlcv(db, stock, _df_nan(days=2))

    assert count == 0
    assert db.query(models.OHLCVDaily).count() == 0


def test_save_ohlcv_tidak_menimpa_harga_baik_dengan_nan(db):
    """Jalur upsert 5-hari-terakhir adalah cara korupsi menyebar: tanpa
    penjagaan, fetch buruk menimpa harga yang sudah benar di DB."""
    stock = models.Stock(ticker="AALI", name="Astra Agro", sector="Agri", market_cap_cat="large")
    db.add(stock); db.commit()
    save_ohlcv(db, stock, _mock_df(days=2))

    save_ohlcv(db, stock, _df_nan(days=2))

    for baris in db.query(models.OHLCVDaily).all():
        assert baris.close == 9050.0


def test_save_ohlcv_menolak_harga_nol(db):
    """Harga nol bukan harga — saham tak pernah ditutup di 0."""
    stock = models.Stock(ticker="AALI", name="Astra Agro", sector="Agri", market_cap_cat="large")
    db.add(stock); db.commit()
    df = _mock_df(days=2)
    df["Close"] = 0.0

    assert save_ohlcv(db, stock, df) == 0
    assert db.query(models.OHLCVDaily).count() == 0
