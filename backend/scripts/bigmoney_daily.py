"""Pipeline harian Big Money — dijalankan GitHub Actions tiap sore hari kerja.

    python scripts/bigmoney_daily.py                  # hari ini
    python scripts/bigmoney_daily.py --date 2026-07-10
    python scripts/bigmoney_daily.py --no-report      # skor saja, jangan panggil Gemini

Satu perintah menggantikan bigmoney_score.py + bigmoney_report.py untuk jalan
otomatis. Skrip terpisah itu tetap ada untuk pemakaian manual dan backfill.

Keluar dengan kode 0 pada hari non-bursa: akhir pekan dan libur bursa bukan
kegagalan, dan job merah tiap Sabtu akan melatih kita mengabaikan alarm.
"""
import argparse
import logging
import os
import sys
from datetime import date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base, SessionLocal, engine  # noqa: E402
import models  # noqa: E402,F401 — daftarkan model ORM
from services.bigmoney.idx_client import IdxFetchError  # noqa: E402
from services.bigmoney.pipeline import run_daily_pipeline  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("bigmoney-daily")


def run(target: date, with_report: bool) -> int:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        result = run_daily_pipeline(target, db, with_report=with_report)
    except IdxFetchError as exc:
        db.rollback()
        logger.error("%s GAGAL mengambil data IDX: %s", target, exc)
        return 1
    finally:
        db.close()

    if not result.trading_day:
        logger.info("%s bukan hari bursa — tidak ada yang dikerjakan", target)
        return 0

    logger.info("Selesai. %d saham di-skor (STRONG %d, WATCH %d)",
                result.scored, result.strong, result.watch)

    # Laporan gagal tidak memerahkan job: skornya sudah tersimpan, dan itu bagian
    # yang berharga. Cukup catat supaya terlihat di log Actions.
    if result.report_error:
        logger.warning("Laporan tidak tertulis: %s", result.report_error)
    elif result.report_skipped:
        logger.warning("Laporan dilewati (GEMINI_API_KEY belum diset atau --no-report)")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline harian Big Money")
    parser.add_argument("--date", type=date.fromisoformat, default=date.today(),
                        help="tanggal YYYY-MM-DD (default: hari ini)")
    parser.add_argument("--no-report", action="store_true",
                        help="lewati laporan Gemini, hitung skor saja")
    args = parser.parse_args()

    return run(args.date, with_report=not args.no_report)


if __name__ == "__main__":
    sys.exit(main())
