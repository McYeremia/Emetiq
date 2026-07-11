"""Tes services/bigmoney/regime — deret pasar, rezim, rotasi sektor.

Deteksi rezim murni diuji tanpa database; persistensi diuji dengan SQLite
in-memory. Tak ada tes yang menyentuh jaringan.
"""
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import Base
from services.bigmoney.regime import compute_regime, detect_regime, market_series

TARGET = date(2026, 7, 10)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _seed(db, d: date, rows: list[dict]):
    for row in rows:
        db.add(models.BigMoneyStockDaily(date=d, **row))
    db.commit()


def _stock(ticker: str, **over) -> dict:
    row = {
        "ticker": ticker,
        "close": 1000.0,
        "volume": 1_000_000,
        "value": 1_000_000_000,
        "change_pct": 0.0,
        "foreign_net": 0,
        "foreign_net_value": 0,
        "avg_ticket": 1_000_000.0,
    }
    row.update(over)
    return row


# --- deteksi rezim (murni) ---------------------------------------------------

def _series(returns: list[float]) -> list[dict]:
    return [
        {"date": TARGET - timedelta(days=len(returns) - i),
         "market_return_pct": r, "breadth": 0.5, "total_foreign_net_value": 0}
        for i, r in enumerate(returns)
    ]


def test_calm_market_when_returns_are_small_and_flat():
    regime = detect_regime(_series([0.1, -0.2, 0.15, 0.05, -0.1] * 4))

    assert regime["volatility_regime"] == "CALM"
    assert regime["trend_regime"] == "SIDEWAYS"
    assert regime["weight_set"] == "CALM"


def test_volatile_market_when_daily_swings_are_wide():
    regime = detect_regime(_series([3.0, -3.5, 2.8, -4.0, 3.2] * 4))

    assert regime["volatility_regime"] == "VOLATILE"
    assert regime["weight_set"] == "VOLATILE"


def test_bull_trend_when_cumulative_return_is_strongly_positive():
    regime = detect_regime(_series([0.5] * 20))

    assert regime["trend_regime"] == "BULL"


def test_bear_market_forces_volatile_weight_set():
    """Pasar turun tapi tenang: bobot tetap harus beralih ke VOLATILE.

    Di pasar beruntun turun, harga masuk lebih menentukan daripada arah aliran —
    itu justru saat cost basis paling berharga.
    """
    regime = detect_regime(_series([-0.6] * 20))

    assert regime["trend_regime"] == "BEAR"
    assert regime["volatility_regime"] == "CALM"
    assert regime["weight_set"] == "VOLATILE"


def test_detect_regime_survives_single_day_series():
    """Hari pertama data: stdev tak terdefinisi, jangan melempar galat."""
    regime = detect_regime(_series([0.4]))

    assert regime["volatility_regime"] in ("CALM", "VOLATILE")
    assert regime["market_volatility_20d"] is None


def test_detect_regime_empty_series_returns_none():
    assert detect_regime([]) is None


# --- deret pasar (DB) --------------------------------------------------------

def test_market_return_is_weighted_by_transaction_value(db):
    """Saham bernilai besar harus menggerakkan indeks lebih kuat daripada saham tipis.

    BESAR: nilai 9e9, naik 2%.  KECIL: nilai 1e9, turun 8%.
    Tertimbang: (9e9*2 + 1e9*-8) / 10e9 = +1,0%.
    """
    _seed(db, TARGET, [
        _stock("BESAR", value=9_000_000_000, change_pct=2.0),
        _stock("KECIL", value=1_000_000_000, change_pct=-8.0),
    ])

    series = market_series(db, TARGET, days=20)

    assert series[-1]["market_return_pct"] == pytest.approx(1.0)


def test_breadth_counts_movers_only(db):
    """Saham yang tak bergerak tak boleh mengencerkan breadth."""
    _seed(db, TARGET, [
        _stock("UP1", change_pct=1.0),
        _stock("UP2", change_pct=2.0),
        _stock("DOWN", change_pct=-1.0),
        _stock("FLAT", change_pct=0.0),
    ])

    series = market_series(db, TARGET, days=20)

    assert series[-1]["breadth"] == pytest.approx(2 / 3)


def test_market_series_excludes_dates_after_target(db):
    """Backfill ulang tanggal lama tak boleh mengintip masa depan."""
    _seed(db, TARGET - timedelta(days=1), [_stock("AAAA", change_pct=1.0)])
    _seed(db, TARGET, [_stock("AAAA", change_pct=2.0)])
    _seed(db, TARGET + timedelta(days=1), [_stock("AAAA", change_pct=9.0)])

    series = market_series(db, TARGET, days=20)

    assert [s["date"] for s in series] == [TARGET - timedelta(days=1), TARGET]


# --- persistensi -------------------------------------------------------------

def test_compute_regime_writes_row_with_sector_rotation(db):
    db.add(models.Stock(ticker="BANK", name="Bank", sector="Finance"))
    db.add(models.Stock(ticker="TAMB", name="Tambang", sector="Mining"))
    db.commit()
    _seed(db, TARGET, [
        _stock("BANK", foreign_net_value=5_000_000_000, change_pct=1.0),
        _stock("TAMB", foreign_net_value=-2_000_000_000, change_pct=-1.0),
        _stock("XXXX", foreign_net_value=1_000_000_000),   # tak ada di tabel stocks
    ])

    regime = compute_regime(TARGET, db)

    assert regime.date == TARGET
    assert regime.total_foreign_net_value == 4_000_000_000
    assert regime.sector_rotation["Finance"] == 5_000_000_000
    assert regime.sector_rotation["Mining"] == -2_000_000_000
    assert "XXXX" not in regime.sector_rotation   # saham tak terpetakan tak mengarang sektor


def test_compute_regime_is_idempotent(db):
    _seed(db, TARGET, [_stock("AAAA", change_pct=1.0)])

    compute_regime(TARGET, db)
    compute_regime(TARGET, db)

    assert db.query(models.BigMoneyMarketRegime).count() == 1


def test_compute_regime_non_trading_day_returns_none(db):
    assert compute_regime(date(2026, 7, 11), db) is None
    assert db.query(models.BigMoneyMarketRegime).count() == 0
