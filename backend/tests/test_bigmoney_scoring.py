"""Tes services/bigmoney/scoring — persentil, bobot, fase, filter, conviction.

Fungsi murni: tanpa database, tanpa jaringan.
"""
from datetime import date

import pytest

from services.bigmoney.scoring import (
    WEIGHTS,
    classify_phase,
    percentile_ranks,
    run_filters,
    score_universe,
    select_universe,
)

TARGET = date(2026, 7, 10)


def _feat(ticker: str, **over) -> dict:
    """Fitur netral: lolos universe, tak memicu satu pun fase atau flag."""
    feat = {
        "ticker": ticker,
        "date": TARGET,
        "close": 1000.0,
        "volume": 1_000_000,
        "value": 2_000_000_000,
        "change_pct": 0.0,
        "foreign_net": 0,
        "foreign_net_value": 0,
        "avg_ticket": 1_000_000.0,
        "foreign_net_days": 0,
        "foreign_net_days_sell": 0,
        "days_confirmed": 0,
        "volume_baseline": 1_000_000.0,
        "vol_spike": 1.0,
        "avg_ticket_median": 1_000_000.0,
        "big_ticket_ratio": 1.0,
        "accum_vwap": None,
        "cost_basis_gap": None,
        "volume_price": 1.0,
        "value_median": 2_000_000_000,
        "high_prior": 1100.0,
    }
    feat.update(over)
    return feat


# --- bobot -------------------------------------------------------------------

def test_weight_sets_each_sum_to_one():
    """Invarian: composite tak akan pernah melebihi 100 kalau bobot berjumlah 1."""
    for weight_set, weights in WEIGHTS.items():
        assert sum(weights.values()) == pytest.approx(1.0), weight_set


def test_volatile_weights_favour_cost_basis_over_flow():
    """Saat pasar volatil, harga masuk lebih menentukan daripada arah aliran dana."""
    assert WEIGHTS["VOLATILE"]["cost_basis"] > WEIGHTS["CALM"]["cost_basis"]
    assert WEIGHTS["VOLATILE"]["relative_foreign_flow"] < WEIGHTS["CALM"]["relative_foreign_flow"]


# --- peringkat persentil -----------------------------------------------------

def test_percentile_ranks_orders_by_value():
    ranks = percentile_ranks({"A": 10.0, "B": 30.0, "C": 20.0})

    assert ranks["B"] > ranks["C"] > ranks["A"]
    assert 0 <= ranks["A"] <= 100 and 0 <= ranks["B"] <= 100


def test_percentile_ranks_single_stock_is_neutral():
    """Universe satu saham: peringkat harus terdefinisi, bukan 0 atau galat pembagian."""
    assert percentile_ranks({"A": 5.0}) == {"A": 50.0}


def test_percentile_ranks_ties_share_the_same_rank():
    ranks = percentile_ranks({"A": 10.0, "B": 10.0, "C": 99.0})

    assert ranks["A"] == ranks["B"]
    assert ranks["C"] > ranks["A"]


def test_percentile_ranks_none_scores_zero():
    """Metrik hilang (mis. cost_basis saham yang asing tak pernah beli) = terburuk, bukan netral."""
    ranks = percentile_ranks({"A": 10.0, "B": None, "C": 20.0})

    assert ranks["B"] == 0.0
    assert ranks["A"] > 0.0


# --- universe ----------------------------------------------------------------

def test_select_universe_drops_illiquid_stocks():
    feats = {
        "LIQD": _feat("LIQD", value_median=2_000_000_000),
        "TIPS": _feat("TIPS", value_median=500_000_000),   # < Rp1 miliar
    }

    assert set(select_universe(feats)) == {"LIQD"}


def test_select_universe_drops_zero_volume_today():
    """Saham disuspend hari ini tak boleh diberi skor meski riwayatnya likuid."""
    feats = {
        "AAAA": _feat("AAAA"),
        "SUSP": _feat("SUSP", volume=0),
    }

    assert set(select_universe(feats)) == {"AAAA"}


# --- klasifikasi fase --------------------------------------------------------

def test_phase_markup_needs_breakout_above_prior_high():
    breakout = _feat("A", foreign_net=500, vol_spike=2.0, change_pct=4.0, close=1200.0, high_prior=1100.0)
    no_breakout = _feat("B", foreign_net=500, vol_spike=2.0, change_pct=4.0, close=1050.0, high_prior=1100.0)

    assert classify_phase(breakout) == "MARKUP"
    assert classify_phase(no_breakout) != "MARKUP"


def test_phase_akumulasi_needs_flat_price_below_accum_vwap():
    feat = _feat("A", foreign_net=100, foreign_net_days=4, change_pct=0.5,
                 close=1000.0, accum_vwap=1050.0)

    assert classify_phase(feat) == "AKUMULASI"


def test_phase_akumulasi_rejected_when_price_ran_above_accum_vwap():
    """Harga sudah 10% di atas area beli asing — itu mengejar, bukan akumulasi."""
    feat = _feat("A", foreign_net=100, foreign_net_days=4, change_pct=0.5,
                 close=1150.0, accum_vwap=1050.0)

    assert classify_phase(feat) == "NETRAL"


def test_phase_distribusi_wins_over_akumulasi_when_both_match():
    """Bias konservatif yang disengaja: sinyal jual menang."""
    feat = _feat("A", foreign_net=-100, foreign_net_days=3, foreign_net_days_sell=3,
                 vol_spike=2.0, change_pct=-0.5, close=1000.0, accum_vwap=1050.0)

    assert classify_phase(feat) == "DISTRIBUSI"


def test_phase_markdown_on_foreign_sell_with_falling_price():
    feat = _feat("A", foreign_net=-800, change_pct=-3.0, vol_spike=1.4)

    assert classify_phase(feat) == "MARKDOWN"


def test_phase_neutral_when_nothing_matches():
    assert classify_phase(_feat("A")) == "NETRAL"


def test_phase_survives_missing_vol_spike():
    """Saham baru IPO: vol_spike None tak boleh melempar TypeError."""
    assert classify_phase(_feat("A", vol_spike=None, foreign_net=500, change_pct=5.0)) in {
        "NETRAL", "MARKUP", "MARKDOWN", "AKUMULASI", "DISTRIBUSI"
    }


# --- filter ------------------------------------------------------------------

def test_pump_dump_risk_on_thin_stock_exploding():
    feat = _feat("A", vol_spike=8.0, change_pct=15.0, value_median=2_000_000_000)

    assert run_filters(feat)["pump_dump_risk"] is True


def test_pump_dump_risk_not_triggered_on_liquid_stock():
    """Volume dan harga meledak, tapi saham tebal — itu bukan gorengan."""
    feat = _feat("A", vol_spike=8.0, change_pct=15.0, value_median=50_000_000_000)

    assert run_filters(feat)["pump_dump_risk"] is False


def test_divergence_when_foreign_buys_but_price_falls():
    feat = _feat("A", foreign_net_value=20_000_000_000, change_pct=-5.0)

    assert run_filters(feat)["divergence"] is True


def test_divergence_when_foreign_sells_but_price_rises():
    feat = _feat("A", foreign_net_value=-20_000_000_000, change_pct=6.0)

    assert run_filters(feat)["divergence"] is True


def test_no_divergence_when_flow_is_trivial():
    """Asing net beli Rp10 juta lalu harga jatuh — itu kebisingan, bukan divergensi."""
    feat = _feat("A", foreign_net_value=10_000_000, change_pct=-5.0)

    assert run_filters(feat)["divergence"] is False


# --- skor akhir --------------------------------------------------------------

def test_score_universe_ranks_best_flow_on_top():
    feats = {
        "WEAK": _feat("WEAK", foreign_net_value=-5_000_000_000),
        "BEST": _feat("BEST", foreign_net_value=50_000_000_000, big_ticket_ratio=3.0,
                      cost_basis_gap=0.1, volume_price=3.0),
        "MID": _feat("MID", foreign_net_value=1_000_000_000),
    }

    scores = score_universe(feats, "CALM")

    assert [s["ticker"] for s in scores][0] == "BEST"
    assert scores[0]["composite"] > scores[-1]["composite"]
    assert scores[0]["weight_set"] == "CALM"


def test_score_universe_emits_all_five_subscores():
    scores = score_universe({"A": _feat("A"), "B": _feat("B")}, "CALM")

    for key in ("s_relative_foreign_flow", "s_foreign_persistence", "s_big_ticket",
                "s_cost_basis", "s_volume_price"):
        assert key in scores[0]


def test_divergence_cuts_composite_by_fifteen_percent():
    clean = _feat("CLEAN", foreign_net_value=20_000_000_000, change_pct=0.0)
    diverging = _feat("DIVG", foreign_net_value=20_000_000_000, change_pct=-5.0)

    scores = {s["ticker"]: s for s in score_universe({"CLEAN": clean, "DIVG": diverging}, "CALM")}

    assert scores["DIVG"]["flags"]["divergence"] is True
    assert scores["DIVG"]["composite"] < scores["CLEAN"]["composite"]


def test_strong_requires_three_confirmed_days():
    """Skor tinggi tapi asing baru masuk sehari: WATCH, bukan STRONG."""
    hot = _feat("HOT", foreign_net_value=99_000_000_000, foreign_net=9_000_000,
                foreign_net_days=1, days_confirmed=1, big_ticket_ratio=5.0,
                cost_basis_gap=0.2, volume_price=5.0, accum_vwap=1050.0)
    filler = _feat("FILL", foreign_net_value=-1_000_000_000)

    scores = {s["ticker"]: s for s in score_universe({"HOT": hot, "FILL": filler}, "CALM")}

    assert scores["HOT"]["composite"] >= 75
    assert scores["HOT"]["conviction"] == "WATCH"


def test_strong_awarded_when_all_conditions_met():
    strong = _feat("STRG", foreign_net_value=99_000_000_000, foreign_net=9_000_000,
                   foreign_net_days=5, days_confirmed=5, big_ticket_ratio=5.0,
                   cost_basis_gap=0.2, volume_price=5.0, change_pct=0.5,
                   close=1000.0, accum_vwap=1050.0)
    filler = _feat("FILL", foreign_net_value=-1_000_000_000)

    scores = {s["ticker"]: s for s in score_universe({"STRG": strong, "FILL": filler}, "CALM")}

    assert scores["STRG"]["phase"] == "AKUMULASI"
    assert scores["STRG"]["conviction"] == "STRONG"


def test_distribution_phase_is_always_weak():
    """Fase jual tak boleh dapat WATCH betapapun tinggi skornya."""
    dist = _feat("DIST", foreign_net_value=80_000_000_000, foreign_net=-100,
                 foreign_net_days_sell=4, vol_spike=2.0, change_pct=-1.0,
                 big_ticket_ratio=5.0, cost_basis_gap=0.3, volume_price=4.0)
    filler = _feat("FILL", foreign_net_value=-9_000_000_000)

    scores = {s["ticker"]: s for s in score_universe({"DIST": dist, "FILL": filler}, "CALM")}

    assert scores["DIST"]["phase"] == "DISTRIBUSI"
    assert scores["DIST"]["conviction"] == "WEAK"


def test_pump_dump_risk_blocks_strong():
    pump = _feat("PUMP", foreign_net_value=99_000_000_000, foreign_net=5_000,
                 foreign_net_days=5, days_confirmed=5, vol_spike=9.0, change_pct=20.0,
                 close=1500.0, high_prior=1100.0, value_median=2_000_000_000,
                 big_ticket_ratio=5.0, cost_basis_gap=0.2, volume_price=5.0)
    filler = _feat("FILL", foreign_net_value=-1_000_000_000)

    scores = {s["ticker"]: s for s in score_universe({"PUMP": pump, "FILL": filler}, "CALM")}

    assert scores["PUMP"]["phase"] == "MARKUP"
    assert scores["PUMP"]["flags"]["pump_dump_risk"] is True
    assert scores["PUMP"]["conviction"] != "STRONG"


def test_score_universe_empty_input_returns_empty():
    assert score_universe({}, "CALM") == []
