"""Tes pemilihan jendela tarik di `scripts/daily_sync.py`.

Mode `penuh` adalah pengganti `POST /stocks/refresh` yang dihapus 3 Sep 2026.
Kalau ia diam-diam berperilaku seperti mode `harian`, kemampuan menambal lubang
hilang tanpa ada yang tahu — dan baru ketahuan saat cron benar-benar mati
berhari-hari, yaitu saat paling buruk untuk menemukannya.

Yang diuji di sini murni **jendela tarik yang diminta ke yfinance**, bukan
penyimpanannya: `fetch_ohlcv` diganti perekam argumen, jadi tak ada jaringan dan
tak ada tulisan ke basis data.
"""
from datetime import date, timedelta

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
import models
import services.data_fetcher as fetcher
import services.watcher as watcher
import scripts.daily_sync as ds


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def panggilan(engine, monkeypatch):
    """Pasang DB in-memory, bungkam jaringan, dan rekam tiap panggilan fetch."""
    Factory = sessionmaker(bind=engine)
    monkeypatch.setattr(ds, "engine", engine)
    monkeypatch.setattr(ds, "SessionLocal", Factory)

    rekaman = []

    def fetch_palsu(ticker, period=None, start=None):
        rekaman.append({"ticker": ticker, "period": period, "start": start})
        return pd.DataFrame()          # kosong: save_ohlcv tak akan dipanggil

    monkeypatch.setattr(fetcher, "fetch_ohlcv", fetch_palsu)
    monkeypatch.setattr(fetcher, "update_stock_fundamentals", lambda db, s: None)
    monkeypatch.setattr(watcher, "scan_market_signals", lambda: 0)
    return Factory, rekaman


def _saham(Factory, ticker: str, tanggal_terakhir: date | None):
    s = Factory()
    st = models.Stock(ticker=ticker, name=ticker, sector="Finance")
    s.add(st)
    s.flush()
    if tanggal_terakhir is not None:
        s.add(models.OHLCVDaily(stock_id=st.id, date=tanggal_terakhir,
                                open=100, high=100, low=100, close=100, volume=1))
    s.commit()
    s.close()


def test_mode_harian_selalu_lima_hari(panggilan):
    Factory, rekaman = panggilan
    _saham(Factory, "BBRI", date.today() - timedelta(days=90))

    ds.run_daily_sync(ds.MODE_HARIAN)

    assert rekaman == [{"ticker": "BBRI", "period": "5d", "start": None}]


def test_mode_penuh_menarik_dari_tanggal_terakhir(panggilan):
    """Inti kemampuannya: lubang 90 hari harus diminta seluruhnya, bukan 5 hari.

    Ini yang TIDAK bisa dilakukan mode harian — `period="5d"` selalu dihitung dari
    hari ini, jadi 85 hari di tengah tak pernah tersentuh lagi.
    """
    Factory, rekaman = panggilan
    terakhir = date.today() - timedelta(days=90)
    _saham(Factory, "BBRI", terakhir)

    ds.run_daily_sync(ds.MODE_PENUH)

    assert rekaman == [{"ticker": "BBRI", "period": None, "start": terakhir}]


def test_mode_penuh_saham_tanpa_riwayat_ditarik_penuh(panggilan):
    """Tanpa satu baris pun harga, tak ada tanggal mulai — biarkan default 5 tahun."""
    Factory, rekaman = panggilan
    _saham(Factory, "BARU", None)

    ds.run_daily_sync(ds.MODE_PENUH)

    assert rekaman == [{"ticker": "BARU", "period": None, "start": None}]


def test_mode_penuh_mengabaikan_tanggal_di_masa_depan(panggilan):
    """Tanggal terakhir di masa depan (jam mesin melenceng / data rusak) akan
    membuat yfinance mengembalikan kosong dan saham itu terlewat diam-diam.
    Jatuhkan ke tarikan penuh, jangan ke jendela kosong."""
    Factory, rekaman = panggilan
    _saham(Factory, "ANEH", date.today() + timedelta(days=7))

    ds.run_daily_sync(ds.MODE_PENUH)

    assert rekaman == [{"ticker": "ANEH", "period": None, "start": None}]


def test_tanggal_terakhir_diambil_satu_query_bukan_per_saham(engine, panggilan):
    """Versi N+1-nya menembak Supabase sekali per saham hanya untuk memilih tanggal
    mulai — ~740 query tambahan di jalur yang sudah panjang."""
    from sqlalchemy import event

    Factory, _ = panggilan
    for t in ("AAAA", "BBBB", "CCCC"):
        _saham(Factory, t, date.today() - timedelta(days=10))

    perintah = []

    @event.listens_for(engine, "before_cursor_execute")
    def rekam(conn, cursor, statement, parameters, context, executemany):
        perintah.append(statement)

    ds.run_daily_sync(ds.MODE_PENUH)

    agregat = [p for p in perintah if "max(" in p.lower()]
    assert len(agregat) == 1, f"harusnya satu query agregat, dapat {len(agregat)}"
