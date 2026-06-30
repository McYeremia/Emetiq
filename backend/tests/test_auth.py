"""Tes auth bersama: verifikasi JWT Supabase (offline), profil otomatis, dev bypass."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
import models
import auth

SECRET = "test-secret-123"


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    monkeypatch.delenv("AUTH_DEV_BYPASS", raising=False)


def _token(sub="user-1", email="a@b.com", exp_delta=3600, secret=SECRET, aud="authenticated"):
    payload = {"sub": sub, "email": email, "aud": aud,
               "exp": datetime.now(timezone.utc) + timedelta(seconds=exp_delta)}
    return jwt.encode(payload, secret, algorithm="HS256")


def test_ensure_profile_creates_free(db):
    p = auth.ensure_profile(db, "user-1", "a@b.com")
    assert p.tier == "free" and p.email == "a@b.com"


def test_ensure_profile_idempotent(db):
    auth.ensure_profile(db, "user-1", "a@b.com")
    auth.ensure_profile(db, "user-1", "a@b.com")
    assert db.query(models.Profile).count() == 1


def test_valid_token(db):
    u = auth.get_current_user(f"Bearer {_token()}", db)
    assert u.id == "user-1" and u.tier == "free" and u.email == "a@b.com"


def test_tier_loaded_from_profile(db):
    db.add(models.Profile(id="user-1", email="a@b.com", tier="pro")); db.commit()
    u = auth.get_current_user(f"Bearer {_token()}", db)
    assert u.tier == "pro"


def test_missing_header_401(db):
    with pytest.raises(HTTPException) as e:
        auth.get_current_user(None, db)
    assert e.value.status_code == 401


def test_non_bearer_header_401(db):
    with pytest.raises(HTTPException) as e:
        auth.get_current_user("Basic abc", db)
    assert e.value.status_code == 401


def test_bad_signature_401(db):
    with pytest.raises(HTTPException) as e:
        auth.get_current_user(f"Bearer {_token(secret='wrong')}", db)
    assert e.value.status_code == 401


def test_expired_401(db):
    with pytest.raises(HTTPException) as e:
        auth.get_current_user(f"Bearer {_token(exp_delta=-10)}", db)
    assert e.value.status_code == 401


def test_optional_user_none_without_header(db):
    assert auth.get_optional_user(None, db) is None


def test_optional_user_returns_on_valid(db):
    u = auth.get_optional_user(f"Bearer {_token()}", db)
    assert u is not None and u.id == "user-1"


def test_dev_bypass(db, monkeypatch):
    monkeypatch.setenv("AUTH_DEV_BYPASS", "1")
    monkeypatch.setenv("AUTH_DEV_TIER", "dev")
    u = auth.get_current_user(None, db)
    assert u.tier == "dev"
