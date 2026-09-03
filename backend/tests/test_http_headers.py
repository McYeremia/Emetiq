"""Tes lapisan HTTP: kompresi gzip dan urutan middleware.

Sengaja memakai endpoint yang TIDAK menyentuh database:
  • /openapi.json      — dihasilkan FastAPI sendiri, ~25 KB (di atas ambang kompresi)
  • /stocks/sync-status — membaca dict di memori, ~200 byte (di bawah ambang)

Dengan begitu tes ini tak bergantung pada isi basis data maupun pada
DATABASE_URL yang sedang aktif.
"""
from fastapi.testclient import TestClient

import main

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
    res = _client().get("/stocks/sync-status")
    assert res.status_code == 200
    assert len(res.content) < AMBANG, "prasyarat tes: sync-status harus < ambang"
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
