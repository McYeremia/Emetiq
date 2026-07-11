"""Hasilkan laporan harian Big Money lewat Gemini.

    python scripts/bigmoney_report.py --dry-run     # cetak prompt, JANGAN panggil Gemini
    python scripts/bigmoney_report.py               # hari bursa terakhir yang sudah di-skor
    python scripts/bigmoney_report.py --date 2026-07-10

`--dry-run` bekerja tanpa GEMINI_API_KEY: prompt bisa dibaca dan dikoreksi sebelum
satu token pun dibelanjakan. Jalankan scripts/bigmoney_score.py lebih dulu — tanpa
skor, tak ada bahan laporan.
"""
import argparse
import logging
import os
import sys
from datetime import date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base, SessionLocal, engine  # noqa: E402
import models  # noqa: E402,F401 — daftarkan model ORM
from services.bigmoney.llm import LlmError, is_configured  # noqa: E402
from services.bigmoney.report_generator import (  # noqa: E402
    build_context,
    generate_report,
    render_prompt,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("bigmoney-report")


def _latest_scored_date(db) -> date | None:
    """Tanggal terakhir yang punya rezim — penanda hari itu sudah lewat engine."""
    from sqlalchemy import func
    return db.query(func.max(models.BigMoneyMarketRegime.date)).scalar()


def run(target: date | None, dry_run: bool) -> int:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        target = target or _latest_scored_date(db)
        if target is None:
            logger.error("Belum ada hari yang di-skor — jalankan scripts/bigmoney_score.py dulu")
            return 1

        if dry_run:
            context = build_context(target, db)
            if context is None:
                logger.error("%s belum di-skor", target)
                return 1
            print(render_prompt(context))
            return 0

        if not is_configured():
            logger.error("GEMINI_API_KEY belum diset. Ambil key di https://aistudio.google.com/apikey, "
                         "taruh di .env backend, atau jalankan dengan --dry-run untuk melihat prompt saja.")
            return 1

        try:
            report = generate_report(target, db)
        except LlmError as exc:
            logger.error("%s GAGAL: %s", target, exc)
            return 1

        if report is None:
            logger.error("%s belum di-skor", target)
            return 1

        logger.info("%s laporan tersimpan: %s", target, report.headline)
        return 0
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Laporan harian Big Money (Gemini)")
    parser.add_argument("--date", type=date.fromisoformat, default=None,
                        help="tanggal YYYY-MM-DD (default: hari terakhir yang sudah di-skor)")
    parser.add_argument("--dry-run", action="store_true",
                        help="cetak prompt tanpa memanggil Gemini — tak butuh API key")
    args = parser.parse_args()

    return run(args.date, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
