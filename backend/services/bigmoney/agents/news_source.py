"""Berita saham dari Google News RSS.

Dipilih setelah pengujian nyata, bukan asumsi. yfinance ditolak: probe ke saham top
akumulasi memberi CUAN 0 berita, PSAB 0 berita, BBRI satu artikel basi tujuh bulan.
Google News RSS mengembalikan artikel berbahasa Indonesia tertanggal hari yang sama,
gratis, tanpa API key, tanpa dependensi baru.

Tanpa LLM: berkas ini hanya mengambil dan mem-parse. Penilaian ada di news_worker.

Artikel basi DIBUANG, bukan dipakai apa adanya. Probe PSAB mengembalikan artikel
September 2025; berita usang lebih berbahaya daripada tak ada berita, karena ia akan
membuat laporan menjelaskan aliran dana hari ini dengan peristiwa tahun lalu.
"""
import logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger("bigmoney.news")

_RSS = "https://news.google.com/rss/search?q={query}&hl=id&gl=ID&ceid=ID:id"
_TIMEOUT = 15
_MAX_AGE_DAYS = 7
_MAX_ITEMS = 5
_UA = "Mozilla/5.0 (compatible; EMETIQ/1.0)"


def build_query(ticker: str, company_name: str | None) -> str:
    """Query Google News untuk satu saham.

    `when:7d` bukan hiasan: tanpa itu Google dengan senang hati mengembalikan artikel
    setahun lalu, dan laporan akan menjelaskan aliran dana hari ini dengan peristiwa usang.

    Nama perusahaan dipakai bila ada — ~227 saham IDX tak terdaftar di tabel `stocks`,
    dan untuk mereka ticker saja harus cukup.
    """
    parts = [f"saham {ticker}"]
    if company_name:
        # Buang akhiran badan hukum: "Tbk." dan "PT" cuma mengaburkan pencarian.
        cleaned = company_name.replace("Tbk.", "").replace("Tbk", "").replace("PT ", "").strip()
        if cleaned:
            parts.append(cleaned)
    parts.append(f"when:{_MAX_AGE_DAYS}d")
    return " ".join(parts)


def parse_feed(xml: str, max_age_days: int = _MAX_AGE_DAYS) -> list[dict]:
    """RSS → daftar artikel, terbaru dulu. Feed rusak menghasilkan daftar kosong.

    Artikel tanpa `pubDate` dibuang: tanpa tanggal, kesegarannya tak bisa dinilai, dan
    menebak lebih buruk daripada melewatkan.
    """
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        logger.warning("Feed berita tak bisa di-parse: %s", exc)
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    articles: list[dict] = []
    for item in root.findall(".//item"):
        raw_date = item.findtext("pubDate")
        if not raw_date:
            continue
        try:
            published = parsedate_to_datetime(raw_date)
        except (TypeError, ValueError):
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        if published < cutoff:
            continue

        articles.append({
            "title": (item.findtext("title") or "").strip(),
            "url": (item.findtext("link") or "").strip(),
            "source": (item.findtext("source") or "").strip(),
            "published": published.isoformat(),
            "_sort": published,
        })

    articles.sort(key=lambda a: a["_sort"], reverse=True)
    for article in articles:
        del article["_sort"]
    return articles


def fetch_news(ticker: str, company_name: str | None, max_items: int = _MAX_ITEMS) -> list[dict]:
    """Berita terkini satu saham. Daftar kosong bila gagal — berita adalah pelengkap.

    Google News tumbang tak boleh menjatuhkan laporan; laporan tanpa konteks berita
    masih jauh lebih berguna daripada tak ada laporan.
    """
    url = _RSS.format(query=quote_plus(build_query(ticker, company_name)))

    try:
        response = httpx.get(url, timeout=_TIMEOUT, follow_redirects=True,
                             headers={"User-Agent": _UA})
    except Exception as exc:   # noqa: BLE001 — httpx melempar aneka galat jaringan
        logger.warning("Gagal mengambil berita %s: %s", ticker, exc)
        return []

    if response.status_code >= 400:
        logger.warning("Google News menolak %s: HTTP %s", ticker, response.status_code)
        return []

    articles = parse_feed(response.text)[:max_items]
    for article in articles:
        article["ticker"] = ticker
    return articles
