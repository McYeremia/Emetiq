"""Kuota harian per tier untuk AI Advisor.

Alur di endpoint: ensure_available() -> jalankan pipeline -> consume().
Kuota dipotong HANYA bila pipeline berhasil (consume dipanggil setelahnya), dan
HANYA untuk intent pipeline (screen/analyze/portfolio). clarify/chitchat tidak memotong.
"""
from datetime import date as date_cls

from sqlalchemy.orm import Session

import models
from services.advisor import config
from services.advisor.auth import AdvisorUser
from services.advisor.schemas import QuotaInfo


class QuotaExceeded(Exception):
    """Kuota harian habis — endpoint membalas HTTP 429."""
    def __init__(self, info: QuotaInfo):
        self.info = info
        super().__init__("Kuota harian advisor habis")


def _today() -> date_cls:
    return date_cls.today()


def _row_for_today(db: Session, user_id: str):
    return (
        db.query(models.AdvisorUsage)
        .filter(models.AdvisorUsage.user_id == user_id, models.AdvisorUsage.date == _today())
        .first()
    )


def _info(used: int, tier: str) -> QuotaInfo:
    limit = config.tier_limit(tier)
    remaining = None if limit is None else max(0, limit - used)
    return QuotaInfo(used=used, limit=limit, remaining=remaining)


def peek(db: Session, user: AdvisorUser) -> QuotaInfo:
    """Kuota saat ini tanpa mengubah apa pun."""
    row = _row_for_today(db, user.id)
    return _info(row.count if row else 0, user.tier)


def ensure_available(db: Session, user: AdvisorUser) -> QuotaInfo:
    """Pastikan masih ada jatah; kalau habis -> QuotaExceeded. Tidak menambah count."""
    info = peek(db, user)
    if info.limit is not None and (info.remaining or 0) <= 0:
        raise QuotaExceeded(info)
    return info


def consume(db: Session, user: AdvisorUser) -> QuotaInfo:
    """Tambah 1 pemakaian (panggil hanya setelah pipeline sukses)."""
    row = _row_for_today(db, user.id)
    if row is None:
        row = models.AdvisorUsage(user_id=user.id, date=_today(), count=0)
        db.add(row)
    row.count += 1
    db.commit()
    return _info(row.count, user.tier)
