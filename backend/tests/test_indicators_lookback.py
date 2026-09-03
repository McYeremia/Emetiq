"""Batas baris indikator tak boleh menghapus MA_200 — juga untuk saham suspensi.

Lahir dari dua kesalahan berurutan saat Tahap 2 optimalisasi (3 Sep 2026), dan
keduanya layak diingat.

Kesalahan pertama: `calculate_indicators` diberi batas berbasis TANGGAL (400 hari
kalender) supaya berhenti menarik seluruh riwayat dari Postgres remote. Diukur pada
data nyata, jendela itu cuma memuat 197 hari bursa — satu langkah di bawah 200 yang
dibutuhkan MA_200 — dan MA_200 jadi None untuk 8 dari 8 saham yang diperiksa.
Kegagalannya SENYAP: `ta` memulangkan NaN, `_last()` mengubahnya jadi None, endpoint
tetap membalas HTTP 200, dan panel indikator cuma menampilkan "-".

Kesalahan kedua: tes pertama untuk regresi itu memakai 600 hari kerja BERURUTAN,
sehingga jendela 400 hari selalu kebagian ~285 baris dan tesnya lolos. Tes yang tak
bisa gagal tidak menjaga apa pun.

Akar masalahnya ternyata bukan besar-kecilnya angka, melainkan batas berbasis
tanggal itu sendiri: ~131 saham di IDX terakhir berdagang berbulan lalu, dan bagi
mereka jendela tanggal mana pun bisa kosong. Karena itu batasnya sekarang JUMLAH
BARIS. `test_saham_suspensi_tetap_punya_indikator` adalah tes yang akan gagal kalau
seseorang mengembalikannya ke basis tanggal.
"""
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
import models
from services.indicators import (
    INDICATOR_MAX_ROWS,
    calculate_indicators,
    calculate_indicators_from_df,
    get_ohlcv_df,
)

_JUMLAH_BARIS = 600


def _buat_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _semai(db, ticker: str, jumlah: int, berakhir: date) -> models.Stock:
    """Saham dengan `jumlah` hari bursa berurutan yang berakhir di `berakhir`.

    Harganya berayun, bukan garis lurus: deret konstan membuat sebagian indikator
    jadi NaN karena alasan yang tak ada hubungannya dengan batas baris.
    """
    stock = models.Stock(ticker=ticker, name=f"Uji {ticker}", sector="Uji")
    db.add(stock)
    db.commit()

    hari, tanggal = berakhir, []
    while len(tanggal) < jumlah:
        if hari.weekday() < 5:
            tanggal.append(hari)
        hari -= timedelta(days=1)
    tanggal.reverse()

    for i, t in enumerate(tanggal):
        harga = 1000.0 + i * 0.5 + (i % 17) * 3.0
        db.add(models.OHLCVDaily(
            stock_id=stock.id, date=t,
            open=harga, high=harga * 1.01, low=harga * 0.99,
            close=harga, volume=100_000 + i, adj_close=harga,
        ))
    db.commit()
    return stock


@pytest.fixture
def saham_aktif():
    db = _buat_db()
    yield db, _semai(db, "AKTIF", _JUMLAH_BARIS, date.today())
    db.close()


@pytest.fixture
def saham_suspensi():
    """Terakhir berdagang DUA TAHUN lalu — seperti ~131 saham suspensi di IDX."""
    db = _buat_db()
    yield db, _semai(db, "SUSPEN", _JUMLAH_BARIS, date.today() - timedelta(days=730))
    db.close()


def test_batas_memuat_lebih_dari_200_baris():
    """Syarat keras MA_200. Di bawah ini, MA_200 diam-diam jadi None."""
    assert INDICATOR_MAX_ROWS > 200


def test_ma200_tidak_hilang(saham_aktif):
    db, stock = saham_aktif
    assert calculate_indicators(db, stock).get("MA_200") is not None


def test_saham_suspensi_tetap_punya_indikator(saham_suspensi):
    """INI tes yang menangkap batas berbasis tanggal.

    Sahamnya terakhir berdagang dua tahun lalu. Batas "N hari terakhir" akan
    memulangkan nol baris dan seluruh indikatornya lenyap; batas "N baris terakhir"
    tetap memberi hasil yang sama seperti riwayat penuh.
    """
    db, stock = saham_suspensi

    baris = len(get_ohlcv_df(db, stock.id, INDICATOR_MAX_ROWS))
    assert baris == INDICATOR_MAX_ROWS, (
        f"Saham suspensi cuma memberi {baris} baris — batasnya kemungkinan "
        "kembali berbasis tanggal, bukan jumlah baris."
    )
    assert calculate_indicators(db, stock).get("MA_200") is not None


@pytest.mark.parametrize("nama_fixture", ["saham_aktif", "saham_suspensi"])
def test_hasilnya_sama_dengan_riwayat_penuh(nama_fixture, request):
    """Dibandingkan pada 2 desimal — presisi yang benar-benar ditampilkan UI.

    EMA rekursif sejak batang pertama, jadi jendela lebih pendek menggeser MACD di
    desimal ke-4. Itu tak pernah sampai ke layar dan bukan yang dijaga tes ini.
    """
    db, stock = request.getfixturevalue(nama_fixture)

    def dibulatkan(d):
        return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in d.items()}

    penuh = calculate_indicators_from_df(get_ohlcv_df(db, stock.id))
    dibatasi = calculate_indicators(db, stock)

    assert dibulatkan(penuh) == dibulatkan(dibatasi)


def test_urutannya_tetap_menaik(saham_aktif):
    """Batas baris mengambil N TERBARU (urut menurun) lalu membalik urutannya.

    Kalau pembalikan itu hilang, seluruh indikator dihitung mundur dan hasilnya
    tetap berupa angka yang tampak masuk akal — jenis kerusakan yang paling sulit
    terlihat.
    """
    db, stock = saham_aktif
    tanggal = list(get_ohlcv_df(db, stock.id, INDICATOR_MAX_ROWS).index)
    assert tanggal == sorted(tanggal)


def test_riwayat_penuh_tetap_bawaan(saham_aktif):
    """Backtester memanggil get_ohlcv_df tanpa batas dan BUTUH semuanya.

    Kalau bawaannya suatu saat diberi batas, backtest jangka panjang akan diam-diam
    memendek dan metriknya berubah tanpa ada yang menyadari.
    """
    db, stock = saham_aktif
    assert len(get_ohlcv_df(db, stock.id)) == _JUMLAH_BARIS
