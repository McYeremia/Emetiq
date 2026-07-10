"""Orkestrasi ingestion harian: IDX → BigMoneyStockDaily.

Menggabungkan idx_client (HTTP) dan transform (perhitungan). Satu commit per
tanggal, sehingga tanggal yang gagal di tengah jalan tidak meninggalkan
keadaan separuh.
"""
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

import models
from services.bigmoney.idx_client import fetch_stock_summary
from services.bigmoney.transform import to_row


@dataclass(frozen=True)
class IngestResult:
    date: date
    trading_day: bool
    inserted: int = 0
    updated: int = 0
    skipped: int = 0


def ingest_stock_summary(target: date, db: Session) -> IngestResult:
    """Ambil ringkasan IDX untuk `target` dan upsert ke bigmoney_stock_daily.

    Idempoten pada (ticker, date). Hari non-bursa mengembalikan
    trading_day=False tanpa melempar galat.
    """
    raw_rows = fetch_stock_summary(target)
    if not raw_rows:
        return IngestResult(date=target, trading_day=False)

    existing = {
        row.ticker: row
        for row in db.query(models.BigMoneyStockDaily)
                     .filter(models.BigMoneyStockDaily.date == target)
                     .all()
    }

    inserted = updated = skipped = 0
    try:
        for raw in raw_rows:
            row = to_row(raw, target)
            if row is None:
                skipped += 1
                continue

            current = existing.get(row["ticker"])
            if current is not None:
                for column, value in row.items():
                    setattr(current, column, value)
                current.scraped_at = datetime.utcnow()
                updated += 1
            else:
                new_row = models.BigMoneyStockDaily(**row)
                db.add(new_row)
                # 2 * existing[...] = new_row untuk tangani duplikat dalam payload yang sama
                existing[row["ticker"]] = new_row
                inserted += 1

        db.commit()
    except Exception:
        db.rollback()
        raise
    return IngestResult(target, True, inserted, updated, skipped)


def latest_trading_date(db: Session, not_after: date | None = None) -> date | None:
    """Hari bursa terakhir yang datanya sudah masuk.

    Tabel hanya berisi tanggal yang benar-benar punya data, jadi MAX(date)
    otomatis melewati akhir pekan, hari libur, dan hari berjalan yang data
    EOD-nya belum terbit IDX.
    """
    query = db.query(func.max(models.BigMoneyStockDaily.date))
    if not_after is not None:
        query = query.filter(models.BigMoneyStockDaily.date <= not_after)
    return query.scalar()
