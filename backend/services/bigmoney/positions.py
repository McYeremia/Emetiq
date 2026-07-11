"""Akumulasi yang dilacak: masuk, bertahan, keluar.

Peringkat harian berganti 6-9 nama tiap hari — terbukti dari data: dari 10 saham,
hanya 1-4 bertahan ke hari berikutnya. Dengan pergantian sederas itu, perkembangan
sebuah akumulasi mustahil diikuti, dan pengguna hanya melihat daftar yang berkedip.

Posisi memperbaiki itu. Saham MASUK ketika akumulasinya terbukti (asing net beli >= 3
dari 5 hari terakhir DAN skor >= 55), lalu BERTAHAN meski peringkat hariannya jatuh —
karena skor harian mengukur "hari ini dibanding saham lain", bukan "akumulasi ini masih
berjalan atau tidak". Dua pertanyaan berbeda; menjawab yang kedua dengan yang pertama
adalah sumber kebisingannya.

Keluarnya dibandingkan dengan akumulasinya SENDIRI, bukan dengan skor: posisi ditutup
ketika dana yang keluar sejak puncak melampaui separuh dari yang pernah masuk, atau
ketika fase distribusi/markdown bertahan dua hari beruntun.

Tanpa LLM. Seluruh aturan deterministik dan bisa diaudit.
"""
import logging
from datetime import date

from sqlalchemy.orm import Session

import models

logger = logging.getLogger("bigmoney.positions")

_LOOKBACK_DAYS = 5          # jendela untuk syarat "3 dari 5 hari"
_MIN_BUY_DAYS = 3
_MIN_SCORE = 55.0           # setara conviction WATCH

# Rp — akumulasi 5 hari di bawah ini bukan "big money", cuma kembalian.
#
# Dikalibrasi terhadap data, bukan ditebak: dengan ambang Rp1 miliar, 105 posisi aktif
# terbuka dan puluhan di antaranya berakumulasi di bawah Rp5 miliar — menenggelamkan
# BBCA (Rp1,1 triliun) dan MDKA (Rp1 triliun) di antara kebisingan. Daftar yang tak
# bisa dibaca sama saja dengan daftar yang tak ada.
_MIN_WINDOW_INFLOW = 10_000_000_000

_EXIT_OUTFLOW_RATIO = 0.5   # keluar bila dana keluar > 50% dari yang pernah masuk
_EXIT_DISTRIBUTION_DAYS = 2

_SELLING_PHASES = ("DISTRIBUSI", "MARKDOWN")


def _trading_dates(db: Session, target: date, count: int) -> list[date]:
    M = models.BigMoneyStockDaily
    rows = (
        db.query(M.date)
          .filter(M.date <= target)
          .distinct()
          .order_by(M.date.desc())
          .limit(count)
          .all()
    )
    return [d for (d,) in rows]


def _last_closed(db: Session) -> dict[str, date]:
    """Tanggal penutupan terakhir per ticker."""
    rows = (
        db.query(models.BigMoneyPosition.ticker, models.BigMoneyPosition.closed_on)
          .filter(models.BigMoneyPosition.status == "CLOSED")
          .all()
    )
    latest: dict[str, date] = {}
    for ticker, closed_on in rows:
        if closed_on and (ticker not in latest or closed_on > latest[ticker]):
            latest[ticker] = closed_on
    return latest


def _window_stats(db: Session, target: date) -> tuple[dict[str, int], dict[str, int]]:
    """Berapa hari asing net beli, per ticker, dalam 5 hari bursa terakhir.

    Hari beli SEBELUM posisi terakhir ditutup tidak dihitung. Akumulasi yang sudah
    terdistribusi adalah akumulasi yang mati — memakainya sebagai bukti untuk masuk
    lagi akan membuka ulang posisi di hari yang sama ia ditutup, dan seluruh gagasan
    "posisi yang stabil" runtuh.
    """
    window = _trading_dates(db, target, _LOOKBACK_DAYS)
    if not window:
        return {}, {}

    closed = _last_closed(db)

    M = models.BigMoneyStockDaily
    counts: dict[str, int] = {}
    inflow: dict[str, int] = {}
    for ticker, net, value, day in db.query(
        M.ticker, M.foreign_net, M.foreign_net_value, M.date
    ).filter(M.date.in_(window)).all():
        penutupan = closed.get(ticker)
        if penutupan is not None and day <= penutupan:
            continue   # bukti lama, dari akumulasi yang sudah dilepas
        inflow[ticker] = inflow.get(ticker, 0) + (value or 0)
        if (net or 0) > 0:
            counts[ticker] = counts.get(ticker, 0) + 1

    # Aliran receh bukan akumulasi. Tanpa ambang ini, 94 saham beraliran di bawah
    # Rp1 miliar ikut membuka posisi dan menenggelamkan yang benar-benar berarti.
    layak = {
        ticker: hari
        for ticker, hari in counts.items()
        if inflow.get(ticker, 0) >= _MIN_WINDOW_INFLOW
    }
    return layak, inflow


def _open_position(db: Session, target: date, score: models.BigMoneyScore,
                   daily: models.BigMoneyStockDaily, entry_inflow: int, buy_days: int) -> None:
    """Buka posisi dengan MEMBAWA akumulasi yang sudah terkumpul di jendela masuk.

    Memulai dari nol akan salah dua kali. Pertama, ia menyangkal kenyataan: akumulasi
    itu sudah terjadi — justru itulah alasan posisi ini dibuka. Kedua, ia membuat
    posisi mati seketika oleh satu hari jual kecil, karena akumulasinya langsung minus
    padahal asing masih untung besar sejak awal masuk.

    Dengan puncak yang benar sejak hari pertama, aturan "keluar bila dana keluar > 50%
    dari yang pernah masuk" langsung punya pembanding yang sah.
    """
    db.add(models.BigMoneyPosition(
        ticker=score.ticker,
        opened_on=target,
        status="ACTIVE",
        entry_close=daily.close,
        last_close=daily.close,
        last_date=target,
        accumulated_value=entry_inflow,
        peak_value=entry_inflow,
        inflow_days=buy_days,
        distribution_days=0,
        entry_score=score.composite,
        last_score=score.composite,
    ))
    logger.info("%s posisi DIBUKA di %s (skor %.1f, akumulasi Rp%.1f M)",
                score.ticker, target, score.composite or 0, entry_inflow / 1e9)


def _advance(position: models.BigMoneyPosition, target: date,
             daily: models.BigMoneyStockDaily, score: models.BigMoneyScore | None) -> None:
    """Majukan posisi satu hari, lalu putuskan apakah ia harus ditutup."""
    flow = daily.foreign_net_value or 0

    position.accumulated_value = (position.accumulated_value or 0) + flow
    position.peak_value = max(position.peak_value or 0, position.accumulated_value)
    if flow > 0:
        position.inflow_days = (position.inflow_days or 0) + 1

    position.last_close = daily.close
    position.last_date = target
    if score is not None:
        position.last_score = score.composite

    phase = score.phase if score else None
    if phase in _SELLING_PHASES:
        position.distribution_days = (position.distribution_days or 0) + 1
    elif flow > 0:
        # Beli lagi berarti beruntunnya patah. Jual-beli-jual bukan dua hari beruntun.
        position.distribution_days = 0

    # Keluar 1: distribusi beruntun — ganti tangan, meski nilainya belum besar.
    if (position.distribution_days or 0) >= _EXIT_DISTRIBUTION_DAYS:
        _close(position, target, "DISTRIBUSI")
        return

    # Keluar 2: akumulasinya berbalik negatif. Asing sudah menjual lebih banyak daripada
    # yang pernah ia beli sejak posisi dibuka — tesisnya mati, apa pun kata skor.
    #
    # Tanpa aturan ini, posisi yang langsung merugi tak pernah bisa keluar: peak_value-nya
    # nol, dan aturan outflow di bawah hanya berlaku ketika peak > 0. Di data nyata itu
    # meninggalkan 61 posisi hidup dengan akumulasi minus.
    if position.accumulated_value < 0:
        _close(position, target, "REVERSED")
        return

    # Keluar 3: dana yang ditarik keluar melampaui separuh yang pernah masuk.
    peak = position.peak_value or 0
    if peak > 0:
        outflow = peak - position.accumulated_value
        if outflow > _EXIT_OUTFLOW_RATIO * peak:
            _close(position, target, "OUTFLOW")


def _close(position: models.BigMoneyPosition, target: date, reason: str) -> None:
    position.status = "CLOSED"
    position.closed_on = target
    position.close_reason = reason
    logger.info("%s posisi DITUTUP di %s (%s)", position.ticker, target, reason)


def update_positions(target: date, db: Session) -> dict:
    """Majukan posisi aktif satu hari, lalu buka posisi baru yang memenuhi syarat.

    Idempoten: menjalankan ulang tanggal yang sama tidak menggandakan akumulasi —
    posisi yang `last_date`-nya sudah sama dengan `target` dilewati.

    Hari non-bursa (tak ada baris harian) tidak melakukan apa pun.
    """
    dailies = {
        row.ticker: row
        for row in db.query(models.BigMoneyStockDaily)
                     .filter(models.BigMoneyStockDaily.date == target)
                     .all()
    }
    if not dailies:
        return {"opened": 0, "closed": 0, "active": 0}

    scores = {
        row.ticker: row
        for row in db.query(models.BigMoneyScore)
                     .filter(models.BigMoneyScore.date == target)
                     .all()
    }

    active = (
        db.query(models.BigMoneyPosition)
          .filter(models.BigMoneyPosition.status == "ACTIVE")
          .all()
    )

    closed = 0
    for position in active:
        if position.last_date is not None and position.last_date >= target:
            continue   # tanggal ini sudah diproses
        daily = dailies.get(position.ticker)
        if daily is None:
            continue   # saham tak diperdagangkan hari ini; posisi menunggu
        _advance(position, target, daily, scores.get(position.ticker))
        if position.status == "CLOSED":
            closed += 1

    db.flush()

    sudah_aktif = {
        p.ticker
        for p in db.query(models.BigMoneyPosition.ticker)
                   .filter(models.BigMoneyPosition.status == "ACTIVE")
                   .all()
    }

    buy_days, window_inflow = _window_stats(db, target)

    opened = 0
    for ticker, score in scores.items():
        if ticker in sudah_aktif:
            continue
        if buy_days.get(ticker, 0) < _MIN_BUY_DAYS:
            continue
        if (score.composite or 0) < _MIN_SCORE:
            continue
        daily = dailies.get(ticker)
        if daily is None:
            continue
        _open_position(db, target, score, daily, window_inflow.get(ticker, 0), buy_days[ticker])
        opened += 1

    db.commit()

    still_active = (
        db.query(models.BigMoneyPosition)
          .filter(models.BigMoneyPosition.status == "ACTIVE")
          .count()
    )
    return {"opened": opened, "closed": closed, "active": still_active}
