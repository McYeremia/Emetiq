"""Tes services/bigmoney/ingest — upsert, idempotensi, hari non-bursa.

Klien IDX di-mock; tidak ada tes yang menyentuh jaringan.
"""
import json
import os
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import Base
from services.bigmoney.ingest import (
    IngestResult,
    ingest_stock_summary,
    latest_trading_date,
)

TARGET = date(2026, 7, 9)
_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "idx_stock_summary_sample.json")


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="module")
def raw_rows():
    with open(_FIXTURE) as f:
        return json.load(f)["data"]


def _mock_fetch(mocker, rows):
    return mocker.patch("services.bigmoney.ingest.fetch_stock_summary", return_value=rows)


def test_ingest_inserts_all_rows(db, mocker, raw_rows):
    _mock_fetch(mocker, raw_rows)

    result = ingest_stock_summary(TARGET, db)

    assert result == IngestResult(date=TARGET, trading_day=True, inserted=4, updated=0, skipped=0)
    assert db.query(models.BigMoneyStockDaily).count() == 4

    bbca = db.query(models.BigMoneyStockDaily).filter_by(ticker="BBCA").one()
    assert bbca.foreign_net == 5_592_300
    assert bbca.foreign_net_value == 34_386_568_450
    assert bbca.vwap == pytest.approx(6148.913407685539)


def test_ingest_is_idempotent(db, mocker, raw_rows):
    """Jalan dua kali untuk tanggal sama: perbarui, jangan gandakan."""
    _mock_fetch(mocker, raw_rows)

    first = ingest_stock_summary(TARGET, db)
    second = ingest_stock_summary(TARGET, db)

    assert first.inserted == 4 and first.updated == 0
    assert second.inserted == 0 and second.updated == 4
    assert db.query(models.BigMoneyStockDaily).count() == 4


def test_ingest_overwrites_changed_values(db, mocker, raw_rows):
    """Data IDX yang direvisi harus menimpa baris lama."""
    _mock_fetch(mocker, raw_rows)
    ingest_stock_summary(TARGET, db)

    revised = [dict(r) for r in raw_rows]
    bbca = next(r for r in revised if r["StockCode"] == "BBCA")
    bbca["ForeignBuy"] = 200_000_000.0
    _mock_fetch(mocker, revised)

    ingest_stock_summary(TARGET, db)

    row = db.query(models.BigMoneyStockDaily).filter_by(ticker="BBCA").one()
    assert row.foreign_buy == 200_000_000
    assert row.foreign_net == 200_000_000 - 144_284_600


def test_ingest_non_trading_day_writes_nothing(db, mocker):
    """IDX balas nol baris untuk Sabtu — bukan galat, dan tak menulis apa pun."""
    _mock_fetch(mocker, [])

    result = ingest_stock_summary(date(2026, 7, 4), db)

    assert result.trading_day is False
    assert result.inserted == 0
    assert db.query(models.BigMoneyStockDaily).count() == 0


def test_ingest_skips_malformed_rows(db, mocker, raw_rows):
    _mock_fetch(mocker, raw_rows + [{"StockCode": "", "Close": 1.0}])

    result = ingest_stock_summary(TARGET, db)

    assert result.inserted == 4
    assert result.skipped == 1


def test_ingest_stores_all_964_tickers_even_without_stocks_row(db, mocker, raw_rows):
    """Tanpa FK ke stocks: saham yang belum terdaftar tetap tersimpan."""
    assert db.query(models.Stock).count() == 0
    _mock_fetch(mocker, raw_rows)

    ingest_stock_summary(TARGET, db)

    assert db.query(models.BigMoneyStockDaily).count() == 4


def test_latest_trading_date_returns_none_when_empty(db):
    assert latest_trading_date(db) is None


def test_latest_trading_date_returns_max_date(db, mocker, raw_rows):
    _mock_fetch(mocker, raw_rows)
    ingest_stock_summary(date(2026, 7, 8), db)
    ingest_stock_summary(date(2026, 7, 9), db)

    assert latest_trading_date(db) == date(2026, 7, 9)


def test_latest_trading_date_respects_not_after(db, mocker, raw_rows):
    _mock_fetch(mocker, raw_rows)
    ingest_stock_summary(date(2026, 7, 8), db)
    ingest_stock_summary(date(2026, 7, 9), db)

    assert latest_trading_date(db, not_after=date(2026, 7, 8)) == date(2026, 7, 8)


def test_ingest_handles_duplicate_ticker_in_payload(db, mocker, raw_rows):
    """Duplikat ticker dalam satu payload: perbarui, jangan gandakan."""
    revised = [dict(r) for r in raw_rows]
    bbca_original = next(r for r in revised if r["StockCode"] == "BBCA")
    bbca_duplicate = dict(bbca_original)
    bbca_duplicate["ForeignBuy"] = 100_000_000.0
    revised.append(bbca_duplicate)
    _mock_fetch(mocker, revised)

    result = ingest_stock_summary(TARGET, db)

    assert result.inserted == 4
    assert result.updated == 1
    assert result.skipped == 0
    assert db.query(models.BigMoneyStockDaily).count() == 4
    row = db.query(models.BigMoneyStockDaily).filter_by(ticker="BBCA").one()
    assert row.foreign_buy == 100_000_000.0


def test_ingest_refreshes_scraped_at_on_update(db, mocker, raw_rows):
    """scraped_at diperbaharui saat data IDX direvisi."""
    _mock_fetch(mocker, raw_rows)
    ingest_stock_summary(TARGET, db)

    old_time = datetime(2020, 1, 1)
    row = db.query(models.BigMoneyStockDaily).filter_by(ticker="BBCA").one()
    row.scraped_at = old_time
    db.commit()

    revised = [dict(r) for r in raw_rows]
    bbca = next(r for r in revised if r["StockCode"] == "BBCA")
    bbca["ForeignBuy"] = 150_000_000.0
    _mock_fetch(mocker, revised)

    ingest_stock_summary(TARGET, db)

    row = db.query(models.BigMoneyStockDaily).filter_by(ticker="BBCA").one()
    assert row.scraped_at > old_time


def test_ingest_rolls_back_on_commit_failure(db, mocker, raw_rows):
    """Jika commit() gagal, rollback dipanggil dan error dipropagasi."""
    _mock_fetch(mocker, raw_rows)

    mocker.patch.object(db, "commit", side_effect=RuntimeError("boom"))
    rollback_spy = mocker.spy(db, "rollback")

    with pytest.raises(RuntimeError, match="boom"):
        ingest_stock_summary(TARGET, db)

    assert rollback_spy.call_count == 1


def test_weekdays_back_skips_weekend():
    """2026-07-10 Jumat; mundur 3 hari kerja → Rab 8, Kam 9, Jum 10."""
    from scripts.bigmoney_backfill import weekdays_back

    assert weekdays_back(date(2026, 7, 10), 3) == [
        date(2026, 7, 8), date(2026, 7, 9), date(2026, 7, 10),
    ]


def test_weekdays_back_starting_on_saturday():
    """Sabtu 2026-07-11 bukan hari kerja; hasil mundur ke Jumat dan sebelumnya."""
    from scripts.bigmoney_backfill import weekdays_back

    assert weekdays_back(date(2026, 7, 11), 2) == [date(2026, 7, 9), date(2026, 7, 10)]


def test_weekdays_back_returns_ascending_order():
    from scripts.bigmoney_backfill import weekdays_back

    days = weekdays_back(date(2026, 7, 10), 10)
    assert days == [
        date(2026, 6, 29), date(2026, 6, 30),
        date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3),
        date(2026, 7, 6), date(2026, 7, 7), date(2026, 7, 8),
        date(2026, 7, 9), date(2026, 7, 10),
    ]
    assert len(days) == 10


def test_run_backfill_continues_on_failing_date(mocker):
    """Satu tanggal gagal (ValueError) tidak menghentikan backfill; loop lanjut."""
    from scripts.bigmoney_backfill import run_backfill

    # Daftarkan model agar SessionLocal bisa bekerja kalau tidak di-mock sepenuhnya
    mocker.patch("scripts.bigmoney_backfill.Base.metadata.create_all")
    mocker.patch("scripts.bigmoney_backfill.time.sleep")

    # Tiga tanggal: yang tengah gagal dengan ValueError
    dates = [date(2026, 7, 8), date(2026, 7, 9), date(2026, 7, 10)]
    mock_session = mocker.MagicMock()
    mocker.patch("scripts.bigmoney_backfill.SessionLocal", return_value=mock_session)
    mocker.patch("scripts.bigmoney_backfill._already_ingested", return_value=False)
    mocker.patch("scripts.bigmoney_backfill.weekdays_back", return_value=dates)

    # ingest_stock_summary: pertama ok, tengah ValueError, ketiga ok
    def ingest_side_effect(target, db):
        if target == date(2026, 7, 9):
            raise ValueError("bad float")
        return IngestResult(date=target, trading_day=True, inserted=1, updated=0, skipped=0)

    mock_ingest = mocker.patch(
        "scripts.bigmoney_backfill.ingest_stock_summary",
        side_effect=ingest_side_effect
    )

    # Jalankan backfill
    exit_code = run_backfill(3, date(2026, 7, 10), force=False)

    # Validasi:
    # - exit code 1 (karena ada kegagalan)
    assert exit_code == 1
    # - ingest_stock_summary dipanggil 3 kali (semua tanggal, termasuk yang gagal)
    assert mock_ingest.call_count == 3
    # - rollback dipanggil untuk tanggal yang gagal (dan kemungkinan transaksi baca lainnya)
    assert mock_session.rollback.call_count >= 1
    # - close dipanggil untuk cleanup
    mock_session.close.assert_called_once()


def test_run_backfill_with_zero_days_returns_cleanly(mocker):
    """--days 0 tidak menyentuh DB dan langsung return 0."""
    from scripts.bigmoney_backfill import run_backfill

    mocker.patch("scripts.bigmoney_backfill.Base.metadata.create_all")
    mock_ingest = mocker.patch("scripts.bigmoney_backfill.ingest_stock_summary")
    mock_session = mocker.MagicMock()
    mocker.patch("scripts.bigmoney_backfill.SessionLocal", return_value=mock_session)

    exit_code = run_backfill(0, date(2026, 7, 10), force=False)

    # Validasi:
    # - exit code 0 (berhasil, tak ada yang diproses)
    assert exit_code == 0
    # - ingest_stock_summary tidak dipanggil sama sekali
    mock_ingest.assert_not_called()
    # - session ditutup
    mock_session.close.assert_called_once()
