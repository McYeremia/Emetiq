"""Tipe user ringan untuk modul advisor (quota).

Autentikasi nyata kini ada di `backend/auth.py` (Supabase JWT). `AdvisorUser`
dipertahankan sebagai struktur ringan (id, tier) yang dipakai `quota.py` — dan
`CurrentUser` dari auth bersama kompatibel (punya `.id` dan `.tier`).
"""
from dataclasses import dataclass


@dataclass
class AdvisorUser:
    id: str
    tier: str   # free | basic | pro | premium | dev
