"""Tes lapisan HTTP: kompresi gzip, urutan middleware, dan header cache.

Bagian kompresi sengaja memakai endpoint yang TIDAK menyentuh database:
  • /openapi.json — dihasilkan FastAPI sendiri, ~25 KB (di atas ambang kompresi)
  • /me tanpa token — balasan 401 ~49 byte (di bawah ambang)

Dulu yang kecil adalah /stocks/sync-status, tapi endpoint itu dihapus bersama
mesin sync 3 Sep 2026. Yang diuji tetap sama: respons di bawah ambang tak boleh
dibungkus gzip. Status 401 bukan 200 tak mengubah apa pun di sini — middleware
kompresi tak peduli status, hanya ukuran.

Bagian cache butuh basis data, jadi memakai SQLite in-memory lewat
dependency_overrides — pola yang sama dengan tes endpoint lain di repo ini.
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
import main
import models
from routers.stocks import CACHE_PASAR

AMBANG = 1000   # samakan dengan minimum_size di main.py


def _client() -> TestClient:
    # TestClient httpx mengirim Accept-Encoding sendiri dan mendekompresi
    # responsnya, tapi header aslinya tetap terbaca.
    return TestClient(main.app)


def test_respons_besar_dikompresi():
    """Payload di atas ambang harus dibungkus gzip."""
    res = _client().get("/openapi.json")
    assert res.status_code == 200
    assert len(res.content) > AMBANG, "prasyarat tes: /openapi.json harus > ambang"
    assert res.headers.get("content-encoding") == "gzip"


def test_respons_kecil_tidak_dikompresi():
    """Di bawah ambang, membungkus justru menambah ukuran — jangan dilakukan."""
    res = _client().get("/me")
    assert res.status_code == 401
    assert len(res.content) < AMBANG, "prasyarat tes: balasan /me harus < ambang"
    assert res.headers.get("content-encoding") is None


def test_klien_tanpa_gzip_tetap_dilayani():
    """Klien yang tak menyatakan dukungan gzip harus menerima respons apa adanya."""
    res = _client().get("/openapi.json", headers={"Accept-Encoding": "identity"})
    assert res.status_code == 200
    assert res.headers.get("content-encoding") is None
    assert res.json()["info"]["title"]


def test_isi_tetap_utuh_setelah_kompresi():
    """Kompresi tak boleh mengubah muatan — bandingkan dengan versi tak terkompresi."""
    c = _client()
    terkompresi = c.get("/openapi.json").json()
    apa_adanya = c.get("/openapi.json", headers={"Accept-Encoding": "identity"}).json()
    assert terkompresi == apa_adanya


def test_cors_tetap_lapisan_terluar():
    """GZip ditambahkan sebelum CORS, jadi preflight harus tetap dijawab CORS.

    Kalau urutan middleware terbalik, OPTIONS akan lolos ke GZip lebih dulu dan
    header CORS-nya hilang — browser lalu memblokir seluruh permintaan.
    """
    res = _client().options(
        "/stocks",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_header_cors_ada_pada_respons_biasa():
    """Respons terkompresi tetap harus membawa header CORS."""
    res = _client().get("/openapi.json", headers={"Origin": "http://localhost:3000"})
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert res.headers.get("content-encoding") == "gzip"


# ── Header cache pada endpoint data pasar ────────────────────────────────────

@pytest.fixture
def klien_db():
    """TestClient dengan SQLite in-memory berisi cukup data untuk lima endpoint baca.

    ^JKSE sengaja disemai LENGKAP dengan dua baris harga: tanpa itu `/stocks/ihsg`
    jatuh ke jalur cadangan yang menembak Yahoo Finance sungguhan, dan tes ini
    berubah jadi tes jaringan.
    """
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    db = Session()
    ihsg = models.Stock(ticker="^JKSE", name="IHSG", sector="Indeks")
    uji = models.Stock(ticker="TEST", name="Saham Uji", sector="Uji")
    db.add_all([ihsg, uji])
    db.commit()
    for hari, tutup in ((date(2026, 5, 21), 7000.0), (date(2026, 5, 22), 7100.0)):
        db.add(models.OHLCVDaily(stock_id=ihsg.id, date=hari, open=tutup, high=tutup,
                                 low=tutup, close=tutup, volume=1000, adj_close=tutup))
    db.commit()
    db.close()

    def override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    main.app.dependency_overrides[get_db] = override
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


@pytest.mark.parametrize("path", [
    "/stocks",
    "/stocks?ringkas=true",
    "/stocks/signals",
    "/stocks/ihsg",
    "/stocks/TEST/ohlcv",
    "/stocks/TEST/indicators",
])
def test_endpoint_pasar_boleh_disimpan(klien_db, path):
    res = klien_db.get(path)
    assert res.status_code == 200
    assert res.headers.get("cache-control") == CACHE_PASAR


def test_endpoint_non_pasar_tidak_ikut_disimpan(klien_db):
    """CACHE_PASAR hanya boleh menempel di lima endpoint pasar.

    Menggantikan tes lama atas /stocks/sync-status, yang dihapus 3 Sep 2026.
    /me membaca user, jadi jawabannya BERBEDA per pemanggil — kalau header
    `public` sampai bocor ke sini, cache bersama bisa menyajikan data satu user
    kepada user lain.
    """
    res = klien_db.get("/me")
    assert res.headers.get("cache-control") is None


def test_galat_tidak_ikut_disimpan(klien_db):
    """404 tak boleh dicache; ticker yang baru ditambahkan harus langsung terbaca."""
    res = klien_db.get("/stocks/TIDAKADA/ohlcv")
    assert res.status_code == 404
    assert res.headers.get("cache-control") is None


def test_nilai_cache_masuk_akal():
    """Jaga agar umur cache tak melampaui jeda polling frontend (5 menit)."""
    assert "public" in CACHE_PASAR
    assert "max-age=300" in CACHE_PASAR
    assert "stale-while-revalidate" in CACHE_PASAR
