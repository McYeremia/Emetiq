"""Tes endpoint admin: gating dev, daftar user, ganti tier + pengaman."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import CurrentUser, get_current_user
from database import Base, get_db
import models
import main


DEV_ID = "dev-1"


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Factory = sessionmaker(bind=engine)
    s = Factory()
    # dev yang sedang login + 2 user biasa
    s.add(models.Profile(id=DEV_ID, email="dev@example.com", tier="dev"))
    s.add(models.Profile(id="u-basic", email="a@example.com", tier="free"))
    s.add(models.Profile(id="u-pro", email="b@example.com", tier="pro"))
    s.commit(); s.close()
    return Factory


@pytest.fixture
def make_client(session_factory):
    def override_db():
        d = session_factory()
        try:
            yield d
        finally:
            d.close()

    def _make(tier, uid=DEV_ID):
        main.app.dependency_overrides[get_db] = override_db
        main.app.dependency_overrides[get_current_user] = lambda: CurrentUser(uid, None, tier)
        return TestClient(main.app)

    yield _make
    main.app.dependency_overrides.clear()


# ── Gating ───────────────────────────────────────────────────────────────────

def test_list_users_requires_dev(make_client):
    assert make_client("free").get("/admin/users").status_code == 403
    r = make_client("dev").get("/admin/users")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_update_tier_requires_dev(make_client):
    assert make_client("free").patch("/admin/users/u-basic", json={"tier": "pro"}).status_code == 403


# ── Ganti tier ───────────────────────────────────────────────────────────────

def test_update_tier_success(make_client):
    r = make_client("dev").patch("/admin/users/u-basic", json={"tier": "premium"})
    assert r.status_code == 200
    assert r.json()["tier"] == "premium"
    # tersimpan
    r2 = make_client("dev").get("/admin/users")
    row = next(u for u in r2.json() if u["id"] == "u-basic")
    assert row["tier"] == "premium"


def test_update_tier_invalid(make_client):
    r = make_client("dev").patch("/admin/users/u-basic", json={"tier": "sultan"})
    assert r.status_code == 400


def test_update_tier_self_blocked(make_client):
    r = make_client("dev").patch(f"/admin/users/{DEV_ID}", json={"tier": "free"})
    assert r.status_code == 400
    assert "sendiri" in r.json()["detail"].lower()


def test_update_tier_user_not_found(make_client):
    r = make_client("dev").patch("/admin/users/ghost", json={"tier": "pro"})
    assert r.status_code == 404
