"""Pagar autentikasi endpoint tulis & endpoint berat.

Sebelum 3 Sep 2026 seluruh router `/stocks`, `/backtest`, dan `/broker-flow`
terbuka tanpa autentikasi apa pun — termasuk `POST /stocks/refresh` (sync ~740
saham) dan `GET /backtest/screen/{id}` (terukur 4,6-9,8 detik CPU, sinkron di
worker yang sama yang melayani pengunjung lain).

Berkas ini menjaga dua arah sekaligus, dan arah KEDUA yang paling mudah rusak:

1. Endpoint tulis/berat MENOLAK anonim.
2. Endpoint BACA data pasar tetap TERBUKA. Dashboard dan overview menariknya dari
   Server Component tanpa token, dan header `Cache-Control: public` hanya sah
   selama jawabannya sama untuk semua orang. Memagari router `/stocks` sekaligus
   akan mematikan halaman-halaman itu tanpa satu pun galat yang terlihat.
"""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import CurrentUser, get_current_user
from database import Base, get_db
import models
import main


@pytest.fixture(autouse=True)
def tanpa_dev_bypass(monkeypatch):
    """`AUTH_DEV_BYPASS=1` membuat get_current_user meloloskan permintaan tanpa
    token sama sekali. Kalau ia kebetulan aktif di environment penjalan tes,
    seluruh berkas ini akan lulus tanpa menguji apa pun."""
    monkeypatch.delenv("AUTH_DEV_BYPASS", raising=False)


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Factory = sessionmaker(bind=engine)
    s = Factory()
    bbri = models.Stock(ticker="BBRI", name="Bank BRI", sector="Finance")
    s.add(bbri)
    s.flush()
    # 60 baris, bukan 1. `ta` melempar IndexError (bukan mengembalikan None) bila
    # deretnya lebih pendek dari jendela indikator, jadi satu baris membuat
    # /indicators balas 500 dan tesnya menuduh pagar auth yang salah.
    for i in range(60):
        harga = 4000 + i
        s.add(models.OHLCVDaily(stock_id=bbri.id, date=date(2026, 1, 1) + timedelta(days=i),
                                open=harga, high=harga + 20, low=harga - 20,
                                close=harga, volume=1000 + i))
    s.commit()
    s.close()
    return Factory


@pytest.fixture
def make_client(session_factory):
    """`user=None` berarti anonim: override get_current_user TIDAK dipasang, jadi
    dependency asli yang jalan dan menolak permintaan tanpa header."""
    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def _make(user_id=None, tier="free"):
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides[get_db] = override_db
        if user_id is not None:
            main.app.dependency_overrides[get_current_user] = \
                lambda: CurrentUser(user_id, None, tier)
        return TestClient(main.app)

    yield _make
    main.app.dependency_overrides.clear()


# --- 1. Anonim ditolak -------------------------------------------------------

ENDPOINT_TERTUTUP = [
    ("POST", "/stocks/BBRI"),
    ("POST", "/stocks/BBRI/refresh"),
    ("GET", "/backtest/screen/ma-cross"),
    ("GET", "/backtest/run/BBRI/ma-cross"),
]


@pytest.mark.parametrize("method,path", ENDPOINT_TERTUTUP)
def test_anonim_ditolak(make_client, method, path):
    c = make_client()
    assert c.request(method, path).status_code == 401, path


# --- 2. Operasi seluruh pasar tak lagi punya jalur HTTP ---------------------

@pytest.mark.parametrize("nama", ["scan", "refresh", "sync-status"])
def test_operasi_seluruh_pasar_tak_bisa_dipicu_lewat_http(make_client, nama):
    """`POST /stocks/refresh` & `/scan` dan `GET /sync-status` dihapus 3 Sep 2026;
    pekerjaannya pindah ke `scripts/daily_sync.py` di runner GitHub.

    Yang diuji di sini bukan sekadar "rutenya hilang". Rute statis di router ini
    semuanya GET, jadi POST ke jalur yang sama jatuh ke `POST /stocks/{ticker}` —
    artinya `POST /stocks/scan` akan dibaca sebagai "tambah saham bernama SCAN"
    dan menembak yfinance. Penjaga NAMA_RUTE_BUKAN_TICKER menghentikannya dengan
    pesan yang jujur, bukan "Stock not found on Yahoo Finance".
    """
    c = make_client("dev1", tier="dev")
    res = c.post(f"/stocks/{nama}")
    assert res.status_code == 404
    assert "bukan kode saham" in res.json()["detail"]


def test_penjaga_nama_rute_tak_menghalangi_ticker_sungguhan(make_client):
    """Penjaga di atas tak boleh menolak saham yang sah."""
    c = make_client("u1", tier="free")
    assert c.post("/stocks/BBRI").json()["status"] == "exists"


# --- 3. Login biasa cukup untuk sisanya -------------------------------------

def test_user_biasa_boleh_tambah_saham(make_client):
    """BBRI sudah ada di fixture, jadi jalur ini pulang lebih dulu tanpa
    menyentuh yfinance — yang diuji di sini pagarnya, bukan pengambilan datanya."""
    c = make_client("u1", tier="free")
    res = c.post("/stocks/BBRI")
    assert res.status_code == 200
    assert res.json()["status"] == "exists"


def test_user_biasa_boleh_backtest(make_client, monkeypatch):
    import services.backtester as bt_svc
    monkeypatch.setattr(bt_svc, "run_backtest",
                        lambda *a, **k: {"strategy_id": "ma-cross", "ticker": "BBRI"})

    c = make_client("u1", tier="free")
    assert c.get("/backtest/run/BBRI/ma-cross").status_code == 200


def test_screener_terpagari_di_level_router(make_client, monkeypatch):
    """Pagar dipasang di `APIRouter(dependencies=[...])`, bukan per-endpoint.
    Tes ini memastikan endpoint yang TIDAK menyebut dependency itu di tanda
    tangannya pun tetap terlindungi."""
    import services.watcher as watcher
    monkeypatch.setattr(watcher, "screen_by_strategy", lambda db, sid: [])

    assert make_client().get("/backtest/screen/ma-cross").status_code == 401
    assert make_client("u1", tier="free").get("/backtest/screen/ma-cross").status_code == 200


# --- 4. Endpoint baca data pasar TETAP publik -------------------------------

@pytest.mark.parametrize("path", [
    "/stocks",
    "/stocks?ringkas=true",
    "/stocks/signals",
    "/stocks/BBRI/ohlcv",
    "/stocks/BBRI/indicators",
])
def test_baca_pasar_tetap_publik(make_client, path):
    assert make_client().get(path).status_code == 200, path


def test_header_cache_masih_terpasang_untuk_anonim(make_client):
    """Tahap 1 dari AUDIT-OPTIMALISASI.md. Kalau endpoint baca suatu saat ikut
    dipagari, nilai header ini WAJIB berubah dari `public` jadi `private` —
    jawaban per-user tak boleh disimpan cache bersama."""
    res = make_client().get("/stocks?ringkas=true")
    assert res.headers.get("cache-control", "").startswith("public")


# --- 5. Peninggalan broker-flow benar-benar hilang --------------------------

@pytest.mark.parametrize("method,path", [
    ("GET", "/broker-flow"),
    ("GET", "/broker-flow/available-dates"),
    ("POST", "/broker-flow/scrape"),
])
def test_rute_broker_flow_sudah_dihapus(make_client, method, path):
    """`POST /broker-flow/scrape` dulu tanpa auth DAN menembak IDX dari IP server.
    Ia tak dipagari melainkan dihapus — halamannya tak tertaut dari mana pun dan
    fungsinya sudah digantikan Big Money. Lihat docstring `models.BrokerFlow`."""
    assert make_client().request(method, path).status_code == 404
