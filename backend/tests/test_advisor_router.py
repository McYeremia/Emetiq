"""Tes router intent (Groq di-mock di level groq_client.chat_json)."""
import pytest

from services.advisor import router, groq_client
from services.advisor.schemas import ScreenForm, AdvisorContext


def _mock_groq(monkeypatch, payload):
    monkeypatch.setattr(groq_client, "chat_json", lambda *a, **k: payload)


def test_route_parses_intent_and_params(monkeypatch):
    _mock_groq(monkeypatch, {"intent": "analyze", "params": {"ticker": "bbri"}, "missing": []})
    out = router.route("gimana bbri?")
    assert out.intent == "analyze"
    assert out.params.ticker == "BBRI"          # di-uppercase


def test_route_invalid_intent_becomes_clarify(monkeypatch):
    _mock_groq(monkeypatch, {"intent": "tradeNow", "params": {}})
    out = router.route("...")
    assert out.intent == "clarify"


def test_route_handles_empty_payload(monkeypatch):
    _mock_groq(monkeypatch, {})
    out = router.route("halo")
    assert out.intent == "clarify"
    assert out.params.ticker is None


def test_route_screen_params(monkeypatch):
    _mock_groq(monkeypatch, {"intent": "screen", "params": {"pe_max": 15, "div_min": 3}, "missing": []})
    out = router.route("cari saham murah dividen tinggi")
    assert out.intent == "screen"
    assert out.params.pe_max == 15
    assert out.params.div_min == 3


def test_route_form_overrides_params(monkeypatch):
    _mock_groq(monkeypatch, {"intent": "screen", "params": {"pe_max": 99}})
    form = ScreenForm(pe_max=12, sector="Finance")
    out = router.route("saring", form=form)
    assert out.params.pe_max == 12              # form menang
    assert out.params.sector == "Finance"


def test_route_form_ticker_uppercased(monkeypatch):
    _mock_groq(monkeypatch, {"intent": "analyze", "params": {}})
    out = router.route("analisa", form=ScreenForm(ticker="tlkm"))
    assert out.params.ticker == "TLKM"


def test_route_extracts_count(monkeypatch):
    _mock_groq(monkeypatch, {"intent": "screen", "params": {"pe_max": 15, "count": 3}})
    out = router.route("kasih 3 saham PE di bawah 15")
    assert out.intent == "screen"
    assert out.params.count == 3


def test_route_extracts_price_and_count(monkeypatch):
    _mock_groq(monkeypatch, {"intent": "screen", "params": {"price_max": 2000, "count": 5}})
    out = router.route("carikan 5 saham bagus dengan harga di bawah 2000")
    assert out.intent == "screen"
    assert out.params.price_max == 2000
    assert out.params.count == 5


def test_route_rank_intent(monkeypatch):
    _mock_groq(monkeypatch, {"intent": "rank", "params": {"count": 1}})
    ctx = AdvisorContext(candidates=[{"ticker": "BBRI"}, {"ticker": "TLKM"}])
    out = router.route("dari tadi mana yang paling oke?", context=ctx)
    assert out.intent == "rank"
    assert out.params.count == 1
