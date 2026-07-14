"""Salin data dari SQLite lokal (idxanalyst.db) -> Postgres (Supabase). SEKALI JALAN.

Menyalin: Stock, OHLCVDaily, BrokerFlow.
TIDAK menyalin: indicators_cache (dihitung ulang on-the-fly), serta tabel auth baru
(profiles/watchlist/trade_logs) yang memang mulai kosong.

Dijalankan DARI LAPTOP (karena sumber SQLite ada di laptop), tapi cuma sekali & cepat.
Setelah ini DB cloud terisi -> laptop boleh dimatikan.

CARA PAKAI (dari folder backend):
  Windows PowerShell:
    $env:TARGET_DATABASE_URL = "postgresql://postgres.xxx:PASSWORD@aws-1-...pooler.supabase.com:5432/postgres"
    .\venv\Scripts\python.exe -m scripts.migrate_sqlite_to_postgres

  (Opsional) sumber lain: set SOURCE_DATABASE_URL. Default = backend/idxanalyst.db.

CATATAN: jalankan ke target yang MASIH KOSONG (belum di-seed), agar tidak bentrok
unique constraint pada OHLCV.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
import models

_BACKEND = Path(__file__).resolve().parent.parent
SRC_URL = os.getenv("SOURCE_DATABASE_URL") or f"sqlite:///{_BACKEND / 'idxanalyst.db'}"
DST_URL = os.getenv("TARGET_DATABASE_URL")

if not DST_URL:
    raise SystemExit("Set TARGET_DATABASE_URL ke connection string Supabase (postgresql://...).")
if DST_URL.startswith("postgres://"):
    DST_URL = DST_URL.replace("postgres://", "postgresql://", 1)

src_engine = create_engine(
    SRC_URL, connect_args={"check_same_thread": False} if SRC_URL.startswith("sqlite") else {}
)
dst_engine = create_engine(DST_URL)
Src = sessionmaker(bind=src_engine)
Dst = sessionmaker(bind=dst_engine)

BATCH = 5000


def _clip(value, n):
    """Potong string ke panjang kolom Postgres (SQLite abaikan batas, Postgres tegas)."""
    return value[:n] if isinstance(value, str) else value


def main():
    Base.metadata.create_all(bind=dst_engine)
    src, dst = Src(), Dst()

    # 1) Stocks — salin tanpa id, bangun peta old_id -> new_id
    id_map = {}
    stocks = src.query(models.Stock).all()
    print(f"Stocks di sumber: {len(stocks)}")
    for s in stocks:
        existing = dst.query(models.Stock).filter_by(ticker=s.ticker).first()
        if existing:
            id_map[s.id] = existing.id
            continue
        ns = models.Stock(
            ticker=_clip(s.ticker, 10), name=_clip(s.name, 100), sector=_clip(s.sector, 50),
            market_cap_cat=_clip(s.market_cap_cat, 10),
            last_updated=s.last_updated, market_cap=s.market_cap, pe_ratio=s.pe_ratio,
            pbv_ratio=s.pbv_ratio, dividend_yield=s.dividend_yield, forward_pe=s.forward_pe,
        )
        dst.add(ns)
        dst.flush()
        id_map[s.id] = ns.id
    dst.commit()
    print(f"Stocks tersalin/tersedia: {len(id_map)}")

    # 2) OHLCV — remap stock_id, insert batch
    total = src.query(models.OHLCVDaily).count()
    print(f"OHLCV di sumber: {total} baris")
    batch, done = [], 0
    for r in src.query(models.OHLCVDaily).yield_per(2000):
        new_sid = id_map.get(r.stock_id)
        if new_sid is None:
            continue
        batch.append({
            "stock_id": new_sid, "date": r.date, "open": r.open, "high": r.high,
            "low": r.low, "close": r.close, "volume": r.volume, "adj_close": r.adj_close,
        })
        if len(batch) >= BATCH:
            dst.bulk_insert_mappings(models.OHLCVDaily, batch)
            dst.commit()
            done += len(batch)
            batch = []
            print(f"  OHLCV {done}/{total}")
    if batch:
        dst.bulk_insert_mappings(models.OHLCVDaily, batch)
        dst.commit()
        done += len(batch)
    print(f"OHLCV selesai: {done} baris")

    # 3) Broker flows
    flows = src.query(models.BrokerFlow).all()
    for f in flows:
        if dst.query(models.BrokerFlow).filter_by(date=f.date, broker_code=f.broker_code).first():
            continue
        dst.add(models.BrokerFlow(
            date=f.date, broker_code=_clip(f.broker_code, 10), broker_name=_clip(f.broker_name, 200),
            total_value=f.total_value, volume=f.volume, frequency=f.frequency,
        ))
    dst.commit()
    print(f"Broker flows tersalin: {len(flows)}")

    src.close()
    dst.close()
    print("\n--- Migrasi SQLite -> Postgres selesai ---")


if __name__ == "__main__":
    main()
