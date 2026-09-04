"""Saham berdata sangat sedikit tak boleh menjatuhkan endpoint indikator.

Temuan §10 butir 7 audit optimalisasi (3 Sep 2026), ditemukan tak sengaja lewat
fixture tes auth yang cuma punya satu baris OHLCV.

`ta` 0.11.0 tidak seragam ketika deretnya lebih pendek dari jendela indikator:
SMA, EMA, RSI, MACD, Bollinger, dan Stochastic memulangkan NaN — yang `_last()`
ubah jadi None — tapi `AverageTrueRange` menulis ke `atr[window - 1]` tanpa
memeriksa panjang deret dan melempar `IndexError`.

Akibatnya ganjil: 0 baris AMAN (dijaga `df.empty` di awal fungsi), tapi 1 sampai
13 baris membuat `GET /stocks/{ticker}/indicators` membalas **500**.

Yang dijaga berkas ini bukan cuma ATR. `test_semua_panjang_deret_aman` memanggil
seluruh perhitungan untuk tiap panjang 1-13, jadi indikator baru yang punya cacat
yang sama akan ketahuan di sini, bukan di produksi.
"""
from datetime import date, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
import main
import models
from services.indicators import calculate_indicators_from_df

# Jendela indikator terpanjang yang MELEMPAR, bukan memulangkan NaN. Di bawah
# angka ini dulunya IndexError; tepat di angka ini ATR_14 mulai punya nilai.
_AMBANG_ATR = 14


def _df(jumlah: int) -> pd.DataFrame:
    """OHLCV sintetis sepanjang `jumlah` baris, harga berayun (bukan garis lurus).

    Deret konstan membuat sebagian indikator NaN karena alasan yang tak ada
    hubungannya dengan panjang deret — itu akan mengaburkan apa yang diuji.
    """
    harga = [1000.0 + i * 2 + (i % 5) * 3.0 for i in range(jumlah)]
    return pd.DataFrame(
        {
            "open": harga,
            "high": [h * 1.01 for h in harga],
            "low": [h * 0.99 for h in harga],
            "close": harga,
            "volume": [100_000.0 + i for i in range(jumlah)],
        },
        index=pd.date_range("2026-01-01", periods=jumlah),
    )


@pytest.mark.parametrize("jumlah", list(range(1, _AMBANG_ATR)))
def test_semua_panjang_deret_aman(jumlah):
    """1 sampai 13 baris: harus memulangkan dict, bukan melempar."""
    hasil = calculate_indicators_from_df(_df(jumlah))
    assert isinstance(hasil, dict)


def test_bentuk_balasannya_tetap_sama():
    """Kunci untuk deret pendek harus SAMA dengan deret panjang.

    Kalau deret pendek memulangkan dict kosong, panel indikator di frontend
    kehilangan barisnya sama sekali alih-alih menampilkan "-" seperti saham lain
    yang datanya belum cukup.
    """
    assert calculate_indicators_from_df(_df(13)).keys() == \
           calculate_indicators_from_df(_df(60)).keys()


def test_yang_belum_bisa_dihitung_bernilai_none():
    """13 baris tak cukup untuk ATR_14 — jawabannya None, bukan galat."""
    assert calculate_indicators_from_df(_df(13))["ATR_14"] is None


def test_atr_tetap_terisi_begitu_datanya_cukup():
    """Penjaga arah sebaliknya: jangan sampai perbaikannya mematikan ATR."""
    assert calculate_indicators_from_df(_df(_AMBANG_ATR))["ATR_14"] is not None


def test_deret_kosong_tetap_dict_kosong():
    """Kontrak lama yang tak boleh ikut berubah: 0 baris -> {}."""
    assert calculate_indicators_from_df(pd.DataFrame()) == {}


@pytest.fixture
def klien_dengan_saham_berdata_satu_baris():
    """Saham nyata di DB dengan tepat SATU baris harga — bentuk yang bikin 500."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Factory = sessionmaker(bind=engine)

    s = Factory()
    saham = models.Stock(ticker="BARU", name="Saham Baru Melantai", sector="Uji")
    s.add(saham)
    s.flush()
    s.add(models.OHLCVDaily(stock_id=saham.id, date=date.today() - timedelta(days=1),
                            open=100.0, high=110.0, low=95.0, close=105.0, volume=5_000))
    s.commit()
    s.close()

    def override_db():
        db = Factory()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = override_db
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_endpoint_indicators_tidak_balas_500(klien_dengan_saham_berdata_satu_baris):
    """Regresi sesungguhnya: saham yang baru melantai membalas 200, bukan 500."""
    r = klien_dengan_saham_berdata_satu_baris.get("/stocks/BARU/indicators")

    assert r.status_code == 200, r.text
    isi = r.json()
    assert isi["ticker"] == "BARU"
    assert isi["indicators"]["ATR_14"] is None
