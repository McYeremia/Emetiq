"""Tes 3 pipeline advisor (Groq di-mock; tiap stage dikenali dari system prompt)."""
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
import models
from services.advisor import pipelines, groq_client
from services.advisor.schemas import RouterParams


# ── Fixture DB ───────────────────────────────────────────────────────────────

def _stock(s, ticker, name, sector, pe, pbv, div, mcap):
    st = models.Stock(ticker=ticker, name=name, sector=sector,
                      pe_ratio=pe, pbv_ratio=pbv, dividend_yield=div, market_cap=mcap)
    s.add(st); s.flush(); return st


def _series(s, stock, start, step, n=60):
    d0 = date(2026, 1, 1)
    for i in range(n):
        p = start + step * i
        s.add(models.OHLCVDaily(stock_id=stock.id, date=d0 + timedelta(days=i),
                                open=p, high=p * 1.01, low=p * 0.99, close=p, volume=1_000_000))


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    bbri = _stock(s, "BBRI", "Bank BRI", "Finance", 9.0, 2.0, 4.0, 800_000_000_000_000)
    _stock(s, "TLKM", "Telkom", "Telco", 18.0, 3.0, 5.0, 400_000_000_000_000)
    _series(s, bbri, 4000, 10)
    _series(s, db_stock_tlkm := s.query(models.Stock).filter_by(ticker="TLKM").first(), 5000, -10)
    s.commit()
    yield s
    s.close()


def _mock(monkeypatch, by_marker):
    def fake(system, user, **k):
        for marker, payload in by_marker.items():
            if marker in system:
                return payload
        return {}
    monkeypatch.setattr(groq_client, "chat_json", fake)


# ── Screening ────────────────────────────────────────────────────────────────

def test_run_screen_empty_skips_llm(db, monkeypatch):
    # pe_max=1 -> tak ada kandidat; LLM tak boleh dipanggil
    def boom(*a, **k):
        raise AssertionError("LLM tidak boleh dipanggil saat kandidat kosong")
    monkeypatch.setattr(groq_client, "chat_json", boom)
    out = pipelines.run_screen(db, RouterParams(pe_max=1))
    assert out["data"]["candidates"] == []
    assert "longgarkan" in out["reply"].lower()


def test_run_screen_ranks_candidates(db, monkeypatch):
    _mock(monkeypatch, {
        "Urutkan kandidat": {"items": [{"ticker": "BBRI", "score": 82, "reason": "PE 9 murah", "key_numbers": {"pe": 9}}]},
        "pemeriksa cepat":  {"items": [{"ticker": "BBRI", "score": 82, "reason": "PE 9 murah", "key_numbers": {"pe": 9}}]},
    })
    out = pipelines.run_screen(db, RouterParams(pe_max=10))
    assert out["data"]["candidates"][0]["ticker"] == "BBRI"
    assert "BBRI" in out["reply"]


# ── Analisa ──────────────────────────────────────────────────────────────────

def test_run_analyze_not_found(db):
    out = pipelines.run_analyze(db, RouterParams(ticker="ZZZZ"))
    assert out["data"]["found"] is False


def test_run_analyze_needs_ticker(db):
    out = pipelines.run_analyze(db, RouterParams())
    assert out["data"]["intent"] == "clarify"


def test_run_analyze_full(db, monkeypatch):
    _mock(monkeypatch, {
        "tim spesialis":     {"technical": "uptrend, RSI sehat", "fundamental": "PE 9 murah", "ml_risk": "n/a", "score": 72},
        "kepala strategi":   {"decision": "BELI", "entry": 4500, "take_profit": 5000, "cut_loss": 4300, "reasoning": "Tren naik, PE 9 murah."},
        "devil's advocate":  {"confidence": 0.68, "notes": "ok", "warnings": ["likuiditas"]},
    })
    out = pipelines.run_analyze(db, RouterParams(ticker="BBRI"))
    card = out["data"]
    assert card["decision"] == "BELI"
    assert card["take_profit"] == 5000
    assert out["confidence"] == 0.68
    assert card["warnings"] == ["likuiditas"]
    assert "murah" in out["reply"]


# ── Portofolio ───────────────────────────────────────────────────────────────

def test_run_portfolio_empty(db):
    out = pipelines.run_portfolio(db)
    assert out["data"]["holdings"] == []
    assert "belum ada posisi" in out["reply"].lower()


def test_run_portfolio_full(db, monkeypatch):
    bbri = db.query(models.Stock).filter_by(ticker="BBRI").first()
    db.add(models.TradeLog(stock_id=bbri.id, action="BUY", date=date(2026, 2, 1),
                           price=4000, quantity=5, trade_type="MANUAL"))
    db.commit()
    _mock(monkeypatch, {
        "penasihat portofolio": {"overview": "Portofolio terkonsentrasi di BBRI.",
                                  "actions": [{"ticker": "BBRI", "action": "HOLD", "reason": "tren naik", "key_numbers": {}}],
                                  "cash_advice": "Sisakan kas untuk peluang."},
        "pemeriksa risiko":     {"confidence": 0.6, "notes": "ok", "warnings": []},
    })
    out = pipelines.run_portfolio(db)
    assert out["data"]["actions"][0]["ticker"] == "BBRI"
    assert "terkonsentrasi" in out["reply"].lower()
    assert out["confidence"] == 0.6
