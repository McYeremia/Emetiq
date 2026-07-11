"""Tes services/bigmoney/engine — upsert skor, idempotensi, top akumulasi.

SQLite in-memory; baris bigmoney_stock_daily disemai langsung. Tak ada jaringan.
"""
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import Base
from services.bigmoney.engine import EngineResult, compute_scores

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


def _seed_history(db, tickers: dict[str, dict], days: int = 6):
    """Semai `days` hari bursa berakhir di TARGET. `tickers` = {ticker: override baris}."""
    for offset in range(days - 1, -1, -1):
        day = TARGET - timedelta(days=offset)
        for ticker, over in tickers.items():
            row = {
                "ticker": ticker,
                "date": day,
                "close": 1000.0,
                "volume": 1_000_000,
                "value": 2_000_000_000,
                "change_pct": 0.0,
                "foreign_net": 0,
                "foreign_net_value": 0,
                "avg_ticket": 1_000_000.0,
            }
            row.update(over)
            db.add(models.BigMoneyStockDaily(**row))
    db.commit()


def test_compute_scores_writes_one_row_per_liquid_ticker(db):
    _seed_history(db, {
        "AAAA": {"foreign_net": 500, "foreign_net_value": 5_000_000_000},
        "BBBB": {"foreign_net": -300, "foreign_net_value": -3_000_000_000},
    })

    result = compute_scores(TARGET, db)

    assert isinstance(result, EngineResult)
    assert result.trading_day is True
    assert result.scored == 2
    assert db.query(models.BigMoneyScore).filter_by(date=TARGET).count() == 2

    row = db.query(models.BigMoneyScore).filter_by(ticker="AAAA", date=TARGET).one()
    assert row.composite > 0
    assert row.conviction in ("STRONG", "WATCH", "WEAK")
    assert row.weight_set in ("CALM", "VOLATILE")
    assert row.flags["divergence"] in (True, False)


def test_compute_scores_skips_illiquid_tickers(db):
    _seed_history(db, {
        "LIQD": {"value": 5_000_000_000},
        "TIPS": {"value": 100_000_000},   # median jauh di bawah Rp1 miliar
    })

    result = compute_scores(TARGET, db)

    assert result.scored == 1
    assert {r.ticker for r in db.query(models.BigMoneyScore).all()} == {"LIQD"}


def test_compute_scores_is_idempotent(db):
    _seed_history(db, {"AAAA": {"foreign_net": 500}, "BBBB": {}})

    first = compute_scores(TARGET, db)
    second = compute_scores(TARGET, db)

    assert first.scored == second.scored == 2
    assert db.query(models.BigMoneyScore).filter_by(date=TARGET).count() == 2


def test_recompute_overwrites_stale_score(db):
    """Ingest yang direvisi harus mengubah skor, bukan menyisakan angka lama."""
    _seed_history(db, {"AAAA": {"foreign_net_value": 1_000_000_000}, "BBBB": {}})
    compute_scores(TARGET, db)
    before = db.query(models.BigMoneyScore).filter_by(ticker="AAAA").one().s_relative_foreign_flow

    row = db.query(models.BigMoneyStockDaily).filter_by(ticker="AAAA", date=TARGET).one()
    row.foreign_net_value = -9_000_000_000
    db.commit()

    compute_scores(TARGET, db)
    after = db.query(models.BigMoneyScore).filter_by(ticker="AAAA").one().s_relative_foreign_flow

    assert after < before


def test_compute_scores_writes_regime_row(db):
    _seed_history(db, {"AAAA": {}, "BBBB": {}})

    compute_scores(TARGET, db)

    regime = db.query(models.BigMoneyMarketRegime).filter_by(date=TARGET).one()
    assert regime.weight_set in ("CALM", "VOLATILE")


def test_top_accumulation_ranks_only_strong_and_watch(db):
    _seed_history(db, {
        "GOOD": {"foreign_net": 900, "foreign_net_value": 90_000_000_000, "avg_ticket": 9_000_000.0},
        "MEH": {"foreign_net": -900, "foreign_net_value": -90_000_000_000},
    })

    compute_scores(TARGET, db)

    top = db.query(models.BigMoneyTopAccumulation).filter_by(date=TARGET).order_by(
        models.BigMoneyTopAccumulation.rank).all()

    assert [t.ticker for t in top] == ["GOOD"]      # MEH ber-conviction WEAK
    assert top[0].rank == 1
    assert top[0].conviction in ("STRONG", "WATCH")


def test_top_accumulation_is_rebuilt_not_appended(db):
    """Peringkat harus konsisten dengan skor terakhir — bukan menumpuk sisa jalan sebelumnya."""
    _seed_history(db, {"GOOD": {"foreign_net": 900, "foreign_net_value": 90_000_000_000},
                       "MEH": {"foreign_net": -900, "foreign_net_value": -90_000_000_000}})

    compute_scores(TARGET, db)
    compute_scores(TARGET, db)

    ranks = [t.rank for t in db.query(models.BigMoneyTopAccumulation).filter_by(date=TARGET).all()]
    assert ranks == sorted(set(ranks))   # tak ada peringkat ganda


def test_top_accumulation_capped_at_ten(db):
    _seed_history(db, {
        f"T{i:03d}": {"foreign_net": 100 * i, "foreign_net_value": 1_000_000_000 * i}
        for i in range(1, 26)
    })

    compute_scores(TARGET, db)

    assert db.query(models.BigMoneyTopAccumulation).filter_by(date=TARGET).count() <= 10


def test_compute_scores_non_trading_day_writes_nothing(db):
    _seed_history(db, {"AAAA": {}})

    result = compute_scores(date(2026, 7, 11), db)   # Sabtu, tak ada baris

    assert result.trading_day is False
    assert result.scored == 0
    assert db.query(models.BigMoneyScore).count() == 0
    assert db.query(models.BigMoneyTopAccumulation).count() == 0
