"""Tes services/bigmoney/transform — pemetaan field IDX + metrik turunan.

Angka harapan dihitung dari respons IDX GetStockSummary asli tanggal 2026-07-09.
Tidak ada I/O jaringan.
"""
import json
import os
from datetime import date

import pytest

from services.bigmoney.transform import to_row

TARGET = date(2026, 7, 9)
_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "idx_stock_summary_sample.json")


@pytest.fixture(scope="module")
def raw_rows():
    with open(_FIXTURE) as f:
        return {r["StockCode"]: r for r in json.load(f)["data"]}


def test_bbca_derived_metrics(raw_rows):
    """Saham likuid dengan asing net beli — semua turunan terdefinisi."""
    row = to_row(raw_rows["BBCA"], TARGET)

    assert row["ticker"] == "BBCA"
    assert row["date"] == TARGET
    assert row["volume"] == 181_155_800
    assert row["value"] == 1_113_911_327_500
    assert row["foreign_net"] == 5_592_300

    assert row["vwap"] == pytest.approx(6148.913407685539)
    assert row["foreign_net_value"] == 34_386_568_450
    assert row["avg_ticket"] == pytest.approx(39_988_201.01593912)
    assert row["foreign_participation"] == pytest.approx(0.8119019650488696)
    assert row["change_pct"] == pytest.approx(0.4048582995951417)


def test_aadi_foreign_net_sell(raw_rows):
    """Asing net jual — foreign_net dan foreign_net_value negatif."""
    row = to_row(raw_rows["AADI"], TARGET)

    assert row["foreign_net"] == -2_822_600
    assert row["foreign_net_value"] == -22_865_378_110
    assert row["vwap"] == pytest.approx(8100.821267538578)
    assert row["change_pct"] == pytest.approx(-0.30864197530864196)


def test_suspended_stock_yields_null_not_zero(raw_rows):
    """volume=0 dan frequency=0: turunan berpembagi harus None, bukan 0.

    Nol akan menarik turun AVG() dan merusak peringkat di engine; NULL diabaikan
    fungsi agregat SQL. 13,7% baris IDX terkena kasus ini.
    """
    row = to_row(raw_rows["ABBA"], TARGET)

    assert row is not None, "baris disuspend tetap disimpan"
    assert row["ticker"] == "ABBA"
    assert row["volume"] == 0
    assert row["vwap"] is None
    assert row["avg_ticket"] is None
    assert row["foreign_participation"] is None
    assert row["foreign_net_value"] is None
    assert row["foreign_net"] == 0        # selalu terdefinisi
    assert row["change_pct"] == 0.0       # prev_close=30 valid, harga tak berubah


def test_zero_foreign_activity_yields_zero_not_null(raw_rows):
    """Ada volume tapi asing tidak bertransaksi: nol yang sah, bukan None."""
    row = to_row(raw_rows["ABDA"], TARGET)

    assert row["vwap"] == pytest.approx(3425.0)
    assert row["foreign_net"] == 0
    assert row["foreign_net_value"] == 0
    assert row["foreign_participation"] == 0.0
    assert row["avg_ticket"] == pytest.approx(513_750.0)


def test_missing_stock_code_returns_none():
    assert to_row({"StockCode": "", "Close": 100.0}, TARGET) is None
    assert to_row({"Close": 100.0}, TARGET) is None


def test_zero_prev_close_yields_null_change_pct():
    raw = {"StockCode": "NEWX", "Previous": 0.0, "Close": 250.0,
           "Volume": 1000.0, "Value": 250000.0, "Frequency": 2.0,
           "ForeignBuy": 0.0, "ForeignSell": 0.0}
    assert to_row(raw, TARGET)["change_pct"] is None


def test_ticker_is_normalised():
    raw = {"StockCode": " bbca ", "Previous": 1.0, "Close": 1.0,
           "Volume": 0.0, "Value": 0.0, "Frequency": 0.0,
           "ForeignBuy": 0.0, "ForeignSell": 0.0}
    assert to_row(raw, TARGET)["ticker"] == "BBCA"


def test_row_keys_match_model_columns(raw_rows):
    """Dict harus bisa langsung dipakai models.BigMoneyStockDaily(**row)."""
    import models
    row = to_row(raw_rows["BBCA"], TARGET)
    model_cols = {c.name for c in models.BigMoneyStockDaily.__table__.columns}
    assert set(row) <= model_cols
    assert "id" not in row and "scraped_at" not in row
