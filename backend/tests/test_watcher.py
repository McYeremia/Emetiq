"""Tes services/watcher — khususnya jejak baca scan_market_signals.

scan_market_signals dipanggil di akhir tiap daily_sync. Sebelum dibatasi, ia
menarik SELURUH riwayat harga tiap saham tanpa batas: 797.487 baris dalam satu
run, padahal indikator terpanjang yang dihitung hanya MA200. Batasnya mengikuti
konvensi screen_by_strategy di berkas yang sama — 700 hari kalender.
"""
import pytest
import pandas as pd
from datetime import date, timedelta
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
import models
import services.watcher as watcher


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=eng)
    return eng


def _saham_dengan_riwayat(session, ticker="BBCA", hari=800, awal=1000.0):
    """Tren naik landai — cukup untuk memicu defensive-bull (ma50 > ma200, rsi > 50)."""
    stock = models.Stock(ticker=ticker, name=ticker, sector="Finance", market_cap_cat="large")
    session.add(stock)
    session.commit()

    hari_ini = date.today()
    for i in range(hari):
        harga = awal + i * 2.0
        session.add(models.OHLCVDaily(
            stock_id=stock.id,
            date=hari_ini - timedelta(days=hari - 1 - i),
            open=harga, high=harga + 5, low=harga - 5, close=harga,
            volume=1_000_000,
        ))
    session.commit()
    return stock


def _jalankan(engine, mocker):
    """Jalankan scan_market_signals di atas engine tes, bukan DB sungguhan."""
    Sesi = sessionmaker(bind=engine)
    mocker.patch("database.SessionLocal", Sesi)
    return watcher.scan_market_signals()


def test_scan_market_signals_membatasi_rentang_tanggal(engine, mocker):
    """Query OHLCV harus punya batas bawah tanggal. Tanpa itu, satu run daily_sync
    menyeret seluruh tabel harga melintasi jaringan."""
    sesi = sessionmaker(bind=engine)()
    _saham_dengan_riwayat(sesi, hari=800)
    sesi.close()

    perintah = []

    @event.listens_for(engine, "before_cursor_execute")
    def rekam(conn, cursor, statement, parameters, context, executemany):
        perintah.append(statement)

    _jalankan(engine, mocker)

    baca_ohlcv = [s for s in perintah if "FROM ohlcv_daily" in s and "SELECT" in s]
    assert baca_ohlcv, "tak ada query ke ohlcv_daily — tes salah sasaran"
    assert all("ohlcv_daily.date >=" in s for s in baca_ohlcv), (
        "ada query ohlcv_daily tanpa batas tanggal:\n" + "\n".join(baca_ohlcv)
    )


def test_scan_market_signals_masih_mengenali_strategi_ma200(engine, mocker):
    """Penjagaan atas permintaan pemilik: pemangkasan tidak boleh merusak data
    yang disajikan. Jendela harus tetap cukup panjang untuk MA200."""
    sesi = sessionmaker(bind=engine)()
    _saham_dengan_riwayat(sesi, hari=800)
    sesi.close()

    _jalankan(engine, mocker)

    periksa = sessionmaker(bind=engine)()
    strategi = {s.strategy_id for s in periksa.query(models.Signal).all()}
    periksa.close()

    assert "defensive-bull" in strategi, (
        f"strategi ber-MA200 hilang — jendela terlalu pendek. Yang muncul: {strategi}"
    )


def test_scan_market_signals_melewati_saham_terlalu_pendek(engine, mocker):
    """Saham baru dengan riwayat < 50 baris tak boleh menghasilkan sinyal."""
    sesi = sessionmaker(bind=engine)()
    _saham_dengan_riwayat(sesi, ticker="BARU", hari=30)
    sesi.close()

    _jalankan(engine, mocker)

    periksa = sessionmaker(bind=engine)()
    jumlah = periksa.query(models.Signal).count()
    periksa.close()

    assert jumlah == 0
