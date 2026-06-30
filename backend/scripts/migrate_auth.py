"""Migrasi satu kali untuk sistem login + tier.

Aman dijalankan ulang (idempoten):
  1. Buat tabel baru: profiles, watchlist (via create_all).
  2. Tambah kolom trade_logs.user_id bila belum ada (ALTER TABLE).
  3. HAPUS semua trade lama (keputusan desain: mulai bersih per-user).

Jalankan dari folder backend:  python -m scripts.migrate_auth
"""
import sys
from pathlib import Path

# Pastikan folder backend ada di path saat dijalankan langsung
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text

from database import Base, engine
import models  # noqa: F401 — register ORM models


def _column_exists(table: str, column: str) -> bool:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def run() -> None:
    # 1) Buat tabel baru (create_all hanya membuat yang belum ada)
    Base.metadata.create_all(bind=engine)
    print("[1/3] Tabel profiles & watchlist dipastikan ada.")

    # 2) Tambah kolom user_id di trade_logs bila belum ada
    if _column_exists("trade_logs", "user_id"):
        print("[2/3] Kolom trade_logs.user_id sudah ada — dilewati.")
    else:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE trade_logs ADD COLUMN user_id VARCHAR(36)"))
        print("[2/3] Kolom trade_logs.user_id ditambahkan.")

    # 3) Hapus semua trade lama (mulai bersih)
    with engine.begin() as conn:
        result = conn.execute(text("DELETE FROM trade_logs"))
    print(f"[3/3] {result.rowcount if result.rowcount is not None else '?'} trade lama dihapus.")

    print("Migrasi selesai.")


if __name__ == "__main__":
    run()
