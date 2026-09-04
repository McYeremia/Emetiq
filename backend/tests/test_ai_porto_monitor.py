"""Pantauan AI Porto untuk tier pro ke atas — baca saja.

Fitur ini menambah SATU endpoint baca di atas data yang sudah ada. Yang dijaga
berkas ini ada tiga lapis, dan lapis ketiga yang paling penting:

1. Tier di bawah `pro` ditolak, tier `pro` ke atas boleh melihat.
2. Tak ada jalur tulis sama sekali di router ini — tak mungkin memicu trade.
3. **AI Porto yang lama tidak ikut terbuka.** Syarat pemilik repo saat fitur ini
   diminta: "jangan sentuh AI Porto yang sudah ada". Kalau suatu saat seseorang
   memindahkan pagar `require_dev` ke helper baru dan salah menyetelnya, tes di
   bagian ketiga inilah yang berteriak.
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import CurrentUser, get_current_user
from database import Base, get_db
import main
import models
from services import trade_exec

MONITOR = "/ai-porto-monitor/portfolio"
DEV = "/ai-porto/portfolio"


@pytest.fixture(autouse=True)
def tanpa_dev_bypass(monkeypatch):
    """`AUTH_DEV_BYPASS=1` meloloskan permintaan tanpa token sama sekali. Kalau ia
    kebetulan aktif di environment penjalan tes, berkas ini lulus tanpa menguji apa
    pun."""
    monkeypatch.delenv("AUTH_DEV_BYPASS", raising=False)


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Factory = sessionmaker(bind=engine)

    s = Factory()
    for tk, harga in [("BBRI", 4000), ("TLKM", 3000)]:
        stock = models.Stock(ticker=tk, name=tk, sector="Finance")
        s.add(stock)
        s.flush()
        s.add(models.OHLCVDaily(stock_id=stock.id, date=date(2026, 1, 1),
                                open=harga, high=harga, low=harga, close=harga, volume=1000))
    s.commit()
    # Satu posisi di bucket AI supaya snapshot-nya tidak kosong.
    trade_exec.execute_trade(s, ticker="BBRI", action="BUY", lots=5,
                             trade_type="AUTO_AI", user_id=None)
    s.close()
    return Factory


@pytest.fixture
def klien(session_factory):
    """`tier=None` berarti anonim: override get_current_user TIDAK dipasang, jadi
    dependency asli yang jalan dan menolak permintaan tanpa header."""
    def override_db():
        d = session_factory()
        try:
            yield d
        finally:
            d.close()

    def buat(tier=None):
        main.app.dependency_overrides[get_db] = override_db
        if tier is None:
            main.app.dependency_overrides.pop(get_current_user, None)
        else:
            main.app.dependency_overrides[get_current_user] = \
                lambda: CurrentUser("uji-1", "uji@example.com", tier)
        return TestClient(main.app)

    yield buat
    main.app.dependency_overrides.clear()


# ── 1. Pagar tier ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("tier", ["free", "basic"])
def test_tier_di_bawah_pro_ditolak(klien, tier):
    assert klien(tier).get(MONITOR).status_code == 403


@pytest.mark.parametrize("tier", ["pro", "premium", "dev"])
def test_pro_ke_atas_boleh_melihat(klien, tier):
    r = klien(tier).get(MONITOR)
    assert r.status_code == 200, r.text
    assert "holdings" in r.json()


def test_anonim_ditolak(klien):
    assert klien().get(MONITOR).status_code == 401


def test_tier_tak_dikenal_ditolak(klien):
    """Gagal ke arah aman: tier yang tak ada di daftar diperlakukan sebagai paling
    rendah, bukan diloloskan."""
    assert klien("tier-karangan").get(MONITOR).status_code == 403


# ── 2. Tak ada jalur tulis ───────────────────────────────────────────────────

@pytest.mark.parametrize("metode", ["post", "put", "patch", "delete"])
def test_tak_ada_jalur_tulis(klien, metode):
    """405, bukan 200 atau 403 — artinya metodenya memang tak terdaftar sama sekali."""
    r = getattr(klien("dev"), metode)(MONITOR)
    assert r.status_code == 405


def test_tak_ada_endpoint_chat(klien):
    """Router pantauan tak boleh punya jalur yang menjalankan pipeline AI."""
    assert klien("dev").post("/ai-porto-monitor/chat", json={"message": "beli"}).status_code == 404


# ── 3. AI Porto lama tidak ikut terbuka ──────────────────────────────────────

@pytest.mark.parametrize("tier", ["free", "basic", "pro", "premium"])
def test_ai_porto_dev_tetap_terkunci(klien, tier):
    """Yang lama HANYA untuk dev — termasuk untuk tier yang boleh memakai pantauan."""
    assert klien(tier).get(DEV).status_code == 403


def test_chat_ai_porto_tetap_dev_saja(klien):
    assert klien("pro").post("/ai-porto/chat", json={"message": "kelola"}).status_code == 403


def test_dev_tetap_bisa_masuk_yang_lama(klien):
    assert klien("dev").get(DEV).status_code == 200


# ── 4. Isinya memang cerminan yang sama ──────────────────────────────────────

def test_isi_pantauan_sama_dengan_yang_dilihat_dev(klien):
    """Kalau suatu saat keduanya berselisih, halaman pantauan diam-diam
    menampilkan angka yang berbeda dari yang dilihat pemiliknya."""
    dev = klien("dev")
    assert dev.get(MONITOR).json() == dev.get(DEV).json()
