"""Tes services/bigmoney/features — jendela 20 hari bursa → fitur per ticker.

Fungsi murni: tanpa database, tanpa jaringan. Angka dibuat tangan supaya tiap
cabang bisa diperiksa dengan aritmatika kepala.
"""
from datetime import date, timedelta

import pytest

from services.bigmoney.features import build_features

TARGET = date(2026, 7, 10)


def _day(n: int) -> date:
    """n hari bursa sebelum TARGET (akhir pekan diabaikan — tes tak peduli kalender)."""
    return TARGET - timedelta(days=n)


def _row(ticker: str, d: date, **over) -> dict:
    row = {
        "ticker": ticker,
        "date": d,
        "close": 1000.0,
        "volume": 1_000_000,
        "value": 1_000_000_000,
        "avg_ticket": 1_000_000.0,
        "foreign_net": 0,
        "foreign_net_value": 0,
        "change_pct": 0.0,
    }
    row.update(over)
    return row


def test_returns_only_tickers_present_on_target():
    """Saham yang berhenti diperdagangkan sebelum target tak boleh muncul."""
    history = [
        _row("AAAA", _day(1)),
        _row("AAAA", TARGET),
        _row("BBBB", _day(1)),  # tak ada baris di TARGET
    ]

    feats = build_features(history, TARGET)

    assert set(feats) == {"AAAA"}


def test_foreign_net_days_counts_last_five_days_only():
    """Net beli di hari ke-6 tak boleh ikut terhitung."""
    history = [
        _row("AAAA", _day(6), foreign_net=500),   # di luar jendela 5 hari
        _row("AAAA", _day(4), foreign_net=100),
        _row("AAAA", _day(3), foreign_net=-50),
        _row("AAAA", _day(2), foreign_net=100),
        _row("AAAA", _day(1), foreign_net=100),
        _row("AAAA", TARGET, foreign_net=100),
    ]

    feats = build_features(history, TARGET)["AAAA"]

    assert feats["foreign_net_days"] == 4        # hari -4, -2, -1, target
    assert feats["foreign_net_days_sell"] == 1   # hari -3


def test_days_confirmed_counts_consecutive_streak_backwards():
    """Beruntun terputus di hari -2 → hanya target dan -1 yang dihitung."""
    history = [
        _row("AAAA", _day(3), foreign_net=100),
        _row("AAAA", _day(2), foreign_net=-10),  # pemutus
        _row("AAAA", _day(1), foreign_net=100),
        _row("AAAA", TARGET, foreign_net=100),
    ]

    assert build_features(history, TARGET)["AAAA"]["days_confirmed"] == 2


def test_days_confirmed_zero_when_target_is_net_sell():
    history = [
        _row("AAAA", _day(1), foreign_net=100),
        _row("AAAA", TARGET, foreign_net=-100),
    ]

    assert build_features(history, TARGET)["AAAA"]["days_confirmed"] == 0


def test_vol_spike_uses_prior_days_as_baseline():
    """Baseline dari hari-hari SEBELUM target — target tak boleh mencemari pembaginya."""
    history = [
        _row("AAAA", _day(2), volume=1_000_000),
        _row("AAAA", _day(1), volume=3_000_000),
        _row("AAAA", TARGET, volume=8_000_000),
    ]

    feats = build_features(history, TARGET)["AAAA"]

    assert feats["volume_baseline"] == pytest.approx(2_000_000.0)
    assert feats["vol_spike"] == pytest.approx(4.0)


def test_vol_spike_none_when_no_prior_history():
    """Saham yang baru IPO hari itu: tak ada baseline, jangan mengarang angka."""
    feats = build_features([_row("AAAA", TARGET)], TARGET)["AAAA"]

    assert feats["volume_baseline"] is None
    assert feats["vol_spike"] is None


def test_accum_vwap_weighted_by_volume_on_foreign_buy_days_only():
    """VWAP akumulasi hanya dari hari asing net beli; hari net jual diabaikan.

    Hari -2: value 2e9 / volume 2e6.  Hari -1 (net jual): diabaikan.
    Target:  value 6e9 / volume 2e6.
    Gabungan: 8e9 / 4e6 = 2000.
    """
    history = [
        _row("AAAA", _day(2), foreign_net=100, value=2_000_000_000, volume=2_000_000),
        _row("AAAA", _day(1), foreign_net=-100, value=9_000_000_000, volume=1_000_000),
        _row("AAAA", TARGET, foreign_net=100, value=6_000_000_000, volume=2_000_000),
    ]

    feats = build_features(history, TARGET)["AAAA"]

    assert feats["accum_vwap"] == pytest.approx(2000.0)


def test_accum_vwap_none_when_foreign_never_bought():
    """Tanpa hari net beli, tak ada harga akumulasi asing — None, bukan 0."""
    history = [
        _row("AAAA", _day(1), foreign_net=-100),
        _row("AAAA", TARGET, foreign_net=-100),
    ]

    feats = build_features(history, TARGET)["AAAA"]

    assert feats["accum_vwap"] is None
    assert feats["cost_basis_gap"] is None


def test_cost_basis_gap_positive_when_price_below_accum_vwap():
    """Harga 900 vs VWAP akumulasi 1000 → masih 10% di bawah area beli asing."""
    history = [
        _row("AAAA", _day(1), foreign_net=100, value=1_000_000_000, volume=1_000_000),
        _row("AAAA", TARGET, foreign_net=100, value=1_000_000_000, volume=1_000_000, close=900.0),
    ]

    feats = build_features(history, TARGET)["AAAA"]

    assert feats["accum_vwap"] == pytest.approx(1000.0)
    assert feats["cost_basis_gap"] == pytest.approx(0.1)


def test_big_ticket_ratio_against_own_median():
    """Median avg_ticket 1jt, hari ini 3jt → institusi bertiket besar masuk."""
    history = [
        _row("AAAA", _day(3), avg_ticket=800_000.0),
        _row("AAAA", _day(2), avg_ticket=1_000_000.0),
        _row("AAAA", _day(1), avg_ticket=1_200_000.0),
        _row("AAAA", TARGET, avg_ticket=3_000_000.0),
    ]

    feats = build_features(history, TARGET)["AAAA"]

    assert feats["avg_ticket_median"] == pytest.approx(1_000_000.0)
    assert feats["big_ticket_ratio"] == pytest.approx(3.0)


def test_big_ticket_ratio_none_when_avg_ticket_missing():
    """avg_ticket NULL (frequency=0, saham disuspend) → rasio tak terdefinisi."""
    history = [
        _row("AAAA", _day(1), avg_ticket=1_000_000.0),
        _row("AAAA", TARGET, avg_ticket=None),
    ]

    assert build_features(history, TARGET)["AAAA"]["big_ticket_ratio"] is None


def test_volume_price_rewards_high_volume_flat_price():
    """Wyckoff: volume 3x dengan harga diam mengalahkan volume 3x dengan harga lari."""
    quiet = [
        _row("AAAA", _day(1), volume=1_000_000),
        _row("AAAA", TARGET, volume=3_000_000, change_pct=0.0),
    ]
    running = [
        _row("BBBB", _day(1), volume=1_000_000),
        _row("BBBB", TARGET, volume=3_000_000, change_pct=3.0),
    ]

    quiet_score = build_features(quiet, TARGET)["AAAA"]["volume_price"]
    running_score = build_features(running, TARGET)["BBBB"]["volume_price"]

    assert quiet_score == pytest.approx(3.0)
    assert running_score == pytest.approx(0.0)   # harga bergerak 3% → faktor nol
    assert quiet_score > running_score


def test_volume_price_never_negative():
    """Harga melonjak >3% tak boleh menghasilkan skor negatif."""
    history = [
        _row("AAAA", _day(1), volume=1_000_000),
        _row("AAAA", TARGET, volume=3_000_000, change_pct=10.0),
    ]

    assert build_features(history, TARGET)["AAAA"]["volume_price"] == 0.0


def test_high_20d_excludes_target_for_breakout_check():
    """Tertinggi jendela harus dari hari sebelumnya, kalau tidak breakout mustahil terdeteksi."""
    history = [
        _row("AAAA", _day(2), close=1000.0),
        _row("AAAA", _day(1), close=1100.0),
        _row("AAAA", TARGET, close=1200.0),
    ]

    feats = build_features(history, TARGET)["AAAA"]

    assert feats["high_prior"] == pytest.approx(1100.0)
    assert feats["close"] > feats["high_prior"]


def test_value_median_survives_single_row():
    """Universe filter memanggil median ini; satu baris tak boleh melempar galat."""
    feats = build_features([_row("AAAA", TARGET, value=5_000_000_000)], TARGET)["AAAA"]

    assert feats["value_median"] == pytest.approx(5_000_000_000)


def test_raw_metrics_passed_through_for_phase_classification():
    """Fase diklasifikasi dari metrik mentah, jadi mereka harus ikut terbawa."""
    history = [_row("AAAA", TARGET, foreign_net=-500, foreign_net_value=-7_000_000_000,
                    change_pct=-2.5, volume=4_000_000)]

    feats = build_features(history, TARGET)["AAAA"]

    assert feats["ticker"] == "AAAA"
    assert feats["foreign_net"] == -500
    assert feats["foreign_net_value"] == -7_000_000_000
    assert feats["change_pct"] == -2.5
    assert feats["volume"] == 4_000_000
