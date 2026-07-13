"""SEMENTARA — cek apakah IP Hugging Face bisa menembus IDX.

GitHub Actions dibalas HTTP 403 oleh IDX (run 2026-07-13 gagal di tahap ingest),
diduga karena IDX memblokir IP datacenter. Laptop dengan IP rumah lolos. Endpoint
ini menjawab satu pertanyaan: HF ikut diblokir atau tidak?

HAPUS FILE INI (dan barisnya di main.py) setelah pertanyaannya terjawab.

Sengaja tanpa auth: kita perlu memanggilnya tanpa JWT. Aman karena responsnya
tidak memuat data pasar, hanya jumlah baris dan pesan galat.
"""
from datetime import date

from fastapi import APIRouter, Query

from services.bigmoney.idx_client import fetch_stock_summary

router = APIRouter(prefix="/diag", tags=["diag"])


@router.get("/idx")
def probe_idx(target: date = Query(default=date(2026, 7, 13))):
    try:
        rows = fetch_stock_summary(target)
    except Exception as exc:  # noqa: BLE001 — apa pun galatnya, itulah jawabannya
        return {"ok": False, "date": str(target), "error": f"{type(exc).__name__}: {exc}"}

    return {"ok": True, "date": str(target), "rows": len(rows)}
