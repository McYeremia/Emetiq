"""Tes kuota harian advisor (per tier, reset harian, dev unlimited)."""
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
import models
from services.advisor import quota
from services.advisor.auth import AdvisorUser


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def test_peek_default_zero(db):
    info = quota.peek(db, AdvisorUser("u1", "basic"))
    assert info.used == 0 and info.limit == 3 and info.remaining == 3


def test_consume_increments(db):
    u = AdvisorUser("u1", "basic")
    quota.consume(db, u)
    quota.consume(db, u)
    info = quota.peek(db, u)
    assert info.used == 2 and info.remaining == 1


def test_free_tier_one_then_blocked(db):
    u = AdvisorUser("f", "free")                               # limit 1
    quota.ensure_available(db, u)                              # pesan ke-1 boleh
    quota.consume(db, u)
    with pytest.raises(quota.QuotaExceeded):
        quota.ensure_available(db, u)                          # ke-2 habis


def test_basic_tier_blocks_when_exhausted(db):
    u = AdvisorUser("u2", "basic")                              # limit 3
    for _ in range(3):
        quota.ensure_available(db, u)
        quota.consume(db, u)
    with pytest.raises(quota.QuotaExceeded):
        quota.ensure_available(db, u)


def test_dev_unlimited(db):
    u = AdvisorUser("dev", "dev")
    for _ in range(20):
        quota.ensure_available(db, u)      # tak pernah raise
        quota.consume(db, u)
    info = quota.peek(db, u)
    assert info.limit is None and info.remaining is None and info.used == 20


def test_resets_per_day(db):
    u = AdvisorUser("u3", "basic")
    # Pemakaian kemarin penuh
    db.add(models.AdvisorUsage(user_id="u3", date=date.today() - timedelta(days=1), count=3))
    db.commit()
    # Hari ini harus segar (baris berbeda per tanggal)
    info = quota.peek(db, u)
    assert info.used == 0 and info.remaining == 3
    quota.ensure_available(db, u)           # tidak raise
