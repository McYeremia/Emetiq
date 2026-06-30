"""Tes endpoint watchlist: CRUD + scoping per user."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import CurrentUser, get_current_user
from database import Base, get_db
import main


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


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


def test_add_normalizes_and_lists(make_client):
    c = make_client("u1")
    assert c.post("/watchlist", json={"ticker": "bbri"}).status_code == 200
    assert c.get("/watchlist").json()["tickers"] == ["BBRI"]


def test_add_idempotent(make_client):
    c = make_client("u1")
    c.post("/watchlist", json={"ticker": "BBRI"})
    c.post("/watchlist", json={"ticker": "BBRI"})
    assert c.get("/watchlist").json()["tickers"] == ["BBRI"]


def test_delete(make_client):
    c = make_client("u1")
    c.post("/watchlist", json={"ticker": "BBRI"})
    c.delete("/watchlist/BBRI")
    assert c.get("/watchlist").json()["tickers"] == []


def test_scoped_per_user(make_client):
    c1 = make_client("u1")
    c1.post("/watchlist", json={"ticker": "BBRI"})
    c2 = make_client("u2")
    assert c2.get("/watchlist").json()["tickers"] == []
