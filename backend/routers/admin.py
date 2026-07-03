"""Endpoint admin (khusus tier dev): lihat user terdaftar & ganti tier.

Tier disimpan di tabel `profiles` milik aplikasi (lihat auth.ensure_profile), jadi
semua operasi cukup di DB sendiri — tak butuh Supabase Admin API / service key.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import CurrentUser, require_dev
from database import get_db
import models

log = logging.getLogger("admin.endpoint")

router = APIRouter(prefix="/admin", tags=["admin"])

# Sumber kebenaran daftar tier valid (samakan dgn CurrentUser.tier & advisor TIER_LIMITS).
VALID_TIERS = ("free", "basic", "pro", "premium", "dev")


class UserRow(BaseModel):
    id: str
    email: Optional[str]
    tier: str
    created_at: Optional[str]  # ISO-8601


class TierUpdate(BaseModel):
    tier: str


def _row(p: models.Profile) -> UserRow:
    return UserRow(id=p.id, email=p.email, tier=p.tier,
                   created_at=p.created_at.isoformat() if p.created_at else None)


@router.get("/users", response_model=List[UserRow])
def list_users(db: Session = Depends(get_db), _: CurrentUser = Depends(require_dev)):
    """Semua profil user, terbaru dulu."""
    rows = db.query(models.Profile).order_by(models.Profile.created_at.desc()).all()
    return [_row(p) for p in rows]


@router.patch("/users/{user_id}", response_model=UserRow)
def update_tier(user_id: str, body: TierUpdate, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require_dev)):
    """Ganti tier satu user. Tidak boleh mengubah tier akun sendiri (cegah lockout)."""
    tier = (body.tier or "").lower().strip()
    if tier not in VALID_TIERS:
        raise HTTPException(status_code=400,
                            detail=f"Tier tidak valid. Pilihan: {', '.join(VALID_TIERS)}.")
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Tidak bisa mengubah tier akun sendiri.")

    prof = db.query(models.Profile).filter(models.Profile.id == user_id).first()
    if prof is None:
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")

    prof.tier = tier
    db.commit()
    db.refresh(prof)
    log.info("Tier user %s diubah ke %s oleh dev %s", user_id, tier, user.id)
    return _row(prof)
