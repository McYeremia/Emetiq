"""Tes GET /stocks — bentuk respons dan jejak bacanya.

Endpoint ini kena tiap kali dashboard, overview, dan screener dimuat, jadi
biayanya dikali jumlah pengunjung — bukan sekali sehari seperti pekerjaan batch.
Sebelum diperbaiki ia menjalankan DUA query agregat terpisah ke ohlcv_daily,
masing-masing memindai seluruh tabel (797 ribu baris) hanya untuk mengambil dua
baris terakhir per saham, dan menarik 9 kolom padahal cuma date + close dipakai.

Tes bentuk di bawah sengaja ditulis sebelum refactor: bentuk respons TIDAK BOLEH
berubah, karena screener memfilter PE, PBV, dividend yield, dan market cap dari
payload yang sama.
"""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
import models
import main


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def client(engine):
    Factory = sessionmaker(bind=engine)

    def override_db():
        d = Factory()
        try:
            yield d
        finally:
            d.close()

    main.app.dependency_overrides[get_db] = override_db
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def _tambah(engine, ticker, harga_per_tanggal, **kolom):
    """harga_per_tanggal: list (selisih_hari_dari_hari_ini, close)."""
    s = sessionmaker(bind=engine)()
    stock = models.Stock(ticker=ticker, name=f"PT {ticker}", sector="Finance",
                         market_cap_cat="large", **kolom)
    s.add(stock)
    s.commit()
    for selisih, close in harga_per_tanggal:
        s.add(models.OHLCVDaily(
            stock_id=stock.id, date=date.today() - timedelta(days=selisih),
            open=close, high=close, low=close, close=close, volume=1_000,
        ))
    s.commit()
    s.close()


def _cari(data, ticker):
    return next(x for x in data if x["ticker"] == ticker)


# ── bentuk respons: dikunci, tak boleh bergeser ──────────────────────────────

def test_harga_dan_perubahan_dari_dua_baris_terakhir(engine, client):
    _tambah(engine, "BBCA", [(2, 100.0), (1, 110.0)])

    row = _cari(client.get("/stocks").json(), "BBCA")

    assert row["last_price"] == 110.0
    assert row["prev_close"] == 100.0
    assert row["change_pct"] == 10.0
    assert row["last_date"] == str(date.today() - timedelta(days=1))


def test_saham_dengan_data_basi_tetap_punya_harga(engine, client):
    """Penjagaan terpenting di berkas ini. Cara termudah mempercepat endpoint
    ini adalah membatasi query ke beberapa hari terakhir — dan itu akan
    MENGHAPUS harga 131 saham suspensi yang terakhir berdagang berbulan lalu."""
    _tambah(engine, "WSKT", [(400, 200.0), (399, 220.0)])

    row = _cari(client.get("/stocks").json(), "WSKT")

    assert row["last_price"] == 220.0
    assert row["prev_close"] == 200.0
    assert row["last_date"] == str(date.today() - timedelta(days=399))


def test_saham_satu_baris_tanpa_pembanding(engine, client):
    _tambah(engine, "BARU", [(1, 50.0)])

    row = _cari(client.get("/stocks").json(), "BARU")

    assert row["last_price"] == 50.0
    assert row["prev_close"] is None
    assert row["change_pct"] is None


def test_saham_tanpa_ohlcv(engine, client):
    _tambah(engine, "FREN", [])

    row = _cari(client.get("/stocks").json(), "FREN")

    assert row["last_price"] is None
    assert row["prev_close"] is None
    assert row["change_pct"] is None
    assert row["last_date"] is None


def test_field_fundamental_ikut_terkirim(engine, client):
    """Screener memfilter dari payload ini — hilang satu, halamannya rusak."""
    _tambah(engine, "TLKM", [(1, 300.0)], market_cap=1e12, pe_ratio=15.0,
            pbv_ratio=2.0, dividend_yield=4.5)

    row = _cari(client.get("/stocks").json(), "TLKM")

    assert row["market_cap"] == 1e12
    assert row["pe_ratio"] == 15.0
    assert row["pbv_ratio"] == 2.0
    assert row["dividend_yield"] == 4.5
    assert row["sector"] == "Finance"
    assert row["name"] == "PT TLKM"


# ── mode ringkas ─────────────────────────────────────────────────────────────
#
# Dashboard dan overview hanya menampilkan ticker, nama, harga, dan perubahan.
# Kolom fundamental hanya dipakai screener. Payload penuh 183 KB melintasi
# bandwidth Space gratis pada ~35 KB/detik — lima detik layar kosong — dan
# dashboard mengulangnya tiap kali polling.

def test_ringkas_hanya_mengirim_yang_ditampilkan(engine, client):
    """Dashboard dan overview hanya menyentuh empat field ini — sector,
    prev_close, dan last_date tak muncul sekali pun di kedua halaman."""
    _tambah(engine, "BBCA", [(2, 100.0), (1, 110.0)], market_cap=1e12,
            pe_ratio=15.0, pbv_ratio=2.0, dividend_yield=4.5)

    row = _cari(client.get("/stocks?ringkas=true").json(), "BBCA")

    assert set(row) == {"ticker", "name", "last_price", "change_pct"}
    assert row["ticker"] == "BBCA"
    assert row["name"] == "PT BBCA"
    assert row["last_price"] == 110.0
    assert row["change_pct"] == 10.0


def test_ringkas_tetap_menghitung_perubahan_dari_dua_baris(engine, client):
    """prev_close dibuang dari payload, tapi perubahan harian tetap dihitung
    di server dari dua baris terakhir — informasinya tidak hilang."""
    _tambah(engine, "WSKT", [(400, 200.0), (399, 220.0)])

    row = _cari(client.get("/stocks?ringkas=true").json(), "WSKT")

    assert row["last_price"] == 220.0
    assert row["change_pct"] == 10.0


def test_tanpa_ringkas_tetap_lengkap(engine, client):
    """Default TIDAK boleh berubah — screener bergantung padanya."""
    _tambah(engine, "TLKM", [(1, 300.0)], market_cap=1e12, pe_ratio=15.0,
            pbv_ratio=2.0, dividend_yield=4.5)

    row = _cari(client.get("/stocks").json(), "TLKM")

    assert row["market_cap"] == 1e12
    assert row["pe_ratio"] == 15.0


# ── jejak baca ───────────────────────────────────────────────────────────────

def _rekam_sql(engine, client):
    perintah = []

    @event.listens_for(engine, "before_cursor_execute")
    def rekam(conn, cursor, statement, parameters, context, executemany):
        perintah.append(statement)

    client.get("/stocks")
    event.remove(engine, "before_cursor_execute", rekam)
    return [s for s in perintah if "ohlcv_daily" in s and s.lstrip().startswith("SELECT")]


def test_ohlcv_dibaca_satu_kali(engine, client):
    _tambah(engine, "BBCA", [(2, 100.0), (1, 110.0)])

    baca = _rekam_sql(engine, client)

    assert len(baca) == 1, (
        f"ohlcv_daily dipindai {len(baca)} kali, harusnya cukup sekali:\n"
        + "\n\n".join(baca)
    )


def test_ohlcv_hanya_kolom_yang_dipakai(engine, client):
    """Respons hanya butuh date dan close. open/high/low/adj_close tak pernah
    dilihat, tapi ikut melintasi jaringan."""
    _tambah(engine, "BBCA", [(2, 100.0), (1, 110.0)])

    baca = _rekam_sql(engine, client)

    for s in baca:
        assert "ohlcv_daily.adj_close" not in s, f"adj_close ikut ditarik:\n{s}"
        assert "ohlcv_daily.open" not in s, f"open ikut ditarik:\n{s}"
