"""Tes AI Porto v2: execute_trade bersama, risiko adaptif, gating dev, pipeline (Groq mock)."""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import CurrentUser, get_current_user
from database import Base, get_db
import models
import main
from services import trade_exec
from services.ai_porto import pipeline, data, risk, scoring, config
import services.advisor.groq_client as gc


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Factory = sessionmaker(bind=engine)
    s = Factory()
    seed = [("BBRI", 4000), ("TLKM", 3000)] + [(f"T{i:02d}", 1000) for i in range(10)]
    for tk, close in seed:
        stock = models.Stock(ticker=tk, name=tk, sector="Finance")
        s.add(stock); s.flush()
        s.add(models.OHLCVDaily(stock_id=stock.id, date=date(2026, 1, 1),
                                open=close, high=close, low=close, close=close, volume=1000))
    s.commit(); s.close()
    return Factory


@pytest.fixture
def db(session_factory):
    session = session_factory()
    yield session
    session.close()


# ── execute_trade (helper bersama) ───────────────────────────────────────────

def test_execute_trade_buy_success(db):
    trade_exec.execute_trade(db, ticker="BBRI", action="BUY", lots=5, trade_type="AUTO_AI", user_id=None)
    assert trade_exec.holdings_for(db, "AI")["BBRI"]["shares"] == 500


def test_execute_trade_insufficient_funds(db):
    with pytest.raises(trade_exec.TradeRejected):
        trade_exec.execute_trade(db, ticker="BBRI", action="BUY", lots=100_000, trade_type="AUTO_AI", user_id=None)


def test_execute_trade_sell_without_holding(db):
    with pytest.raises(trade_exec.TradeRejected):
        trade_exec.execute_trade(db, ticker="BBRI", action="SELL", lots=1, trade_type="AUTO_AI", user_id=None)


def test_execute_trade_unknown_ticker(db):
    with pytest.raises(trade_exec.StockNotFound):
        trade_exec.execute_trade(db, ticker="ZZZZ", action="BUY", lots=1, trade_type="AUTO_AI", user_id=None)


# ── risiko adaptif ───────────────────────────────────────────────────────────

def test_compute_regime_aggressive():
    assert risk.compute_regime(17_000_000, 17_000_000) == "AGGRESSIVE"


def test_compute_regime_defensive_by_return():
    assert risk.compute_regime(14_500_000, 15_000_000) == "DEFENSIVE"


def test_compute_regime_defensive_by_drawdown():
    # cuan tipis tapi turun >10% dari puncak -> lindungi (defensif)
    assert risk.compute_regime(15_500_000, 17_500_000) == "DEFENSIVE"


def test_compute_regime_normal():
    assert risk.compute_regime(15_500_000, 15_500_000) == "NORMAL"


def test_auto_exit_orders_tp_cl():
    state = {"holdings": [
        {"ticker": "AAA", "unrealized_pct": 25.0, "lots": 3},   # >= +15% TP
        {"ticker": "BBB", "unrealized_pct": -12.0, "lots": 2},  # <= -8% CL
        {"ticker": "CCC", "unrealized_pct": 5.0, "lots": 1},    # aman
    ]}
    orders = risk.auto_exit_orders(state, config.REGIMES["NORMAL"])
    tickers = {o["ticker"] for o in orders}
    assert tickers == {"AAA", "BBB"}


def test_score_candidate_ranks_strong_higher():
    strong = scoring.score_candidate({"signal_strength": 90, "trend": "up", "rsi": 50, "pe": 10, "dividend_yield": 4})
    weak = scoring.score_candidate({"trend": "down", "rsi": 80})
    assert 0 <= weak < strong <= 100


# ── pipeline.run_manage (Groq di-mock) ───────────────────────────────────────

def _mock_plan(monkeypatch, plan: dict):
    monkeypatch.setattr(gc, "chat_json", lambda *a, **k: plan)


def test_run_manage_executes_within_guardrail(db, monkeypatch):
    _mock_plan(monkeypatch, {"orders": [{"action": "BUY", "ticker": "BBRI", "lots": 5, "reason": "ok"}],
                             "strategy_note": "value"})
    out = pipeline.run_manage(db, "kelola")
    assert out["regime"] == "NORMAL"
    assert len(out["executed"]) == 1
    assert out["executed"][0]["lots"] == 5
    assert out["snapshot"]["position_count"] == 1


def test_run_manage_clamps_oversized_buy(db, monkeypatch):
    # 100000 lot BBRI dipangkas ke plafon posisi rezim NORMAL (22% dari 15jt / (4000*100) = 8 lot)
    _mock_plan(monkeypatch, {"orders": [{"action": "BUY", "ticker": "BBRI", "lots": 100_000, "reason": "serakah"}],
                             "strategy_note": ""})
    out = pipeline.run_manage(db, "beli maksimal")
    assert len(out["executed"]) == 1
    assert out["executed"][0]["lots"] == 8
    assert out["skipped"] == []


def test_run_manage_enforces_max_positions(db, monkeypatch):
    orders = [{"action": "BUY", "ticker": f"T{i:02d}", "lots": 1, "reason": "x"} for i in range(10)]
    _mock_plan(monkeypatch, {"orders": orders, "strategy_note": ""})
    out = pipeline.run_manage(db, "diversifikasi")
    # NORMAL: maks 8 posisi -> sisanya ditolak
    assert len(out["executed"]) == config.REGIMES["NORMAL"]["max_positions"]
    assert all("posisi" in s["reason"] for s in out["skipped"])


def test_run_manage_unknown_ticker_skipped(db, monkeypatch):
    _mock_plan(monkeypatch, {"orders": [{"action": "BUY", "ticker": "ZZZZ", "lots": 1, "reason": "?"}],
                             "strategy_note": ""})
    out = pipeline.run_manage(db, "beli")
    assert out["executed"] == []
    assert len(out["skipped"]) == 1


# ── gating tier + endpoint ───────────────────────────────────────────────────

@pytest.fixture
def make_client(session_factory):
    def override_db():
        d = session_factory()
        try:
            yield d
        finally:
            d.close()

    def _make(tier):
        main.app.dependency_overrides[get_db] = override_db
        main.app.dependency_overrides[get_current_user] = lambda: CurrentUser("dev-1", None, tier)
        return TestClient(main.app)

    yield _make
    main.app.dependency_overrides.clear()


def test_ai_porto_requires_dev(make_client):
    assert make_client("free").get("/ai-porto/portfolio").status_code == 403
    assert make_client("dev").get("/ai-porto/portfolio").status_code == 200


def test_ai_porto_chat_dev_only(make_client, monkeypatch):
    _mock_plan(monkeypatch, {"orders": [{"action": "BUY", "ticker": "BBRI", "lots": 2, "reason": "ok"}],
                             "strategy_note": "note"})
    assert make_client("free").post("/ai-porto/chat", json={"message": "kelola"}).status_code == 403
    r = make_client("dev").post("/ai-porto/chat", json={"message": "kelola"})
    assert r.status_code == 200
    body = r.json()
    assert body["regime"] == "NORMAL"
    assert len(body["executed"]) == 1


def test_trades_portfolio_has_ai_bucket(make_client):
    assert "AI" in make_client("dev").get("/trades/portfolio").json()
