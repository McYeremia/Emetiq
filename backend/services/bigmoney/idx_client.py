"""Klien HTTP untuk IDX Trading Summary.

Hanya bicara HTTP: tidak tahu apa-apa soal database maupun model ORM.

IDX memeriksa TLS fingerprint, jadi `requests` biasa akan ditolak. `curl_cffi`
dengan impersonate Chrome lolos — pola yang sama sudah dipakai
services/broker_scraper.py.

Hari non-bursa (akhir pekan, libur) dibalas HTTP 200 dengan nol baris, bukan
error. Terverifikasi: Sabtu 2026-07-04 → 0 baris; Rabu 2026-07-08 → 963 baris.
"""
import time
from datetime import date

from curl_cffi import requests as cffi_requests

_IDX_HOME = "https://www.idx.co.id/id"
_IDX_STOCK_SUMMARY = "https://www.idx.co.id/primary/TradingSummary/GetStockSummary"
_REFERER = "https://www.idx.co.id/id/data-pasar/ringkasan-perdagangan/ringkasan-saham/"

_PAGE_SIZE = 1000      # seluruh pasar (~964 baris) muat dalam satu halaman
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (1, 3, 9)
_TIMEOUT = 30


class IdxFetchError(RuntimeError):
    """Gagal mengambil data dari IDX setelah semua percobaan ulang."""


def _new_session():
    """Sesi ber-cookie. IDX menolak endpoint /primary tanpa cookie dari homepage."""
    session = cffi_requests.Session(impersonate="chrome120")
    try:
        session.get(_IDX_HOME, timeout=_TIMEOUT)
    except Exception as exc:
        raise IdxFetchError(f"Gagal membuka sesi IDX: {exc}") from exc
    return session


def _get_json(session, url: str) -> dict:
    """GET dengan retry berjenjang. 4xx tidak diulang — permintaannya yang salah."""
    headers = {
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": _REFERER,
    }
    last_error: Exception | None = None

    for attempt in range(_MAX_ATTEMPTS):
        try:
            resp = session.get(url, timeout=_TIMEOUT, headers=headers)
        except Exception as exc:
            last_error = IdxFetchError(f"Galat jaringan ke IDX: {exc}")
        else:
            if 400 <= resp.status_code < 500:
                raise IdxFetchError(f"IDX menolak permintaan: HTTP {resp.status_code}")
            if resp.status_code >= 500:
                last_error = IdxFetchError(f"IDX galat server: HTTP {resp.status_code}")
            else:
                try:
                    return resp.json()
                except Exception as exc:
                    last_error = IdxFetchError(f"Respons IDX bukan JSON: {exc}")

        if attempt < _MAX_ATTEMPTS - 1:
            time.sleep(_BACKOFF_SECONDS[attempt])

    raise last_error


def fetch_stock_summary(target: date) -> list[dict]:
    """Ambil ringkasan perdagangan seluruh saham untuk satu tanggal.

    Mengembalikan daftar dict mentah IDX, atau [] bila bukan hari bursa.
    Melempar IdxFetchError pada kegagalan jaringan atau HTTP.
    """
    session = _new_session()
    date_str = target.strftime("%Y-%m-%d")

    rows: list[dict] = []
    start = 0
    while True:
        url = f"{_IDX_STOCK_SUMMARY}?length={_PAGE_SIZE}&start={start}&date={date_str}"
        payload = _get_json(session, url)

        page = payload.get("data") or []
        if not page:
            break

        rows.extend(page)
        total = payload.get("recordsTotal") or len(rows)
        start += _PAGE_SIZE
        if start >= total:
            break
        time.sleep(0.5)

    return rows
