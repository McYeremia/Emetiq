"""Tes agents/news_source — pengambilan & parsing Google News RSS.

HTTP di-mock. Berita basi adalah bahaya utama di sini: artikel tahun lalu akan
membuat laporan menjelaskan aliran dana hari ini dengan peristiwa yang sudah usang.
"""
from datetime import datetime, timedelta, timezone

import pytest

from services.bigmoney.agents import news_source
from services.bigmoney.agents.news_source import build_query, fetch_news, parse_feed


def _rfc822(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


def _feed(items: list[tuple[str, datetime]]) -> str:
    entries = "".join(
        f"<item><title>{title}</title><link>https://x/{i}</link>"
        f"<pubDate>{_rfc822(dt)}</pubDate><source>Kontan</source></item>"
        for i, (title, dt) in enumerate(items)
    )
    return f"<?xml version='1.0'?><rss><channel>{entries}</channel></rss>"


NOW = datetime.now(timezone.utc)


# --- query -------------------------------------------------------------------

def test_query_includes_ticker_and_company_name():
    query = build_query("CUAN", "Petrindo Jaya Kreasi Tbk.")

    assert "CUAN" in query
    assert "Petrindo" in query


def test_query_limits_to_recent_window():
    """Tanpa batas waktu, Google mengembalikan artikel tahun lalu — probe PSAB membuktikannya."""
    assert "when:7d" in build_query("PSAB", None)


def test_query_works_without_company_name():
    """~227 saham IDX tak ada di tabel stocks; jangan gagal, cukup pakai tickernya."""
    assert "PSAB" in build_query("PSAB", None)


# --- parsing -----------------------------------------------------------------

def test_parse_feed_extracts_articles():
    xml = _feed([("Prajogo jual 1,7 miliar saham CUAN", NOW - timedelta(days=1))])

    articles = parse_feed(xml, max_age_days=7)

    assert len(articles) == 1
    assert "Prajogo" in articles[0]["title"]
    assert articles[0]["url"].startswith("https://")
    assert articles[0]["published"]


def test_parse_feed_drops_stale_articles():
    """Berita basi lebih berbahaya daripada tak ada berita."""
    xml = _feed([
        ("Berita hari ini", NOW - timedelta(days=2)),
        ("Berita tahun lalu", NOW - timedelta(days=300)),
    ])

    articles = parse_feed(xml, max_age_days=7)

    assert [a["title"] for a in articles] == ["Berita hari ini"]


def test_parse_feed_sorts_newest_first():
    xml = _feed([
        ("Lama", NOW - timedelta(days=5)),
        ("Baru", NOW - timedelta(hours=2)),
    ])

    assert [a["title"] for a in parse_feed(xml, max_age_days=7)] == ["Baru", "Lama"]


def test_parse_feed_survives_broken_xml():
    """Feed rusak tak boleh menjatuhkan laporan — kembalikan kosong."""
    assert parse_feed("<rss><channel><item>bocor", max_age_days=7) == []


def test_parse_feed_keeps_article_without_date():
    """Tanpa pubDate kita tak bisa menilai kesegarannya — buang, jangan tebak."""
    xml = "<?xml version='1.0'?><rss><channel><item><title>Tanpa tanggal</title>" \
          "<link>https://x/1</link></item></channel></rss>"

    assert parse_feed(xml, max_age_days=7) == []


# --- fetch -------------------------------------------------------------------

def test_fetch_news_returns_parsed_articles(mocker):
    mocker.patch.object(news_source.httpx, "get", return_value=mocker.Mock(
        status_code=200, text=_feed([("Saham CUAN dilahap", NOW)])))

    articles = fetch_news("CUAN", "Petrindo", max_items=5)

    assert len(articles) == 1
    assert articles[0]["ticker"] == "CUAN"


def test_fetch_news_caps_item_count(mocker):
    """Prompt LLM punya batas; 100 judul akan menenggelamkan sinyalnya."""
    mocker.patch.object(news_source.httpx, "get", return_value=mocker.Mock(
        status_code=200,
        text=_feed([(f"Berita {i}", NOW - timedelta(hours=i)) for i in range(20)])))

    assert len(fetch_news("CUAN", None, max_items=3)) == 3


def test_fetch_news_returns_empty_on_network_error(mocker):
    """Google News tumbang tak boleh menjatuhkan laporan — berita itu pelengkap."""
    mocker.patch.object(news_source.httpx, "get", side_effect=RuntimeError("timeout"))

    assert fetch_news("CUAN", None) == []


def test_fetch_news_returns_empty_on_http_error(mocker):
    mocker.patch.object(news_source.httpx, "get",
                        return_value=mocker.Mock(status_code=503, text=""))

    assert fetch_news("CUAN", None) == []
