"""Backfill riwayat bigmoney_stock_daily dari IDX.

    python scripts/bigmoney_backfill.py --days 90
    python scripts/bigmoney_backfill.py --days 30 --end 2026-06-30 --force

Hari libur bursa tak perlu dikodekan: IDX cukup mengembalikan nol baris, dan
tanggal itu dicatat sebagai dilewati. Akhir pekan dilewati tanpa request.
Kegagalan satu tanggal dicatat lalu backfill lanjut ke tanggal berikutnya.
"""
import argparse
import logging
import os
import sys
import time
from datetime import date, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base, SessionLocal, engine  # noqa: E402
import models  # noqa: E402,F401 — daftarkan model ORM
from services.bigmoney.ingest import ingest_stock_summary  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("bigmoney-backfill")

_REQUEST_DELAY_SECONDS = 1.5


def weekdays_back(end: date, count: int) -> list[date]:
    """`count` hari kerja terakhir sampai dan termasuk `end`, urut menaik."""
    days: list[date] = []
    cursor = end
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return sorted(days)


def _already_ingested(db, target: date) -> bool:
    return (
        db.query(models.BigMoneyStockDaily.id)
          .filter(models.BigMoneyStockDaily.date == target)
          .first()
        is not None
    )


def run_backfill(days: int, end: date, force: bool) -> int:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    targets = weekdays_back(end, days)
    if not targets:
        logger.warning("Tak ada hari kerja untuk diproses (days=%d)", days)
        db.close()
        return 0
    logger.info("Backfill %d hari kerja: %s .. %s", len(targets), targets[0], targets[-1])

    filled = skipped = failed = 0
    failures: list[str] = []

    try:
        for target in targets:
            if not force and _already_ingested(db, target):
                logger.info("%s sudah ada, dilewati", target)
                skipped += 1
                continue

            try:
                result = ingest_stock_summary(target, db)
            except Exception as exc:
                # ingest_stock_summary sudah me-rollback tulisannya sendiri; ini
                # membersihkan transaksi baca menggantung dari _already_ingested.
                db.rollback()
                logger.error("%s GAGAL: %s", target, exc)
                failures.append(f"{target}: {exc}")
                failed += 1
            else:
                if not result.trading_day:
                    logger.info("%s bukan hari bursa", target)
                    skipped += 1
                else:
                    logger.info(
                        "%s terisi: +%d baru, %d diperbarui, %d dilewati",
                        target, result.inserted, result.updated, result.skipped,
                    )
                    filled += 1

            time.sleep(_REQUEST_DELAY_SECONDS)
    finally:
        db.close()

    logger.info("Selesai. Terisi: %d | Dilewati: %d | Gagal: %d", filled, skipped, failed)
    for line in failures:
        logger.warning("  gagal → %s", line)

    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill bigmoney_stock_daily dari IDX")
    parser.add_argument("--days", type=int, default=90, help="jumlah hari kerja (default 90)")
    parser.add_argument("--end", type=date.fromisoformat, default=date.today(),
                        help="tanggal akhir YYYY-MM-DD (default hari ini)")
    parser.add_argument("--force", action="store_true", help="ulangi tanggal yang sudah ada")
    args = parser.parse_args()

    return run_backfill(args.days, args.end, args.force)


if __name__ == "__main__":
    sys.exit(main())
