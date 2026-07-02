"""Tes AI Porto: execute_trade bersama, gating dev, dan pipeline (Groq di-mock)."""
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
from services.ai_porto import pipeline, data
import services.advisor.groq_client as gc


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Factory = sessionmaker(bind=engine)
    s = Factory()
    for tk, name, close in [("BBRI", "Bank BRI", 4000), ("TLKM", "Telkom", 3000)]:
        stock = models.Stock(ticker=tk, name=name, sector="Finance")
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
    tr = trade_exec.execute_trade(db, ticker="BBRI", action="BUY", lots=5,
                                  trade_type="AUTO_AI", user_id=None)
    assert tr.quantity == 5
    holdings = trade_exec.holdings_for(db, "AI")
    assert holdings["BBRI"]["shares"] == 500


def test_execute_trade_insufficient_funds(db):
    with pytest.raises(trade_exec.TradeRejected):
        # 100000 lot * 4000 * 100 jauh melebihi modal 15jt
        trade_exec.execute_trade(db, ticker="BBRI", action="BUY", lots=100_000,
                                 trade_type="AUTO_AI", user_id=None)


def test_execute_trade_sell_without_holding(db):
    with pytest.raises(trade_exec.TradeRejected):
        trade_exec.execute_trade(db, ticker="BBRI", action="SELL", lots=1,
                                 trade_type="AUTO_AI", user_id=None)


def test_execute_trade_unknown_ticker(db):
    with pytest.raises(trade_exec.StockNotFound):
        trade_exec.execute_trade(db, ticker="ZZZZ", action="BUY", lots=1,
                                 trade_type="AUTO_AI", user_id=None)


# ── pipeline.run_manage (Groq di-mock) ───────────────────────────────────────

def _mock_plan(monkeypatch, plan: dict):
    monkeypatch.setattr(gc, "chat_json", lambda *a, **k: plan)


def test_run_manage_executes_valid_plan(db, monkeypatch):
    _mock_plan(monkeypatch, {"orders": [{"action": "BUY", "ticker": "BBRI", "lots": 5,
                                          "reason": "murah"}], "strategy_note": "value"})
    out = pipeline.run_manage(db, "kelola porto")
    assert len(out["executed"]) == 1
    assert out["skipped"] == []
    assert out["snapshot"]["position_count"] == 1
    # trade tercatat sebagai AUTO_AI global
    assert db.query(models.TradeLog).filter(models.TradeLog.trade_type == "AUTO_AI").count() == 1


def test_run_manage_skips_invalid_order_keeps_valid(db, monkeypatch):
    _mock_plan(monkeypatch, {"orders": [
        {"action": "BUY", "ticker": "BBRI", "lots": 5, "reason": "ok"},
        {"action": "BUY", "ticker": "TLKM", "lots": 100_000, "reason": "kemahalan"},
    ], "strategy_note": ""})
    out = pipeline.run_manage(db, "beli")
    assert len(out["executed"]) == 1
    assert len(out["skipped"]) == 1
    assert out["skipped"][0]["ticker"] == "TLKM"


def test_run_manage_truncates_to_max_orders(db, monkeypatch):
    orders = [{"action": "BUY", "ticker": "BBRI", "lots": 1, "reason": "x"} for _ in range(12)]
    _mock_plan(monkeypatch, {"orders": orders, "strategy_note": ""})
    out = pipeline.run_manage(db, "spam")
    assert len(out["executed"]) == pipeline.MAX_ORDERS


def test_run_manage_unknown_ticker_skipped(db, monkeypatch):
    _mock_plan(monkeypatch, {"orders": [{"action": "BUY", "ticker": "ZZZZ", "lots": 1,
                                         "reason": "?"}], "strategy_note": ""})
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
    _mock_plan(monkeypatch, {"orders": [{"action": "BUY", "ticker": "BBRI", "lots": 2,
                                         "reason": "ok"}], "strategy_note": "note"})
    assert make_client("free").post("/ai-porto/chat", json={"message": "kelola"}).status_code == 403

    r = make_client("dev").post("/ai-porto/chat", json={"message": "kelola"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["executed"]) == 1
    assert body["snapshot"]["position_count"] == 1


def test_trades_portfolio_has_ai_bucket(make_client):
    p = make_client("dev").get("/trades/portfolio").json()
    assert "AI" in p
