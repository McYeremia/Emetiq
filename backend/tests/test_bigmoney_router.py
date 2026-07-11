"""Tes routers/bigmoney — endpoint report-only, khusus tier dev.

Fitur ini dev-mode sampai siap rilis, jadi gating tier ikut diuji: bocor ke user
free berarti menyiarkan sinyal setengah matang ke publik.
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import CurrentUser, get_current_user
from database import Base, get_db
import main
import models

TARGET = date(2026, 7, 10)
EARLIER = date(2026, 7, 9)


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Factory = sessionmaker(bind=engine)
    db = Factory()

    for day, weight_set, foreign in ((EARLIER, "CALM", 120_000_000_000),
                                     (TARGET, "VOLATILE", -285_410_584_421)):
        db.add(models.BigMoneyMarketRegime(
            date=day, volatility_regime="VOLATILE" if weight_set == "VOLATILE" else "CALM",
            trend_regime="BULL", weight_set=weight_set, market_return_pct=0.08,
            market_volatility_20d=3.07, breadth=0.6, total_foreign_net_value=foreign,
            sector_rotation={"Energy": 61_200_000_000, "Finance": -178_100_000_000}))

    db.add(models.BigMoneyTopAccumulation(
        date=TARGET, rank=1, ticker="CUAN", composite=85.0, conviction="WATCH", phase="AKUMULASI"))
    db.add(models.BigMoneyTopAccumulation(
        date=TARGET, rank=2, ticker="GOTO", composite=81.66, conviction="STRONG", phase="AKUMULASI"))
    db.add(models.BigMoneyTopAccumulation(
        date=EARLIER, rank=1, ticker="BBCA", composite=70.0, conviction="WATCH", phase="NETRAL"))

    db.add(models.BigMoneyScore(
        date=TARGET, ticker="CUAN", composite=85.0, conviction="WATCH", phase="AKUMULASI",
        weight_set="VOLATILE", days_confirmed=2, s_relative_foreign_flow=99.0,
        s_foreign_persistence=70.0, s_big_ticket=88.0, s_cost_basis=60.0, s_volume_price=55.0,
        flags={"divergence": False, "pump_dump_risk": False}))
    db.add(models.BigMoneyStockDaily(
        date=TARGET, ticker="CUAN", close=1500.0, volume=1_000_000, value=2_000_000_000,
        change_pct=1.2, foreign_net=500, foreign_net_value=16_230_000_000, avg_ticket=2_000_000.0))

    db.add(models.BigMoneyDailyReport(
        date=TARGET, headline="Asing keluar dari Finance",
        narrative="Energy jadi satu-satunya penadah.",
        context={"regime": {"weight_set": "VOLATILE"}}, model="gemini-2.0-flash"))

    db.commit()
    db.close()
    return Factory


@pytest.fixture
def make_client(session_factory):
    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def _make(tier="dev"):
        main.app.dependency_overrides[get_db] = override_db
        main.app.dependency_overrides[get_current_user] = lambda: CurrentUser("u-1", None, tier)
        return TestClient(main.app)

    yield _make
    main.app.dependency_overrides.clear()


# --- gating ------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/bigmoney/regime", "/bigmoney/top-accumulation", "/bigmoney/report/latest"])
def test_non_dev_tier_is_rejected(make_client, path):
    """Dev-mode berarti dev-mode: user pro pun belum boleh melihatnya."""
    assert make_client(tier="pro").get(path).status_code == 403


@pytest.mark.parametrize("path", ["/bigmoney/regime", "/bigmoney/top-accumulation", "/bigmoney/report/latest"])
def test_dev_tier_is_allowed(make_client, path):
    assert make_client(tier="dev").get(path).status_code == 200


# --- regime ------------------------------------------------------------------

def test_regime_returns_latest_by_default(make_client):
    body = make_client().get("/bigmoney/regime").json()

    assert body["date"] == "2026-07-10"
    assert body["weight_set"] == "VOLATILE"
    assert body["total_foreign_net_value"] == -285_410_584_421
    assert body["sector_rotation"]["Energy"] == 61_200_000_000


def test_regime_accepts_explicit_date(make_client):
    body = make_client().get("/bigmoney/regime?date=2026-07-09").json()

    assert body["date"] == "2026-07-09"
    assert body["weight_set"] == "CALM"


def test_regime_unknown_date_returns_404(make_client):
    assert make_client().get("/bigmoney/regime?date=2026-01-01").status_code == 404


# --- top accumulation --------------------------------------------------------

def test_top_accumulation_returns_latest_day_ranked(make_client):
    body = make_client().get("/bigmoney/top-accumulation").json()

    assert body["date"] == "2026-07-10"
    assert [row["ticker"] for row in body["data"]] == ["CUAN", "GOTO"]
    assert body["data"][0]["rank"] == 1
    assert body["data"][0]["conviction"] == "WATCH"


def test_top_accumulation_carries_evidence_for_the_ui(make_client):
    """Halaman report-only harus bisa menunjukkan BUKTI, bukan cuma peringkat."""
    row = make_client().get("/bigmoney/top-accumulation").json()["data"][0]

    assert row["days_confirmed"] == 2
    assert row["foreign_net_value"] == 16_230_000_000
    assert row["subscores"]["relative_foreign_flow"] == 99.0
    assert row["flags"]["pump_dump_risk"] is False


def test_top_accumulation_includes_disclaimer(make_client):
    """Angka asing adalah estimasi; UI tak boleh menampilkannya tanpa peringatan."""
    body = make_client().get("/bigmoney/top-accumulation").json()

    assert "estimasi" in body["disclaimer"].lower()
    assert "bukan nasihat investasi" in body["disclaimer"].lower()


def test_top_accumulation_empty_when_never_scored(make_client, session_factory):
    factory = session_factory()
    factory.query(models.BigMoneyTopAccumulation).delete()
    factory.commit()
    factory.close()

    body = make_client().get("/bigmoney/top-accumulation").json()

    assert body["date"] is None
    assert body["data"] == []


# --- laporan -----------------------------------------------------------------

def test_report_latest_returns_headline_and_narrative(make_client):
    body = make_client().get("/bigmoney/report/latest").json()

    assert body["date"] == "2026-07-10"
    assert body["headline"] == "Asing keluar dari Finance"
    assert "Energy" in body["narrative"]
    assert body["model"] == "gemini-2.0-flash"
    assert "bukan nasihat investasi" in body["disclaimer"].lower()


def test_report_latest_without_report_says_so(make_client, session_factory):
    db = session_factory()
    db.query(models.BigMoneyDailyReport).delete()
    db.commit()
    db.close()

    response = make_client().get("/bigmoney/report/latest")

    assert response.status_code == 200
    assert response.json()["report"] is None   # belum ada laporan bukanlah galat
