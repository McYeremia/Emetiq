"""Sinkronisasi harian harga + fundamental + pemindaian sinyal.

Dijalankan `daily-sync.yml` (10:00 UTC = 17:00 WIB, Senin-Jumat) di runner GitHub.

Dua mode
--------
`harian` (bawaan) — `period="5d"` per saham. Cepat, cukup untuk cron yang tertib.

`penuh` — menarik dari **tanggal terakhir yang tersimpan** untuk tiap saham, jadi
lubang sepanjang apa pun tertambal. Ini menggantikan `POST /stocks/refresh` yang
dihapus 3 Sep 2026: kemampuannya sama, tapi jalannya di runner GitHub, bukan di
dalam worker Space yang sedang melayani pengunjung.

Kenapa mode `harian` tak bisa menambal lubang: `period="5d"` selalu dihitung dari
hari ini. Kalau cron mati enam hari, jendela itu tak pernah lagi menyentuh hari
yang terlewat — dan `save_ohlcv` hanya menulis apa yang diberikan kepadanya, jadi
lubangnya menetap sampai seseorang menjalankan mode `penuh`.

    python scripts/daily_sync.py              # harian
    python scripts/daily_sync.py --mode penuh # tambal lubang

Di GitHub: Actions > "Daily Sync" > Run workflow > mode: penuh.
"""
import argparse
import sys
import os
import logging
from datetime import date, datetime

# Fix Pathing
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func

from database import SessionLocal, engine, Base
import models
import services.data_fetcher as fetcher
import services.watcher as watcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("daily-sync")

MODE_HARIAN = "harian"
MODE_PENUH = "penuh"


def _tanggal_terakhir_per_saham(db) -> dict:
    """Satu query agregat, bukan satu query per saham.

    Dipanggil hanya di mode `penuh`. Versi N+1-nya akan menembak Supabase ~740 kali
    hanya untuk memutuskan tanggal mulai — biaya yang tak perlu di jalur yang sudah
    panjang.
    """
    return dict(
        db.query(models.OHLCVDaily.stock_id, func.max(models.OHLCVDaily.date))
        .group_by(models.OHLCVDaily.stock_id)
        .all()
    )


def run_daily_sync(mode: str = MODE_HARIAN):
    # Pastikan semua tabel ada (penting saat job jalan di lingkungan bersih, mis. CI/cron)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    stocks = db.query(models.Stock).all()

    logger.info(f"--- DAILY SYNC STARTED AT {datetime.now()} (mode: {mode}) ---")
    logger.info(f"Synchronizing {len(stocks)} assets...")

    terakhir = _tanggal_terakhir_per_saham(db) if mode == MODE_PENUH else {}

    success_count = 0
    for stock in stocks:
        try:
            # 1. Fetch & Save Latest Price
            if mode == MODE_PENUH:
                ld = terakhir.get(stock.id)
                # `ld > hari ini` mustahil pada data waras, tapi kalau sampai terjadi
                # (jam mesin melenceng, data rusak) `start` di masa depan membuat
                # yfinance mengembalikan kosong dan sahamnya diam-diam terlewat.
                # Jatuhkan ke tarikan penuh, jangan ke jendela kosong.
                if ld is not None and ld <= date.today():
                    df = fetcher.fetch_ohlcv(stock.ticker, start=ld)
                else:
                    df = fetcher.fetch_ohlcv(stock.ticker)   # default period="5y"
            else:
                df = fetcher.fetch_ohlcv(stock.ticker, period="5d")  # Ambil 5 hari terakhir saja agar cepat

            if not df.empty:
                new_rows = fetcher.save_ohlcv(db, stock, df)

                # 2. Update Fundamentals once a week (or every sync if light)
                fetcher.update_stock_fundamentals(db, stock)

                success_count += 1
                if success_count % 20 == 0:
                    logger.info(f"Progress: {success_count} stocks updated...")
        except Exception as e:
            logger.error(f"Failed to sync {stock.ticker}: {e}")
            continue

    db.commit()

    # 3. Trigger AI Watcher to find new signals with fresh data
    #
    # Ia menghapus seluruh tabel `signals` lebih dulu lalu menghitung ulang, jadi ia
    # harus jalan di tempat yang tak akan dipotong di tengah — itu sebabnya jalur
    # HTTP-nya (`POST /stocks/scan`) dihapus dan hanya jalur ini yang tersisa.
    # Tabel itu dibaca AI Porto lewat services/ai_porto/data.py.
    logger.info("Triggering AI Market Scanner...")
    watcher.scan_market_signals()

    db.close()
    logger.info(f"--- DAILY SYNC COMPLETED: {success_count} ASSETS UPDATED ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sinkronisasi harian EMETIQ")
    parser.add_argument(
        "--mode",
        choices=[MODE_HARIAN, MODE_PENUH],
        default=MODE_HARIAN,
        help=f"'{MODE_HARIAN}': 5 hari terakhir (bawaan). "
             f"'{MODE_PENUH}': dari tanggal terakhir tiap saham — untuk menambal lubang.",
    )
    run_daily_sync(parser.parse_args().mode)
