"""
Broker Flow scraper — mengambil data aktivitas broker harian dari IDX resmi.

Source: https://www.idx.co.id/primary/TradingSummary/GetBrokerSummary
Data: AGGREGATE seluruh pasar per hari (bukan per-saham).
      Menampilkan broker mana yang paling aktif bertransaksi di IDX.

Langkah:
1. Ambil session cookie dari idx.co.id/id
2. Gunakan cookie tersebut untuk hit endpoint GetBrokerSummary
"""

import time
from datetime import date
from sqlalchemy.orm import Session
from curl_cffi import requests as cffi_requests

import models

_IDX_HOME   = "https://www.idx.co.id/id"
_IDX_BROKER = "https://www.idx.co.id/primary/TradingSummary/GetBrokerSummary"


def scrape_broker_flow(target_date: date, db: Session) -> int:
    """
    Scrape IDX untuk data aktivitas broker harian pada target_date.
    Data bersifat AGGREGATE (seluruh pasar, bukan per-saham).
    Menggunakan curl_cffi untuk impersonate Chrome (bypass TLS fingerprint check IDX).

    Return: jumlah baris broker yang berhasil disimpan.
    Raise RuntimeError jika gagal.
    """
    session = cffi_requests.Session(impersonate="chrome120")

    # Step 1: Visit homepage untuk dapat session cookie
    try:
        session.get(_IDX_HOME, timeout=20)
    except Exception as e:
        raise RuntimeError(f"Gagal ambil session dari IDX: {e}")

    # Step 2: Fetch broker summary dengan session yang sudah punya cookie
    date_str = target_date.strftime("%Y-%m-%d")
    all_rows: list = []
    start  = 0
    length = 100

    while True:
        url = f"{_IDX_BROKER}?length={length}&start={start}&date={date_str}"
        try:
            resp = session.get(
                url,
                timeout=20,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": "https://www.idx.co.id/id/data-pasar/ringkasan-perdagangan/ringkasan-broker/",
                },
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:
            raise RuntimeError(f"Gagal fetch IDX broker summary: {e}")

        # IDX mengembalikan {"data": [...], "recordsTotal": N, ...}
        data = payload.get("data") or payload.get("Data") or []
        if not data:
            break

        all_rows.extend(data)
        total = payload.get("recordsTotal") or payload.get("RecordsTotal") or len(data)
        start += length
        if start >= total:
            break
        time.sleep(0.5)

    if not all_rows:
        raise RuntimeError(
            f"Tidak ada data broker dari IDX untuk tanggal {date_str}. "
            "Pastikan tanggal adalah hari bursa (Senin-Jumat, bukan libur nasional)."
        )

    # Step 3: Upsert ke DB
    saved = 0
    for item in all_rows:
        # IDX field names: IDFirm, FirmName, Value, Volume, Frequency
        code = str(item.get("IDFirm") or item.get("BrokerCode") or item.get("brokerCode") or "").strip()
        if not code:
            continue

        name  = str(item.get("FirmName")   or item.get("BrokerName")  or item.get("brokerName")  or "").strip()
        value = int(item.get("Value")      or item.get("TotalValue")  or item.get("totalValue")  or 0)
        vol   = int(item.get("Volume")     or item.get("volume")      or 0)
        freq  = int(item.get("Frequency")  or item.get("frequency")   or 0)

        existing = (
            db.query(models.BrokerFlow)
            .filter_by(date=target_date, broker_code=code)
            .first()
        )
        if existing:
            existing.broker_name = name
            existing.total_value = value
            existing.volume      = vol
            existing.frequency   = freq
        else:
            db.add(models.BrokerFlow(
                date=target_date,
                broker_code=code,
                broker_name=name,
                total_value=value,
                volume=vol,
                frequency=freq,
            ))
        saved += 1

    db.commit()
    return saved
