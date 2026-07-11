"""Tambahkan kolom yang hilang pada tabel yang sudah terlanjur ada.

    python scripts/bigmoney_migrate.py

`Base.metadata.create_all()` — yang dipakai main.py — hanya membuat tabel BARU. Ia
tidak pernah menambahkan kolom ke tabel yang sudah ada. Selama fitur baru selalu
berupa tabel baru, itu tak jadi masalah; begitu kita menambah kolom ke `profiles`
(tautan Telegram) dan `bigmoney_daily_report` (penanda kirim), tabel lama di database
lama langsung ketinggalan dan query-nya gagal dengan "no such column".

Skrip ini menambalnya. Idempoten: kolom yang sudah ada dilewati, jadi aman dijalankan
berkali-kali dan aman dijalankan pada database yang masih kosong.

Jalankan sekali di tiap database — lokal (SQLite) maupun Supabase (Postgres).
"""
import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text  # noqa: E402

from database import Base, engine  # noqa: E402
import models  # noqa: E402,F401 — daftarkan model ORM

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("bigmoney-migrate")

# Tipe ditulis dalam SQL yang dipahami SQLite maupun Postgres.
_COLUMNS = {
    "profiles": {
        "telegram_chat_id": "VARCHAR(32)",
        "telegram_link_code": "VARCHAR(12)",
        "telegram_code_expires_at": "TIMESTAMP",
    },
    "bigmoney_daily_report": {
        "sent_at": "TIMESTAMP",
    },
}


def main() -> int:
    # Tabel yang benar-benar baru tetap dibuat lewat jalur biasa.
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    added = 0
    with engine.begin() as conn:
        for table, columns in _COLUMNS.items():
            if table not in existing_tables:
                logger.info("%s belum ada — create_all sudah menanganinya", table)
                continue

            present = {col["name"] for col in inspector.get_columns(table)}
            for column, sql_type in columns.items():
                if column in present:
                    continue
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
                logger.info("%s: kolom %s ditambahkan", table, column)
                added += 1

    logger.info("Selesai. %d kolom ditambahkan.", added)
    return 0


if __name__ == "__main__":
    sys.exit(main())
