"""Penjaga untuk skor kecocokan & urutan hasil screening (Tahap 1 audit Advisor).

Tes screening yang sudah ada hanya memeriksa KEANGGOTAAN — apakah saham yang tak
memenuhi syarat tersaring keluar. Tak satu pun memeriksa URUTAN, dan itulah sebabnya
cacat berikut bisa hidup lama dengan 511 tes hijau:

  hasil diurutkan murni per kapitalisasi pasar, sehingga 15 kursi yang dikirim ke LLM
  selalu ditempati perusahaan terbesar — berapa pun jauh kandidat lain melampaui
  kriteria yang diketik user.

Berkas ini menuntut yang sebaliknya, plus menjaga dua perbaikan sekitarnya: indikator
selalu terisi, dan tertinggi/terendah 20 hari diambil dari kolom high/low.
"""
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
import models
from services.advisor import data_provider as dp, pipelines, scoring


# ── Fixture ──────────────────────────────────────────────────────────────────

def _saham(s, ticker, pe, div, mcap, sector="Finance"):
    st = models.Stock(ticker=ticker, name=f"PT {ticker}", sector=sector,
                      pe_ratio=pe, pbv_ratio=1.5, dividend_yield=div, market_cap=mcap)
    s.add(st)
    s.flush()
    return st


def _deret(s, stock, awal, langkah, n=90):
    """Deret harga naik dengan riak kecil supaya RSI tidak mentok 100."""
    d0 = date.today() - timedelta(days=n)
    for i in range(n):
        riak = 3 if i % 3 == 0 else -1
        harga = awal + langkah * i + riak
        s.add(models.OHLCVDaily(
            stock_id=stock.id, date=d0 + timedelta(days=i),
            open=harga, high=harga * 1.08, low=harga * 0.94, close=harga, volume=1_000_000,
        ))


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()

    # Raksasa dengan fundamental biasa vs emiten kecil yang jauh lebih unggul di
    # kriteria. Sebelum perbaikan, raksasa SELALU menang hanya karena kapitalisasi.
    besar = _saham(s, "BESAR", pe=12.0, div=3.2, mcap=1_000_000_000_000_000)
    kecil = _saham(s, "KECIL", pe=4.0, div=9.0, mcap=500_000_000_000)
    _deret(s, besar, awal=9000, langkah=5)
    _deret(s, kecil, awal=200, langkah=2)
    s.commit()
    yield s
    s.close()


# ── E3: urutan wajib menghormati kriteria, bukan kapitalisasi ────────────────

def test_urutan_menghormati_kriteria_bukan_kapitalisasi(db):
    """Saham ber-PE 4 harus mengalahkan raksasa ber-PE 12 saat user minta PE rendah.

    Inilah penjaga utama berkas ini. Kalau tes ini merah, kemungkinan besar urutan
    kembali ditentukan `market_cap` dan jawaban screening kembali seragam.
    """
    hasil = dp.screen(db, pe_max=15)
    urutan = [c["ticker"] for c in hasil]
    assert urutan[0] == "KECIL", f"KECIL (PE 4) harus di puncak, dapatnya {urutan}"


def test_skor_kecocokan_ikut_dikembalikan(db):
    hasil = dp.screen(db, pe_max=15)
    assert all(isinstance(c["match_score"], (int, float)) for c in hasil)
    # Terurut menurun
    skor = [c["match_score"] for c in hasil]
    assert skor == sorted(skor, reverse=True)


def test_dividen_tinggi_menang_saat_dividen_yang_diminta(db):
    hasil = dp.screen(db, div_min=3.0)
    assert hasil[0]["ticker"] == "KECIL", "dividen 9% harus mengalahkan 3,2%"


def test_tanpa_kriteria_angka_kualitas_dan_likuiditas_yang_menentukan(db):
    """Tanpa kriteria bernilai angka tak ada yang bisa dicocokkan, jadi bobotnya
    dibagikan ke tren/RSI/likuiditas — di situ raksasa memang pantas menang."""
    hasil = dp.screen(db)
    assert hasil[0]["ticker"] == "BESAR"


# ── A2: indikator tak boleh kosong walau tak difilter ────────────────────────

def test_indikator_terisi_walau_tanpa_filter_teknikal(db):
    """Dulu rsi/trend dikirim None ke LLM kecuali user memfilternya — padahal prompt
    mewajibkan alasan teknikal. Model lalu terjepit antara mengarang dan menyerah."""
    hasil = dp.screen(db, pe_max=15)
    assert hasil, "fixture harus menghasilkan kandidat"
    for c in hasil:
        assert c["rsi"] is not None, f"{c['ticker']} tak punya RSI"
        assert c["trend"] is not None, f"{c['ticker']} tak punya tren"


def test_indikator_terisi_tanpa_kriteria_sama_sekali(db):
    for c in dp.screen(db):
        assert c["rsi"] is not None and c["trend"] is not None


# ── A4: tertinggi/terendah 20 hari dari kolom high/low ───────────────────────

def test_high_low_20d_dari_kolom_high_low_bukan_close(db):
    """`high_20d` dipakai LLM sebagai resistance untuk menyarankan take-profit.
    Menghitungnya dari close membuat taksirannya sistematis terlalu rendah."""
    a = dp.analyze(db, "BESAR")
    stock = db.query(models.Stock).filter(models.Stock.ticker == "BESAR").first()
    rows = (db.query(models.OHLCVDaily)
            .filter(models.OHLCVDaily.stock_id == stock.id)
            .order_by(models.OHLCVDaily.date.desc()).limit(20).all())

    assert a["high_20d"] == pytest.approx(max(r.high for r in rows), rel=1e-6)
    assert a["low_20d"] == pytest.approx(min(r.low for r in rows), rel=1e-6)
    # Dan benar-benar berbeda dari versi lama yang memakai close
    assert a["high_20d"] > max(r.close for r in rows)
    assert a["low_20d"] < min(r.close for r in rows)


# ── Unit: komponen skor ──────────────────────────────────────────────────────

def test_margin_kriteria_makin_jauh_melampaui_makin_tinggi():
    f = {"pe_max": 15.0}
    murah = scoring.margin_kriteria({"pe": 4.0}, f)
    mepet = scoring.margin_kriteria({"pe": 14.0}, f)
    assert murah > mepet
    assert 0.0 <= mepet < murah <= 1.0


def test_margin_kriteria_none_bila_hanya_kriteria_kategorikal():
    """sector/rsi/trend sudah disaring keras; menilainya lagi = hitung ganda."""
    assert scoring.margin_kriteria({"pe": 9.0}, {"sector": "Finance"}) is None
    assert scoring.margin_kriteria({"pe": 9.0}, {}) is None


def test_margin_kriteria_abaikan_batas_harga():
    """price_max/price_min itu batasan anggaran, bukan pernyataan kualitas."""
    assert scoring.margin_kriteria({"pe": 9.0, "last_price": 100}, {"price_max": 5000}) is None


def test_skor_rsi_menghukum_jenuh_beli_paling_berat():
    assert scoring.skor_rsi(50) == 1.00          # sehat
    assert scoring.skor_rsi(85) < scoring.skor_rsi(25)   # jenuh beli < jenuh jual
    assert scoring.skor_rsi(25) < scoring.skor_rsi(50)   # jenuh jual bukan yang terbaik
    assert scoring.skor_rsi(None) == 0.5


def test_skor_tren():
    assert scoring.skor_tren("up") == 1.0
    assert scoring.skor_tren("down") == 0.0
    assert scoring.skor_tren(None) == 0.5


def test_skor_likuiditas_skala_log_dan_aman_terhadap_none():
    assert scoring.skor_likuiditas(None) == 0.0
    assert scoring.skor_likuiditas(0) == 0.0
    assert scoring.skor_likuiditas(10 ** 11) == 0.0        # di bawah lantai
    assert scoring.skor_likuiditas(10 ** 16) == 1.0        # di atas atap
    assert 0.0 < scoring.skor_likuiditas(10 ** 13) < 1.0


def test_skor_kecocokan_selalu_dalam_rentang_0_100():
    ekstrem = [
        {"pe": 0.1, "pbv": 0.1, "dividend_yield": 99.0, "trend": "up",
         "rsi": 50, "market_cap": 10 ** 18},
        {"pe": None, "pbv": None, "dividend_yield": None, "trend": None,
         "rsi": None, "market_cap": None},
    ]
    for c in ekstrem:
        for f in ({"pe_max": 15.0, "div_min": 3.0}, {}):
            assert 0.0 <= scoring.skor_kecocokan(c, f) <= 100.0


def test_kapitalisasi_tidak_lagi_bisa_menutup_kriteria():
    """Raksasa yang cuma mepet lolos tak boleh mengalahkan emiten kecil yang unggul jauh."""
    f = {"pe_max": 15.0}
    raksasa = {"pe": 14.5, "trend": "up", "rsi": 50, "market_cap": 10 ** 16}
    kecil = {"pe": 3.0, "trend": "up", "rsi": 50, "market_cap": 10 ** 12}
    assert scoring.skor_kecocokan(kecil, f) > scoring.skor_kecocokan(raksasa, f)


# ── A6 & A7: kebersihan konteks dan kejujuran pemangkasan ────────────────────

def test_tanpa_alasan_membuang_reason_saja():
    masuk = [{"ticker": "BBRI", "score": 80, "reason": "panjang sekali",
              "key_numbers": {"pe": 9}}]
    keluar = pipelines._tanpa_alasan(masuk)
    assert keluar == [{"ticker": "BBRI", "score": 80, "key_numbers": {"pe": 9}}]
    assert "reason" in masuk[0], "input tidak boleh dimutasi"


def test_catatan_pemangkasan_muncul_hanya_saat_dipangkas():
    assert "10" in pipelines._catatan_pemangkasan(10, 5)
    assert pipelines._catatan_pemangkasan(3, 3) == ""
    assert pipelines._catatan_pemangkasan(None, 5) == ""
    assert pipelines._catatan_pemangkasan("bukan angka", 5) == ""
