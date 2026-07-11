"""Hitung skor big money dari bigmoney_stock_daily yang sudah ter-ingest.

    python scripts/bigmoney_score.py                    # hari bursa terakhir
    python scripts/bigmoney_score.py --date 2026-07-10
    python scripts/bigmoney_score.py --days 30          # 30 hari bursa terakhir

Tidak menyentuh jaringan sama sekali: seluruh masukan sudah ada di database.
Kegagalan satu tanggal dicatat lalu lanjut ke tanggal berikutnya.
"""
import argparse
import logging
import os
import sys
from datetime import date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base, SessionLocal, engine  # noqa: E402
import models  # noqa: E402,F401 — daftarkan model ORM
from services.bigmoney.engine import compute_scores  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("bigmoney-score")


def trading_dates(db, end: date | None, count: int) -> list[date]:
    """`count` hari bursa terakhir yang punya data, sampai dan termasuk `end`.

    Diambil dari tabel, bukan dari kalender: hanya tanggal yang benar-benar
    ter-ingest yang bisa di-skor, dan itu otomatis melewati libur bursa.
    """
    M = models.BigMoneyStockDaily
    query = db.query(M.date).distinct()
    if end is not None:
        query = query.filter(M.date <= end)
    dates = [d for (d,) in query.order_by(M.date.desc()).limit(count).all()]
    return sorted(dates)


def run(end: date | None, days: int) -> int:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        targets = trading_dates(db, end, days)
        if not targets:
            logger.error("Tak ada data di bigmoney_stock_daily — jalankan bigmoney_backfill.py dulu")
            return 1

        logger.info("Scoring %d hari bursa: %s .. %s", len(targets), targets[0], targets[-1])

        failed = 0
        for target in targets:
            try:
                result = compute_scores(target, db)
            except Exception as exc:               # noqa: BLE001 — satu tanggal gagal tak boleh menghentikan sisanya
                db.rollback()
                logger.error("%s GAGAL: %s", target, exc)
                failed += 1
            else:
                logger.info("%s: %d saham di-skor | STRONG %d | WATCH %d",
                            target, result.scored, result.strong, result.watch)

        logger.info("Selesai. Gagal: %d", failed)
        return 1 if failed else 0
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Hitung skor big money")
    parser.add_argument("--date", type=date.fromisoformat, default=None,
                        help="tanggal akhir YYYY-MM-DD (default: hari bursa terakhir yang ada)")
    parser.add_argument("--days", type=int, default=1,
                        help="jumlah hari bursa yang dihitung, mundur dari --date (default 1)")
    args = parser.parse_args()

    return run(args.date, args.days)


if __name__ == "__main__":
    sys.exit(main())
