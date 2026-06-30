import sys
import os
import logging
from datetime import datetime

# Fix Pathing
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, engine, Base
import models
import services.data_fetcher as fetcher
import services.watcher as watcher
import services.ml_predictor as ml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("daily-sync")

def run_daily_sync():
    # Pastikan semua tabel ada (penting saat job jalan di lingkungan bersih, mis. CI/cron)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    stocks = db.query(models.Stock).all()
    
    logger.info(f"--- DAILY SYNC STARTED AT {datetime.now()} ---")
    logger.info(f"Synchronizing {len(stocks)} assets...")

    success_count = 0
    for stock in stocks:
        try:
            # 1. Fetch & Save Latest Price
            df = fetcher.fetch_ohlcv(stock.ticker, period="5d") # Ambil 5 hari terakhir saja agar cepat
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
    logger.info("Triggering AI Market Scanner...")
    watcher.scan_market_signals()

    # 4. Re-train ML models on the fresh data and upsert each prediction.
    #    Done here (off the request path) so end users never trigger the heavy
    #    GradientBoosting fit — they only read the stored prediction.
    #    Upsert = 1 baris per saham yang ditimpa tiap hari, jadi tabel tidak membengkak.
    logger.info("Re-training ML models & storing predictions...")
    trained = 0
    skipped = 0
    for stock in stocks:
        try:
            res = ml.train_and_store(stock.ticker, db)
            if res.get("status") == "ok":
                trained += 1
            else:
                skipped += 1  # e.g. data tidak cukup — fungsi mengembalikan status non-ok
        except Exception as e:
            logger.error(f"ML training failed for {stock.ticker}: {e}")
            db.rollback()
            skipped += 1
    logger.info(f"ML training done: {trained} stored, {skipped} skipped")

    db.close()
    logger.info(f"--- DAILY SYNC COMPLETED: {success_count} ASSETS UPDATED ---")

if __name__ == "__main__":
    run_daily_sync()
