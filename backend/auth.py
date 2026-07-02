"""Autentikasi bersama (Supabase Auth) untuk seluruh backend.

Verifikasi JWT Supabase secara OFFLINE (HS256 dengan SUPABASE_JWT_SECRET) — tidak
memanggil Supabase per-request. `get_current_user` adalah dependency FastAPI yang
mengembalikan user terverifikasi beserta tier-nya (dari tabel `profiles`).

Dev/local & pytest: set AUTH_DEV_BYPASS=1 untuk melewati verifikasi JWT dan memakai
user dev (id/tier dari env). Untuk test endpoint, lebih disarankan memakai
`app.dependency_overrides[get_current_user]`.
"""
import os
from dataclasses import dataclass
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

import models
from database import get_db


@dataclass
class CurrentUser:
    id: str
    email: Optional[str]
    tier: str   # free | basic | pro | premium | dev


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def _jwt_secret() -> str:
    return os.getenv("SUPABASE_JWT_SECRET", "")


def _jwt_aud() -> str:
    return os.getenv("SUPABASE_JWT_AUD", "authenticated")


def _supabase_url() -> str:
    # URL project Supabase (mis. https://xxxx.supabase.co). Dipakai untuk JWKS bila
    # token ditandatangani dengan kunci asimetris (ES256/RS256) — default project baru.
    return (os.getenv("SUPABASE_URL")
            or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")).rstrip("/")


# Cache PyJWKClient per-URL agar kunci publik JWKS tidak di-fetch tiap request.
_jwks_clients: dict = {}


def _jwks_client(url: str):
    client = _jwks_clients.get(url)
    if client is None:
        client = jwt.PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json", timeout=5)
        _jwks_clients[url] = client
    return client


def ensure_profile(db: Session, user_id: str, email: Optional[str]) -> models.Profile:
    """Cari baris profiles; buat (tier 'free') bila belum ada. Sinkronkan email."""
    prof = db.query(models.Profile).filter(models.Profile.id == user_id).first()
    if prof is None:
        prof = models.Profile(id=user_id, email=email, tier="free")
        db.add(prof)
        db.commit()
        db.refresh(prof)
    elif email and prof.email != email:
        prof.email = email
        db.commit()
    return prof


def _decode_token(token: str) -> dict:
    """Verifikasi JWT Supabase secara offline.

    Mendukung dua skema tanda tangan Supabase:
      • HS256  — legacy shared secret (SUPABASE_JWT_SECRET).
      • ES256/RS256 — kunci asimetris (default project baru), diverifikasi via JWKS
        publik dari SUPABASE_URL (kunci di-cache, tidak di-fetch tiap request).
    Algoritma dipilih otomatis dari header token.
    """
    try:
        alg = jwt.get_unverified_header(token).get("alg", "")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token tidak valid.")

    try:
        if alg == "HS256":
            secret = _jwt_secret()
            if not secret:
                raise HTTPException(status_code=500, detail="SUPABASE_JWT_SECRET belum diatur di server.")
            return jwt.decode(token, secret, algorithms=["HS256"], audience=_jwt_aud())

        if alg in ("ES256", "RS256"):
            url = _supabase_url()
            if not url:
                raise HTTPException(status_code=500, detail="SUPABASE_URL belum diatur di server (butuh JWKS).")
            key = _jwks_client(url).get_signing_key_from_jwt(token).key
            return jwt.decode(token, key, algorithms=["ES256", "RS256"], audience=_jwt_aud())

        raise HTTPException(status_code=401, detail=f"Algoritma token tidak didukung: {alg or 'kosong'}.")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token kedaluwarsa, silakan login ulang.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token tidak valid.")
    except jwt.PyJWKClientError:
        raise HTTPException(status_code=401, detail="Gagal memuat kunci verifikasi (JWKS).")


def _dev_user(db: Session) -> CurrentUser:
    uid = os.getenv("AUTH_DEV_USER_ID", "dev-user")
    prof = ensure_profile(db, uid, os.getenv("AUTH_DEV_EMAIL", "dev@example.com"))
    tier = os.getenv("AUTH_DEV_TIER") or prof.tier
    return CurrentUser(id=uid, email=prof.email, tier=tier)


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """Wajib login. Token hilang/invalid -> 401."""
    if _env_flag("AUTH_DEV_BYPASS"):
        return _dev_user(db)

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Tidak terautentikasi. Silakan login.")
    token = authorization.split(" ", 1)[1].strip()
    payload = _decode_token(token)
    uid = payload.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="Token tanpa subjek (sub).")
    prof = ensure_profile(db, uid, payload.get("email"))
    return CurrentUser(id=uid, email=prof.email, tier=prof.tier)


def require_dev(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Seperti get_current_user tapi hanya lolos untuk tier 'dev' (403 selain itu)."""
    if (user.tier or "").lower() != "dev":
        raise HTTPException(status_code=403, detail="Fitur ini khusus tier developer.")
    return user


def get_optional_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Optional[CurrentUser]:
    """Seperti get_current_user tapi mengembalikan None (bukan 401) saat belum login."""
    if _env_flag("AUTH_DEV_BYPASS"):
        return _dev_user(db)
    if not authorization:
        return None
    try:
        return get_current_user(authorization, db)
    except HTTPException:
        return None
