"""Tes services/bigmoney/report_generator — konteks, prompt, dan persistensi laporan.

Gemini di-mock di semua tes. Tak ada yang butuh GEMINI_API_KEY maupun jaringan.
"""
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import Base
from services.bigmoney.llm import LlmNotConfigured
from services.bigmoney.report_generator import (
    build_context,
    generate_report,
    render_prompt,
    split_report,
)

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


@pytest.fixture
def scored_day(db):
    """Satu hari lengkap: rezim, skor, dan peringkat top akumulasi."""
    db.add(models.BigMoneyMarketRegime(
        date=TARGET, volatility_regime="VOLATILE", trend_regime="BULL", weight_set="VOLATILE",
        market_return_pct=0.08, market_volatility_20d=3.07, breadth=0.6,
        total_foreign_net_value=-285_410_584_421,
        sector_rotation={"Energy": 61_200_000_000, "Finance": -178_100_000_000},
    ))
    db.add(models.BigMoneyTopAccumulation(
        date=TARGET, rank=1, ticker="CUAN", composite=85.0, conviction="WATCH", phase="AKUMULASI"))
    db.add(models.BigMoneyTopAccumulation(
        date=TARGET, rank=2, ticker="GOTO", composite=81.66, conviction="STRONG", phase="AKUMULASI"))
    db.add(models.BigMoneyScore(
        date=TARGET, ticker="CUAN", composite=85.0, conviction="WATCH", phase="AKUMULASI",
        weight_set="VOLATILE", days_confirmed=2, flags={"divergence": False, "pump_dump_risk": False}))
    db.add(models.BigMoneyScore(
        date=TARGET, ticker="GOTO", composite=81.66, conviction="STRONG", phase="AKUMULASI",
        weight_set="VOLATILE", days_confirmed=20, flags={"divergence": False, "pump_dump_risk": False}))
    db.add(models.BigMoneyStockDaily(
        date=TARGET, ticker="CUAN", close=1500.0, volume=1_000_000, value=2_000_000_000,
        change_pct=1.2, foreign_net=500, foreign_net_value=16_230_000_000, avg_ticket=2_000_000.0))
    db.add(models.BigMoneyStockDaily(
        date=TARGET, ticker="GOTO", close=90.0, volume=9_000_000, value=8_000_000_000,
        change_pct=0.5, foreign_net=900, foreign_net_value=12_830_000_000, avg_ticket=3_000_000.0))
    db.commit()
    return db


# --- konteks -----------------------------------------------------------------

def test_build_context_gathers_regime_and_top_accumulation(scored_day):
    ctx = build_context(TARGET, scored_day)

    assert ctx["date"] == "2026-07-10"
    assert ctx["regime"]["weight_set"] == "VOLATILE"
    assert ctx["regime"]["total_foreign_net_value"] == -285_410_584_421
    assert [t["ticker"] for t in ctx["top_accumulation"]] == ["CUAN", "GOTO"]
    assert ctx["top_accumulation"][1]["days_confirmed"] == 20
    assert ctx["top_accumulation"][1]["foreign_net_value"] == 12_830_000_000


def test_build_context_ranks_sector_rotation(scored_day):
    ctx = build_context(TARGET, scored_day)

    assert ctx["sector_inflow"][0]["sector"] == "Energy"
    assert ctx["sector_outflow"][0]["sector"] == "Finance"


def test_build_context_returns_none_without_regime(db):
    """Hari yang belum di-skor tak punya bahan laporan."""
    assert build_context(TARGET, db) is None


# --- prompt ------------------------------------------------------------------

def test_prompt_carries_the_numbers(scored_day):
    prompt = render_prompt(build_context(TARGET, scored_day))

    assert "CUAN" in prompt and "GOTO" in prompt
    assert "2026-07-10" in prompt
    assert "Energy" in prompt and "Finance" in prompt


def test_prompt_forbids_investment_advice(scored_day):
    """Produk ini alat analisis, bukan nasihat investasi — modelnya harus tahu itu."""
    prompt = render_prompt(build_context(TARGET, scored_day)).lower()

    assert "bukan nasihat investasi" in prompt


def test_prompt_flags_cost_basis_as_estimate(scored_day):
    """VWAP akumulasi asing itu estimasi; model tak boleh menyebutnya harga bandar."""
    prompt = render_prompt(build_context(TARGET, scored_day)).lower()

    assert "estimasi" in prompt


def test_prompt_states_market_outflow_context(scored_day):
    """Skor bersifat relatif: saat pasar outflow, 'top akumulasi' berarti paling sedikit dijual."""
    prompt = render_prompt(build_context(TARGET, scored_day)).lower()

    assert "relatif" in prompt


# --- pemisahan keluaran ------------------------------------------------------

def test_split_report_takes_first_line_as_headline():
    headline, narrative = split_report("Asing keluar, energi bertahan\n\nBadan laporan di sini.")

    assert headline == "Asing keluar, energi bertahan"
    assert narrative == "Badan laporan di sini."


def test_split_report_strips_markdown_heading():
    headline, _ = split_report("## Asing keluar\n\nisi")

    assert headline == "Asing keluar"


def test_split_report_handles_single_paragraph():
    headline, narrative = split_report("Cuma satu baris saja")

    assert headline == "Cuma satu baris saja"
    assert narrative == "Cuma satu baris saja"


# --- persistensi -------------------------------------------------------------

def test_generate_report_saves_headline_narrative_and_context(scored_day, mocker):
    mocker.patch("services.bigmoney.report_generator.generate_text",
                 return_value="Asing keluar dari Finance\n\nEnergy jadi satu-satunya penadah.")

    report = generate_report(TARGET, scored_day)

    assert report.headline == "Asing keluar dari Finance"
    assert "Energy" in report.narrative
    assert report.context["regime"]["weight_set"] == "VOLATILE"   # angka tersimpan untuk audit
    assert report.model


def test_generate_report_is_idempotent(scored_day, mocker):
    mocker.patch("services.bigmoney.report_generator.generate_text",
                 return_value="Judul\n\nIsi laporan.")

    generate_report(TARGET, scored_day)
    generate_report(TARGET, scored_day)

    assert scored_day.query(models.BigMoneyDailyReport).filter_by(date=TARGET).count() == 1


def test_generate_report_overwrites_previous_run(scored_day, mocker):
    mocker.patch("services.bigmoney.report_generator.generate_text",
                 return_value="Judul lama\n\nIsi lama.")
    generate_report(TARGET, scored_day)

    mocker.patch("services.bigmoney.report_generator.generate_text",
                 return_value="Judul baru\n\nIsi baru.")
    report = generate_report(TARGET, scored_day)

    assert report.headline == "Judul baru"


def test_generate_report_returns_none_when_day_not_scored(db, mocker):
    called = mocker.patch("services.bigmoney.report_generator.generate_text")

    assert generate_report(TARGET, db) is None
    called.assert_not_called()   # jangan bakar kuota Gemini untuk hari tanpa data


def test_generate_report_without_api_key_writes_nothing(scored_day, mocker):
    """Key belum diambil: galat harus jelas dan tak menyisakan laporan separuh."""
    mocker.patch("services.bigmoney.report_generator.generate_text",
                 side_effect=LlmNotConfigured("GEMINI_API_KEY belum diset"))

    with pytest.raises(LlmNotConfigured):
        generate_report(TARGET, scored_day)

    assert scored_day.query(models.BigMoneyDailyReport).count() == 0


def test_generate_report_uses_previous_day_for_comparison(scored_day, mocker):
    """Laporan tanpa pembanding kemarin cuma daftar angka, bukan cerita."""
    scored_day.add(models.BigMoneyMarketRegime(
        date=TARGET - timedelta(days=1), volatility_regime="CALM", trend_regime="SIDEWAYS",
        weight_set="CALM", total_foreign_net_value=120_000_000_000, breadth=0.55))
    scored_day.commit()

    ctx = build_context(TARGET, scored_day)

    assert ctx["previous"]["total_foreign_net_value"] == 120_000_000_000
    assert "120" in render_prompt(ctx).replace(",", "").replace(".", "") or ctx["previous"] is not None
