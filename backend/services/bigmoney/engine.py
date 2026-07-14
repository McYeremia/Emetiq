"""Orkestrasi scoring harian: bigmoney_stock_daily → skor + peringkat top akumulasi.

Lem antara features (fitur jendela), regime (bobot yang berlaku), dan scoring
(keputusan). Tak ada logika bisnis di sini — kalau ada aritmatika yang menggoda
untuk ditulis di berkas ini, tempatnya di features.py atau scoring.py.

Idempoten pada (ticker, date): menjalankan ulang memperbarui baris, tak
menggandakannya. Satu commit per tanggal.
"""
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

import models
from services.bigmoney.features import build_features
from services.bigmoney.positions import update_positions
from services.bigmoney.regime import compute_regime
from services.bigmoney.scoring import score_universe, select_universe

_WINDOW_DAYS = 20   # jendela riwayat yang dimuat untuk fitur
_TOP_N = 10

_SCORE_COLUMNS = (
    "composite", "conviction", "phase", "weight_set",
    "s_relative_foreign_flow", "s_foreign_persistence", "s_big_ticket",
    "s_cost_basis", "s_volume_price", "days_confirmed", "flags",
)


@dataclass(frozen=True)
class EngineResult:
    date: date
    trading_day: bool
    scored: int = 0
    strong: int = 0
    watch: int = 0


def _load_window(db: Session, target: date) -> list[dict]:
    """Baris mentah jendela sebagai dict — features.py tak boleh kenal SQLAlchemy."""
    M = models.BigMoneyStockDaily
    dates = [
        d for (d,) in db.query(M.date)
                        .filter(M.date <= target)
                        .distinct()
                        .order_by(M.date.desc())
                        .limit(_WINDOW_DAYS)
                        .all()
    ]
    if target not in dates:
        return []

    # Hanya 9 kolom yang benar-benar dipakai, bukan 63: tabelnya lebar, dan
    # `db.query(M)` menyeret semua kolom melintasi jaringan hanya untuk dibuang
    # di dict ini. Jendela 20 hari × ~963 saham = ~19.200 baris per skoring.
    columns = (M.ticker, M.date, M.close, M.volume, M.value,
               M.avg_ticket, M.foreign_net, M.foreign_net_value, M.change_pct)

    return [
        {
            "ticker": r.ticker,
            "date": r.date,
            "close": r.close,
            "volume": r.volume,
            "value": r.value,
            "avg_ticket": r.avg_ticket,
            "foreign_net": r.foreign_net,
            "foreign_net_value": r.foreign_net_value,
            "change_pct": r.change_pct,
        }
        for r in db.query(*columns).filter(M.date.in_(dates)).all()
    ]


def _upsert_scores(db: Session, target: date, scores: list[dict]) -> None:
    existing = {
        row.ticker: row
        for row in db.query(models.BigMoneyScore)
                     .filter(models.BigMoneyScore.date == target)
                     .all()
    }

    for score in scores:
        row = existing.get(score["ticker"])
        if row is None:
            row = models.BigMoneyScore(ticker=score["ticker"], date=target)
            db.add(row)
        for column in _SCORE_COLUMNS:
            setattr(row, column, score[column])


def _rebuild_top_accumulation(db: Session, target: date, scores: list[dict]) -> None:
    """Hapus lalu tulis ulang: peringkat harus konsisten dengan skor yang melahirkannya."""
    db.query(models.BigMoneyTopAccumulation).filter(
        models.BigMoneyTopAccumulation.date == target
    ).delete(synchronize_session=False)

    candidates = [s for s in scores if s["conviction"] in ("STRONG", "WATCH")][:_TOP_N]
    for rank, score in enumerate(candidates, start=1):
        db.add(models.BigMoneyTopAccumulation(
            date=target,
            rank=rank,
            ticker=score["ticker"],
            composite=score["composite"],
            conviction=score["conviction"],
            phase=score["phase"],
        ))


def compute_scores(target: date, db: Session) -> EngineResult:
    """Hitung skor big money untuk `target` dan perbarui peringkat top akumulasi.

    Hari non-bursa (tak ada baris di bigmoney_stock_daily) mengembalikan
    trading_day=False tanpa melempar galat — cerminan ingest_stock_summary.
    """
    history = _load_window(db, target)
    if not history:
        return EngineResult(date=target, trading_day=False)

    regime = compute_regime(target, db)
    universe = select_universe(build_features(history, target))
    scores = score_universe(universe, regime.weight_set)

    _upsert_scores(db, target, scores)
    _rebuild_top_accumulation(db, target, scores)
    db.commit()

    # Posisi dimajukan setelah skor tersimpan: ia membaca skor hari ini untuk syarat
    # masuk dan fase untuk syarat keluar.
    update_positions(target, db)

    return EngineResult(
        date=target,
        trading_day=True,
        scored=len(scores),
        strong=sum(1 for s in scores if s["conviction"] == "STRONG"),
        watch=sum(1 for s in scores if s["conviction"] == "WATCH"),
    )
