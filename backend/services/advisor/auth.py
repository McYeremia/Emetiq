"""Stub auth untuk AI Advisor (auth-agnostic).

Spec B (sistem akun) di luar cakupan; advisor hanya butuh `get_current_user()` yang
mengembalikan user dengan `id` dan `tier`. Saat sistem akun siap, ganti implementasi
ini untuk membaca user dari sesi/token — sisanya tak perlu berubah.
"""
import os
from dataclasses import dataclass


@dataclass
class AdvisorUser:
    id: str
    tier: str   # free | basic | pro | premium | dev


def get_current_user() -> AdvisorUser:
    # Sementara: satu user dev (kuota unlimited). Override lewat env saat perlu menguji tier.
    return AdvisorUser(
        id=os.getenv("ADVISOR_DEV_USER_ID", "dev-user"),
        tier=os.getenv("ADVISOR_DEV_TIER", "dev"),
    )
