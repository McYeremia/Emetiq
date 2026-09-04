"""Penjaga: `AUTH_DEV_BYPASS` tak boleh menyala di atas basis data non-lokal.

`AUTH_DEV_BYPASS=1` membuat `get_current_user` meloloskan SETIAP permintaan sebagai
user dev — tanpa token, tanpa verifikasi apa pun. Itu memang gunanya saat
mengembangkan di laptop. Tapi kalau flag yang sama ikut menyala di server produksi,
seluruh aplikasi terbuka: siapa pun bisa membaca portofolio, mengubah tier orang
lain, dan memerintahkan AI Porto mengeksekusi trade.

Yang berbahaya dari kesalahan konfigurasi seperti ini adalah **diamnya**: tak ada
galat, tak ada log mencurigakan, aplikasinya jalan normal — hanya saja pintunya
terbuka. Penjaga ini mengubahnya jadi kegagalan keras saat server dinyalakan.

Aturannya sederhana: bypass hanya boleh untuk basis data LOKAL (SQLite, atau
Postgres di localhost). Basis data di mesin lain — Supabase termasuk — menolak.
"""
import pytest

from auth import pastikan_bypass_aman

SUPABASE = "postgresql://pengguna:rahasia-sekali@db.abcdefgh.supabase.co:5432/postgres"


@pytest.fixture
def bypass(monkeypatch):
    """Menyalakan AUTH_DEV_BYPASS untuk satu tes."""
    monkeypatch.setenv("AUTH_DEV_BYPASS", "1")


@pytest.fixture(autouse=True)
def bersihkan_env(monkeypatch):
    monkeypatch.delenv("AUTH_DEV_BYPASS", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)


# ── Yang boleh ───────────────────────────────────────────────────────────────

def test_tanpa_bypass_basis_data_jauh_pun_boleh():
    """Tanpa flag, penjaga ini tak berpendapat apa-apa — itu keadaan normal."""
    pastikan_bypass_aman(SUPABASE)


@pytest.mark.parametrize("url", [
    "sqlite://",                       # in-memory, dipakai suite tes
    "sqlite:///./idxanalyst.db",       # berkas lokal
    "postgresql://u:p@localhost:5432/emetiq",
    "postgresql://u:p@127.0.0.1:5432/emetiq",
    "",                                # kosong -> database.py jatuh ke SQLite lokal
])
def test_basis_data_lokal_boleh_dibypass(bypass, url):
    pastikan_bypass_aman(url)


# ── Yang ditolak ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    SUPABASE,
    "postgresql://u:p@10.20.30.40:5432/emetiq",
    "postgres://u:p@db.internal.example.com/emetiq",
    "mysql://u:p@db.example.com/emetiq",
])
def test_basis_data_jauh_menolak_bypass(bypass, url):
    with pytest.raises(RuntimeError):
        pastikan_bypass_aman(url)


@pytest.mark.parametrize("nilai", ["1", "true", "TRUE", "yes"])
def test_semua_bentuk_flag_ikut_dijaga(monkeypatch, nilai):
    """Flag-nya dibaca longgar (`1`/`true`/`yes`), jadi penjaganya harus sama longgar
    — kalau tidak, satu ejaan lolos diam-diam."""
    monkeypatch.setenv("AUTH_DEV_BYPASS", nilai)
    with pytest.raises(RuntimeError):
        pastikan_bypass_aman(SUPABASE)


def test_membaca_dari_environment_bila_tak_diberi_url(monkeypatch, bypass):
    monkeypatch.setenv("DATABASE_URL", SUPABASE)
    with pytest.raises(RuntimeError):
        pastikan_bypass_aman()


# ── Pesannya tak boleh membocorkan kredensial ────────────────────────────────

def test_pesan_galat_tak_memuat_kata_sandi(bypass):
    """Pesan ini muncul di log server dan mungkin ikut tersalin ke tiket atau chat.
    Ia harus menjelaskan masalahnya tanpa membawa isi DATABASE_URL."""
    with pytest.raises(RuntimeError) as galat:
        pastikan_bypass_aman(SUPABASE)

    pesan = str(galat.value)
    assert "rahasia-sekali" not in pesan
    assert "pengguna" not in pesan
    assert "AUTH_DEV_BYPASS" in pesan, "pesan harus menyebut flag mana yang bermasalah"
