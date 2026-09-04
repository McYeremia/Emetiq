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


# Urutan tier dari yang paling rendah. Sumber kebenaran daftar tiernya ada di
# `routers/admin.py` (VALID_TIERS); di sini yang ditambahkan adalah URUTANNYA.
#
# `dev` diletakkan paling atas karena ia tier pemilik: apa pun yang boleh dilihat
# `premium` sudah pasti boleh dilihat `dev`. Itu membuat pagar "pro ke atas" tak
# perlu menyebut `dev` satu per satu — dan tak akan lupa menyebutnya nanti.
URUTAN_TIER = ("free", "basic", "pro", "premium", "dev")


def require_tier_minimal(minimal: str):
    """Dependency: menolak 403 bila tier user berada DI BAWAH `minimal`.

    Berbeda dari `require_dev` yang mencocokkan satu tier persis, ini berbasis
    urutan — dipakai fitur yang dibuka bertahap ke tier berbayar.

    Tier yang tak dikenal (mis. sisa data lama atau salah ketik di dashboard admin)
    diperlakukan sebagai paling rendah, bukan diloloskan. Gagal ke arah aman.
    """
    if minimal not in URUTAN_TIER:
        raise ValueError(f"Tier tak dikenal: {minimal}")
    batas = URUTAN_TIER.index(minimal)

    def penjaga(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        tier = (user.tier or "").lower()
        posisi = URUTAN_TIER.index(tier) if tier in URUTAN_TIER else -1
        if posisi < batas:
            raise HTTPException(
                status_code=403,
                detail=f"Fitur ini untuk tier {minimal} ke atas.",
            )
        return user

    return penjaga


# Host yang dianggap "mesin ini juga". Basis data di sini aman dibypass: yang bisa
# menyentuhnya cuma orang yang sudah duduk di depan komputernya.
_HOST_LOKAL = {"", "localhost", "127.0.0.1", "::1", "[::1]"}


def pastikan_bypass_aman(database_url: Optional[str] = None) -> None:
    """Menolak menyalakan server bila `AUTH_DEV_BYPASS` aktif atas basis data JAUH.

    `AUTH_DEV_BYPASS=1` membuat `get_current_user` meloloskan setiap permintaan
    sebagai user dev — tanpa token sama sekali. Itu memang gunanya saat
    mengembangkan di laptop. Tapi flag yang sama menyala di server berarti seluruh
    aplikasi terbuka untuk siapa pun: membaca portofolio, mengubah tier orang lain,
    dan memerintahkan AI Porto mengeksekusi trade.

    Yang membuat kesalahan konfigurasi seperti itu berbahaya adalah DIAMNYA — tak ada
    galat, tak ada log aneh, aplikasinya jalan normal dengan pintu terbuka. Fungsi ini
    mengubahnya jadi kegagalan keras saat boot, yang mustahil tak disadari.

    Aturannya: bypass hanya untuk basis data lokal (SQLite, atau Postgres di
    localhost). Selain itu — Supabase termasuk — server menolak menyala.

    Pesan galatnya sengaja TIDAK memuat `DATABASE_URL`: ia mengandung kata sandi, dan
    pesan ini berakhir di log server yang bisa tersalin ke mana-mana.
    """
    if not _env_flag("AUTH_DEV_BYPASS"):
        return

    url = database_url if database_url is not None else os.getenv("DATABASE_URL", "")
    url = (url or "").strip()
    if not url:
        return  # database.py jatuh ke berkas SQLite lokal

    skema, _, sisa = url.partition("://")
    if skema.lower().startswith("sqlite"):
        return

    # Ambil host tanpa mengurai kredensial: bagian setelah '@' terakhir, sebelum
    # '/' atau ':' berikutnya.
    otoritas = sisa.rsplit("@", 1)[-1]
    host = otoritas.split("/", 1)[0].rsplit(":", 1)[0].lower()
    if host in _HOST_LOKAL:
        return

    raise RuntimeError(
        "AUTH_DEV_BYPASS aktif sementara DATABASE_URL menunjuk basis data non-lokal "
        f"(skema '{skema}'). Kombinasi itu membuka SELURUH aplikasi tanpa autentikasi "
        "— termasuk eksekusi trade AI Porto. Matikan AUTH_DEV_BYPASS, atau arahkan "
        "DATABASE_URL ke basis data lokal."
    )
