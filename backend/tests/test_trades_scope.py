"""Tes scoping portofolio/trade per user (USER bucket di-scope user_id)."""
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


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Factory = sessionmaker(bind=engine)
    s = Factory()
    bbri = models.Stock(ticker="BBRI", name="Bank BRI", sector="Finance")
    s.add(bbri); s.flush()
    s.add(models.OHLCVDaily(stock_id=bbri.id, date=date(2026, 1, 1),
                            open=4000, high=4000, low=4000, close=4000, volume=1000))
    s.commit(); s.close()
    return Factory


@pytest.fixture
def make_client(session_factory):
    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def _make(user_id, tier="free"):
        main.app.dependency_overrides[get_db] = override_db
        main.app.dependency_overrides[get_current_user] = lambda: CurrentUser(user_id, None, tier)
        return TestClient(main.app)

    yield _make
    main.app.dependency_overrides.clear()


def test_portfolio_scoped_per_user(make_client):
    c1 = make_client("u1")
    assert c1.post("/trades", json={"ticker": "BBRI", "action": "BUY",
                                     "quantity": 5, "price": 4000}).status_code == 200
    p1 = c1.get("/trades/portfolio").json()
    assert any(a["ticker"] == "BBRI" for a in p1["USER"]["assets"])

    c2 = make_client("u2")
    p2 = c2.get("/trades/portfolio").json()
    assert p2["USER"]["assets"] == []


def test_trade_detail_ownership(make_client):
    c1 = make_client("u1")
    c1.post("/trades", json={"ticker": "BBRI", "action": "BUY", "quantity": 5, "price": 4000})
    tid = c1.get("/trades/history?agent=USER").json()[0]["id"]

    assert c1.get(f"/trades/{tid}").status_code == 200
    c2 = make_client("u2")
    assert c2.get(f"/trades/{tid}").status_code == 404


def test_user_biasa_tak_bisa_menulis_ke_bucket_ai(make_client):
    """`trade_type` datang dari klien, dan trade AI disimpan dengan user_id NULL
    sehingga terlihat oleh SEMUA user lewat `_visible_trades`. Tanpa pagar ini,
    user tier `free` cukup mengirim {"trade_type": "AUTO_AI"} untuk menitipkan
    posisi palsu ke porto orang lain."""
    c = make_client("u1", tier="free")
    for tipe in ("AUTO_AI", "AUTO_GEMINI", "AUTO_CLAUDE", "auto_ai"):
        res = c.post("/trades", json={"ticker": "BBRI", "action": "BUY",
                                      "quantity": 5, "price": 4000, "trade_type": tipe})
        assert res.status_code == 403, tipe

    # Dan bucket AI-nya memang tetap kosong — bukan sekadar status kodenya benar.
    assert c.get("/trades/portfolio").json()["AI"]["assets"] == []


def test_dev_tetap_bisa_menulis_ke_bucket_ai(make_client):
    """Pagar di atas tak boleh mematikan AI Porto, yang justru bekerja dengan
    menulis ke bucket global itu."""
    c = make_client("dev1", tier="dev")
    res = c.post("/trades", json={"ticker": "BBRI", "action": "BUY",
                                  "quantity": 5, "price": 4000, "trade_type": "AUTO_AI"})
    assert res.status_code == 200
    assert any(a["ticker"] == "BBRI" for a in c.get("/trades/portfolio").json()["AI"]["assets"])
