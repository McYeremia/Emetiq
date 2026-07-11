"""Tes services/bigmoney/positions — masuk, bertahan, dan keluar.

Inti masalah yang dipecahkan: peringkat harian berganti 6-9 nama tiap hari, sehingga
perkembangan sebuah akumulasi mustahil diikuti. Posisi harus BERTAHAN meski peringkat
hariannya jatuh, dan keluar hanya ketika distribusinya nyata — dibandingkan dengan
akumulasinya sendiri, bukan dengan skor.
"""
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import Base
from services.bigmoney.positions import update_positions

D0 = date(2026, 7, 1)


def hari(n: int) -> date:
    return D0 + timedelta(days=n)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _hari_bursa(db, d: date, ticker: str, *, foreign_net: int, foreign_net_value: int,
                close: float = 1000.0, composite: float = 70.0, phase: str = "AKUMULASI"):
    """Satu hari: baris harian IDX + skornya."""
    db.add(models.BigMoneyStockDaily(
        date=d, ticker=ticker, close=close, volume=1_000_000, value=2_000_000_000,
        change_pct=0.5, foreign_net=foreign_net, foreign_net_value=foreign_net_value,
        avg_ticket=1_000_000.0, foreign_buy=max(foreign_net, 0), foreign_sell=max(-foreign_net, 0)))
    db.add(models.BigMoneyScore(
        date=d, ticker=ticker, composite=composite, conviction="WATCH" if composite >= 55 else "WEAK",
        phase=phase, weight_set="CALM", days_confirmed=3,
        flags={"divergence": False, "pump_dump_risk": False}))
    db.commit()


def _akumulasi(db, ticker: str, hari_ke: list[int], *, nilai: int = 5_000_000_000,
               close: float = 1000.0, composite: float = 70.0):
    """Beli bersih di hari-hari tertentu; hari lain net jual kecil."""
    for n in range(max(hari_ke) + 1):
        beli = n in hari_ke
        _hari_bursa(db, hari(n), ticker,
                    foreign_net=1000 if beli else -100,
                    foreign_net_value=nilai if beli else -200_000_000,
                    close=close, composite=composite)


def _jalankan(db, sampai: int):
    for n in range(sampai + 1):
        update_positions(hari(n), db)


def _posisi(db, ticker: str) -> models.BigMoneyPosition | None:
    return (db.query(models.BigMoneyPosition)
              .filter_by(ticker=ticker)
              .order_by(models.BigMoneyPosition.id.desc())
              .first())


# --- masuk -------------------------------------------------------------------

def test_opens_after_three_buy_days_in_five(db):
    """Syarat masuk: asing net beli >= 3 dari 5 hari terakhir DAN skor >= 55."""
    _akumulasi(db, "AAAA", [0, 1, 2])
    _jalankan(db, 2)

    posisi = _posisi(db, "AAAA")

    assert posisi is not None
    assert posisi.status == "ACTIVE"
    assert posisi.opened_on == hari(2)
    assert posisi.entry_close == 1000.0


def test_does_not_open_on_a_single_spike(db):
    """Satu hari lonjakan bukan akumulasi. Ini persis kebisingan yang ingin dihindari."""
    _akumulasi(db, "AAAA", [2], nilai=90_000_000_000)
    _jalankan(db, 2)

    assert _posisi(db, "AAAA") is None


def test_does_not_open_when_score_too_low(db):
    """Asing beli tiga hari tapi skornya lemah — belum layak dilacak."""
    _akumulasi(db, "AAAA", [0, 1, 2], composite=40.0)
    _jalankan(db, 2)

    assert _posisi(db, "AAAA") is None


def test_does_not_open_twice_for_the_same_stock(db):
    _akumulasi(db, "AAAA", [0, 1, 2, 3, 4])
    _jalankan(db, 4)

    assert db.query(models.BigMoneyPosition).filter_by(ticker="AAAA", status="ACTIVE").count() == 1


# --- bertahan ----------------------------------------------------------------

def test_survives_a_drop_in_daily_rank(db):
    """Inti fitur ini: posisi TIDAK keluar hanya karena skor hariannya jatuh.

    Skor 30 berarti ia lenyap dari peringkat harian — tapi akumulasinya utuh, jadi
    posisinya harus tetap berjalan.
    """
    _akumulasi(db, "AAAA", [0, 1, 2])
    _jalankan(db, 2)

    for n in (3, 4, 5):
        _hari_bursa(db, hari(n), "AAAA", foreign_net=50, foreign_net_value=100_000_000,
                    composite=30.0, phase="NETRAL")
        update_positions(hari(n), db)

    posisi = _posisi(db, "AAAA")

    assert posisi.status == "ACTIVE"
    assert posisi.last_score == 30.0   # peringkat harian jatuh, posisi tetap berdiri


def test_position_carries_the_accumulation_that_justified_entry(db):
    """Posisi dibuka dengan MEMBAWA akumulasi jendela masuknya, bukan dari nol.

    Akumulasi itu sudah terjadi — justru itulah alasan ia masuk. Memulai dari nol
    membuat satu hari jual kecil langsung mematikannya, padahal asing masih untung
    besar sejak awal.

    Jendela hari 0-2: 3 hari beli @ Rp5 miliar = Rp15 miliar.
    """
    _akumulasi(db, "AAAA", [0, 1, 2], nilai=5_000_000_000, close=1000.0)
    _jalankan(db, 2)

    posisi = _posisi(db, "AAAA")

    assert posisi.accumulated_value == 15_000_000_000
    assert posisi.peak_value == 15_000_000_000
    assert posisi.inflow_days == 3


def test_tracks_progress_since_entry(db):
    """Yang ingin dilihat pengguna: sudah berapa lama, dana masuk berapa, harga ke mana."""
    _akumulasi(db, "AAAA", [0, 1, 2], nilai=5_000_000_000, close=1000.0)
    _jalankan(db, 2)

    _hari_bursa(db, hari(3), "AAAA", foreign_net=1000, foreign_net_value=3_000_000_000, close=1100.0)
    update_positions(hari(3), db)

    posisi = _posisi(db, "AAAA")

    assert posisi.accumulated_value == 18_000_000_000   # 15 miliar jendela + 3 miliar hari ini
    assert posisi.inflow_days == 4
    assert posisi.last_close == 1100.0
    assert posisi.entry_close == 1000.0                 # +10% sejak masuk


# --- keluar ------------------------------------------------------------------

def test_closes_when_outflow_exceeds_half_of_inflow(db):
    """Aturan Anda: keluarnya dibandingkan dengan akumulasinya sendiri.

    Puncak Rp25 miliar (15 jendela + 10 hari ke-3), lalu keluar Rp14 miliar
    (56% > 50%) → posisi ditutup.
    """
    _akumulasi(db, "AAAA", [0, 1, 2])
    _jalankan(db, 2)

    _hari_bursa(db, hari(3), "AAAA", foreign_net=2000, foreign_net_value=10_000_000_000)
    update_positions(hari(3), db)
    assert _posisi(db, "AAAA").peak_value == 25_000_000_000

    _hari_bursa(db, hari(4), "AAAA", foreign_net=-2800, foreign_net_value=-14_000_000_000,
                phase="NETRAL")
    update_positions(hari(4), db)

    posisi = _posisi(db, "AAAA")

    assert posisi.status == "CLOSED"
    assert posisi.close_reason == "OUTFLOW"
    assert posisi.closed_on == hari(4)


def test_stays_open_when_outflow_is_moderate(db):
    """Keluar Rp5 miliar dari puncak Rp25 miliar (20%) masih wajar — jangan gugup."""
    _akumulasi(db, "AAAA", [0, 1, 2])
    _jalankan(db, 2)

    _hari_bursa(db, hari(3), "AAAA", foreign_net=2000, foreign_net_value=10_000_000_000)
    update_positions(hari(3), db)

    _hari_bursa(db, hari(4), "AAAA", foreign_net=-1000, foreign_net_value=-5_000_000_000,
                phase="NETRAL")
    update_positions(hari(4), db)

    assert _posisi(db, "AAAA").status == "ACTIVE"


def test_closes_after_two_consecutive_distribution_days(db):
    """Distribusi beruntun adalah tanda ganti tangan, meski nilainya belum besar."""
    _akumulasi(db, "AAAA", [0, 1, 2])
    _jalankan(db, 2)

    for n in (3, 4):
        _hari_bursa(db, hari(n), "AAAA", foreign_net=-500, foreign_net_value=-500_000_000,
                    phase="DISTRIBUSI")
        update_positions(hari(n), db)

    posisi = _posisi(db, "AAAA")

    assert posisi.status == "CLOSED"
    assert posisi.close_reason == "DISTRIBUSI"


def test_one_distribution_day_does_not_close(db):
    """Satu hari jual bisa saja ambil untung — bukan bukti distribusi."""
    _akumulasi(db, "AAAA", [0, 1, 2])
    _jalankan(db, 2)

    _hari_bursa(db, hari(3), "AAAA", foreign_net=-500, foreign_net_value=-500_000_000,
                phase="DISTRIBUSI")
    update_positions(hari(3), db)

    assert _posisi(db, "AAAA").status == "ACTIVE"


def test_distribution_streak_resets_on_a_buy_day(db):
    """Jual, lalu beli lagi, lalu jual — itu bukan dua hari beruntun."""
    _akumulasi(db, "AAAA", [0, 1, 2])
    _jalankan(db, 2)

    _hari_bursa(db, hari(3), "AAAA", foreign_net=-500, foreign_net_value=-500_000_000, phase="DISTRIBUSI")
    update_positions(hari(3), db)
    _hari_bursa(db, hari(4), "AAAA", foreign_net=800, foreign_net_value=2_000_000_000, phase="AKUMULASI")
    update_positions(hari(4), db)
    _hari_bursa(db, hari(5), "AAAA", foreign_net=-500, foreign_net_value=-500_000_000, phase="DISTRIBUSI")
    update_positions(hari(5), db)

    assert _posisi(db, "AAAA").status == "ACTIVE"


def test_closed_position_can_reopen_later(db):
    """Akumulasi baru setelah distribusi selesai adalah posisi BARU, bukan lanjutan."""
    _akumulasi(db, "AAAA", [0, 1, 2])
    _jalankan(db, 2)
    for n in (3, 4):
        _hari_bursa(db, hari(n), "AAAA", foreign_net=-500, foreign_net_value=-500_000_000, phase="DISTRIBUSI")
        update_positions(hari(n), db)
    assert _posisi(db, "AAAA").status == "CLOSED"

    for n in (5, 6, 7):
        _hari_bursa(db, hari(n), "AAAA", foreign_net=900, foreign_net_value=4_000_000_000)
        update_positions(hari(n), db)

    assert db.query(models.BigMoneyPosition).filter_by(ticker="AAAA").count() == 2
    assert _posisi(db, "AAAA").status == "ACTIVE"
    assert _posisi(db, "AAAA").opened_on == hari(7)


def test_closes_when_accumulation_turns_negative(db):
    """Tesis yang mati harus ditutup.

    Ditemukan di data nyata: 61 posisi aktif berakumulasi NEGATIF — asing justru
    menjual bersih sejak posisi dibuka, tapi posisinya tak pernah keluar karena
    peak_value-nya nol dan aturan outflow hanya berlaku saat peak > 0. Posisi
    "akumulasi berjalan" yang akumulasinya minus adalah omong kosong.
    """
    _akumulasi(db, "AAAA", [0, 1, 2])
    _jalankan(db, 2)   # akumulasi jendela: Rp15 miliar

    _hari_bursa(db, hari(3), "AAAA", foreign_net=-4000, foreign_net_value=-20_000_000_000,
                phase="NETRAL")
    update_positions(hari(3), db)

    posisi = _posisi(db, "AAAA")

    assert posisi.accumulated_value < 0
    assert posisi.status == "CLOSED"
    assert posisi.close_reason == "REVERSED"


def test_does_not_open_on_trivial_flow(db):
    """Aliran kecil bukan akumulasi — itu kembalian.

    Ambang Rp10 miliar dikalibrasi terhadap data nyata: dengan Rp1 miliar, 105 posisi
    terbuka dan puluhan berakumulasi di bawah Rp5 miliar, menenggelamkan BBCA (Rp1,1
    triliun) di antara kebisingan.
    """
    _akumulasi(db, "AAAA", [0, 1, 2], nilai=1_000_000_000)   # total Rp3 miliar
    _jalankan(db, 2)

    assert _posisi(db, "AAAA") is None


def test_opens_when_flow_is_material(db):
    _akumulasi(db, "AAAA", [0, 1, 2], nilai=5_000_000_000)   # total Rp15 miliar

    _jalankan(db, 2)

    assert _posisi(db, "AAAA").status == "ACTIVE"


# --- idempotensi -------------------------------------------------------------

def test_rerunning_the_same_day_changes_nothing(db):
    """Workflow yang di-rerun tak boleh menggandakan akumulasi."""
    _akumulasi(db, "AAAA", [0, 1, 2])
    _jalankan(db, 2)

    _hari_bursa(db, hari(3), "AAAA", foreign_net=1000, foreign_net_value=3_000_000_000)
    update_positions(hari(3), db)
    update_positions(hari(3), db)

    posisi = _posisi(db, "AAAA")

    assert posisi.accumulated_value == 18_000_000_000   # 15 jendela + 3, bukan + 6
    assert posisi.inflow_days == 4


def test_non_trading_day_is_a_no_op(db):
    _akumulasi(db, "AAAA", [0, 1, 2])
    _jalankan(db, 2)

    update_positions(hari(9), db)   # tak ada data

    assert _posisi(db, "AAAA").status == "ACTIVE"
    assert _posisi(db, "AAAA").last_date == hari(2)
