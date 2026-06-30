"""Tes integrasi endpoint POST /advisor/chat (Groq di-mock, DB in-memory)."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
import models
import main
import routers.advisor as advisor_ep
from services.advisor import groq_client
from services.advisor.auth import AdvisorUser


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Factory = sessionmaker(bind=engine)
    s = Factory()
    bbri = models.Stock(ticker="BBRI", name="Bank BRI", sector="Finance",
                        pe_ratio=9.0, pbv_ratio=2.0, dividend_yield=4.0, market_cap=8 * 10**14)
    s.add(bbri); s.flush()
    d0 = date(2026, 1, 1)
    for i in range(60):
        p = 4000 + 10 * i
        s.add(models.OHLCVDaily(stock_id=bbri.id, date=d0 + timedelta(days=i),
                                open=p, high=p * 1.01, low=p * 0.99, close=p, volume=1_000_000))
    s.commit(); s.close()
    return Factory


@pytest.fixture
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()
    main.app.dependency_overrides[get_db] = override_get_db
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def _install_groq(monkeypatch, router_payload):
    payloads = {
        "router niat":     router_payload,
        "tim spesialis":   {"technical": "uptrend", "fundamental": "PE 9 murah", "ml_risk": "n/a", "score": 70},
        "kepala strategi": {"decision": "BELI", "entry": 4500, "take_profit": 5000, "cut_loss": 4300, "reasoning": "Tren naik, PE 9 murah."},
        "devil's advocate": {"confidence": 0.66, "notes": "ok", "warnings": []},
    }
    def fake(system, user, **k):
        for marker, p in payloads.items():
            if marker in system:
                return p
        return {}
    monkeypatch.setattr(groq_client, "chat_json", fake)


def _user(monkeypatch, tier):
    monkeypatch.setattr(advisor_ep, "get_current_user", lambda: AdvisorUser("u-test", tier))


def test_chitchat_no_quota(client, monkeypatch):
    _user(monkeypatch, "basic")
    _install_groq(monkeypatch, {"intent": "chitchat"})
    r = client.post("/advisor/chat", json={"message": "halo"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "chitchat"
    assert body["quota"]["used"] == 0          # chitchat tak memotong kuota


def test_clarify_no_quota(client, monkeypatch):
    _user(monkeypatch, "basic")
    _install_groq(monkeypatch, {"intent": "clarify", "missing": ["ticker"]})
    r = client.post("/advisor/chat", json={"message": "analisa dong"})
    assert r.status_code == 200
    assert r.json()["intent"] == "clarify"
    assert r.json()["quota"]["used"] == 0


def test_analyze_consumes_quota(client, monkeypatch):
    _user(monkeypatch, "dev")
    _install_groq(monkeypatch, {"intent": "analyze", "params": {"ticker": "BBRI"}})
    r = client.post("/advisor/chat", json={"message": "analisa BBRI"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "analyze"
    assert body["data"]["decision"] == "BELI"
    assert body["confidence"] == 0.66
    assert body["quota"]["used"] == 1          # pipeline sukses -> kuota dipotong


def test_quota_exhausted_429(client, monkeypatch):
    _user(monkeypatch, "free")                 # limit 0
    _install_groq(monkeypatch, {"intent": "analyze", "params": {"ticker": "BBRI"}})
    r = client.post("/advisor/chat", json={"message": "analisa BBRI"})
    assert r.status_code == 429
    assert "kuota" in r.json()["detail"]["message"].lower()
