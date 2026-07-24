"""Tes services/bigmoney/telegram — format pesan, broadcast idempoten, penautan akun.

Bot API di-mock di semua tes; tak ada yang menyentuh jaringan atau butuh
TELEGRAM_BOT_TOKEN.
"""
from datetime import date, datetime, timedelta

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import Base
from services.bigmoney import telegram
from services.bigmoney.telegram import (
    TelegramError,
    broadcast_report,
    format_report,
    issue_link_code,
    link_chat,
    render_top,
)

TARGET = date(2026, 7, 10)


@pytest.fixture(autouse=True)
def token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-palsu")


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def reported(db):
    db.add(models.BigMoneyDailyReport(
        date=TARGET, headline="Asing keluar dari Finance",
        narrative="Energy jadi satu-satunya penadah hari ini.\n\nParagraf kedua.",
        model="gemini-2.0-flash",
        context={
            "regime": {"volatility_regime": "VOLATILE", "trend_regime": "BULL",
                       "weight_set": "VOLATILE", "total_foreign_net_value": -285_410_584_421},
            "top_accumulation": [
                {"rank": 1, "ticker": "CUAN", "composite": 85.0, "conviction": "WATCH",
                 "phase": "AKUMULASI", "days_confirmed": 2, "foreign_net_value": 16_230_000_000,
                 "flags": {"divergence": False, "pump_dump_risk": False}},
                {"rank": 2, "ticker": "GOTO", "composite": 81.7, "conviction": "STRONG",
                 "phase": "AKUMULASI", "days_confirmed": 20, "foreign_net_value": 12_830_000_000,
                 "flags": {"divergence": False, "pump_dump_risk": True}},
            ],
        }))
    db.add(models.Profile(id="u-dev", email="dev@example.com", tier="dev", telegram_chat_id="111"))
    db.commit()
    return db


@pytest.fixture
def send(mocker):
    return mocker.patch("services.bigmoney.telegram.send_message")


# --- pengiriman & proxy ------------------------------------------------------

def test_send_message_hits_bot_api_directly_by_default(mocker, monkeypatch):
    """Tanpa TELEGRAM_API_BASE: tembak api.telegram.org langsung (jalur laptop)."""
    monkeypatch.delenv("TELEGRAM_API_BASE", raising=False)
    post = mocker.patch("services.bigmoney.telegram.httpx.post")
    post.return_value.status_code = 200

    telegram.send_message("111", "halo")

    url = post.call_args.args[0]
    assert url == "https://api.telegram.org/bottoken-palsu/sendMessage"
    assert "X-Proxy-Secret" not in post.call_args.kwargs["headers"]


def test_send_message_routes_through_proxy_when_base_set(mocker, monkeypatch):
    """TELEGRAM_API_BASE mengalihkan ke Worker; secret ikut supaya bukan open relay."""
    monkeypatch.setenv("TELEGRAM_API_BASE", "https://tg-proxy.example.workers.dev/")
    monkeypatch.setenv("TELEGRAM_PROXY_SECRET", "rahasia")
    post = mocker.patch("services.bigmoney.telegram.httpx.post")
    post.return_value.status_code = 200

    telegram.send_message("111", "halo")

    url = post.call_args.args[0]
    assert url == "https://tg-proxy.example.workers.dev/bottoken-palsu/sendMessage"
    assert post.call_args.kwargs["headers"]["X-Proxy-Secret"] == "rahasia"


def test_send_message_retries_transient_network_error(mocker, monkeypatch):
    """Satu kedipan jaringan tak boleh menelan balasan bot."""
    monkeypatch.setattr(telegram.time, "sleep", lambda _: None)
    post = mocker.patch("services.bigmoney.telegram.httpx.post")
    post.side_effect = [httpx.ConnectError("EOF"), mocker.Mock(status_code=200, text="{}")]

    telegram.send_message("111", "halo")

    assert post.call_count == 2


def test_send_message_gives_up_after_max_attempts(mocker, monkeypatch):
    """Gagal terus bukan kedipan — sebutkan jumlah percobaan dan host tujuannya."""
    monkeypatch.setattr(telegram.time, "sleep", lambda _: None)
    monkeypatch.setenv("TELEGRAM_API_BASE", "https://emetiq.vercel.app/api/tg")
    post = mocker.patch("services.bigmoney.telegram.httpx.post",
                        side_effect=httpx.ConnectError("EOF"))

    with pytest.raises(telegram.TelegramError, match="emetiq.vercel.app.*3 percobaan"):
        telegram.send_message("111", "halo")

    assert post.call_count == 3


def test_send_message_does_not_retry_http_rejection(mocker, monkeypatch):
    """403 secret salah itu deterministik; mengulanginya cuma menunda kabar buruk."""
    monkeypatch.setattr(telegram.time, "sleep", lambda _: None)
    post = mocker.patch("services.bigmoney.telegram.httpx.post")
    post.return_value = mocker.Mock(status_code=403, text="Forbidden")

    with pytest.raises(telegram.TelegramError, match="Ditolak"):
        telegram.send_message("111", "halo")

    assert post.call_count == 1


# --- format pesan ------------------------------------------------------------

def test_report_message_carries_headline_and_top_picks(reported):
    text = format_report(reported.query(models.BigMoneyDailyReport).one())

    assert "Asing keluar dari Finance" in text
    assert "CUAN" in text and "GOTO" in text
    assert "2026-07-10" in text


def test_report_message_warns_on_pump_dump(reported):
    """Saham berbendera risiko harus tampil sebagai peringatan, bukan peluang."""
    text = format_report(reported.query(models.BigMoneyDailyReport).one())

    assert "peringatan, bukan peluang" in text


def test_report_message_speaks_plainly(reported):
    """Pembacanya awam: istilah engine boleh muncul, tapi tak boleh berdiri sendiri."""
    text = format_report(reported.query(models.BigMoneyDailyReport).one())

    assert "sedang mengumpulkan diam-diam" in text
    assert "pasar bergejolak" in text and "tren naik" in text
    assert "Rezim:" not in text


def test_report_message_marks_daily_figure_as_today(reported):
    """Angka harian yang tak berlabel dikira total — itu keluhan yang memicu perubahan ini."""
    text = format_report(reported.query(models.BigMoneyDailyReport).one())

    assert "Hari ini Rp 16,2 miliar" in text


def test_report_says_money_left_when_market_is_negative(reported):
    """Tanda minus menuntut pembaca menerjemahkan sendiri; hari outflow paling sering terjadi."""
    text = format_report(reported.query(models.BigMoneyDailyReport).one())

    assert "keluar</b> dari pasar" in text
    assert "-285" not in text and "−285" not in text


def test_rupiah_uses_indonesian_number_format():
    """Pembacanya orang Indonesia: titik untuk ribuan, koma untuk desimal."""
    assert telegram._rupiah(1_204_300_000_000) == "Rp 1,2 triliun"
    assert telegram._rupiah(45_200_000_000) == "Rp 45,2 miliar"
    assert telegram._rupiah(-2_500_000_000_000) == "Rp -2,5 triliun"
    assert telegram._rupiah(None) == "tidak tersedia"


def test_report_message_shows_running_accumulation(db):
    """Posisi berjalan menjawab 'sebesar apa, selama berapa hari'."""
    db.add(models.BigMoneyDailyReport(
        date=TARGET, headline="Judul", narrative="Isi", model="gemini",
        context={
            "regime": {"volatility_regime": "CALM", "trend_regime": "BULL",
                       "total_foreign_net_value": 1_204_300_000_000},
            "top_accumulation": [
                {"rank": 1, "ticker": "CUAN", "composite": 82.0, "conviction": "STRONG",
                 "phase": "AKUMULASI", "days_confirmed": 5, "flags": {},
                 "foreign_net_value": 45_200_000_000,
                 "accumulated_value": 312_700_000_000, "inflow_days": 5,
                 "opened_on": "2026-07-14", "gain_since_entry_pct": 4.8},
            ],
        }))
    db.commit()

    text = format_report(db.query(models.BigMoneyDailyReport).one())

    assert "total Rp 312,7 miliar" in text
    assert "5 hari beli" in text
    assert "sejak 14 Jul" in text
    assert "+4,8%" in text


def test_report_message_falls_back_to_streak_without_position(reported):
    """Tanpa posisi aktif, 'total 0' akan berbohong — pakai hari beruntun saja."""
    text = format_report(reported.query(models.BigMoneyDailyReport).one())

    assert "2 hari beli beruntun" in text
    assert "total Rp" not in text


def test_report_message_carries_score_legend(reported):
    """Nilai 0-100 tanpa penjelasan asalnya tak berarti apa-apa bagi pembaca awam."""
    text = format_report(reported.query(models.BigMoneyDailyReport).one())

    assert "pada hari yang sama" in text
    assert "/skor" in text


def test_report_message_skips_legend_without_picks(reported):
    """Tanpa satu pun saham, legenda menjelaskan nilai yang tak ditampilkan di mana pun."""
    report = reported.query(models.BigMoneyDailyReport).one()
    report.context = {**report.context, "top_accumulation": []}

    text = format_report(report)

    assert "/skor" not in text
    assert "bukan nasihat investasi" in text.lower()


# --- batas panjang pesan -----------------------------------------------------

def test_report_message_stays_within_telegram_limit(reported):
    """Bot API menolak pesan >4096 satuan dengan HTTP 400, dan broadcast tetap
    menandai laporan terkirim — kegagalannya senyap, jadi jangan sampai terjadi."""
    report = reported.query(models.BigMoneyDailyReport).one()
    report.narrative = "Kalimat panjang tentang aliran dana asing. " * 200

    text = format_report(report)

    assert telegram._panjang(text) <= telegram._BATAS_PESAN


def test_truncated_report_keeps_numbers_and_disclaimer(reported):
    """Yang dipangkas hanya narasi. Angka, peringatan risiko, dan disclaimer harus utuh."""
    report = reported.query(models.BigMoneyDailyReport).one()
    report.narrative = "Kalimat panjang tentang aliran dana asing. " * 200

    text = format_report(report)

    assert "CUAN" in text and "GOTO" in text
    assert "Hari ini Rp 16,2 miliar" in text
    assert "peringatan, bukan peluang" in text
    assert "bukan nasihat investasi" in text.lower()


def test_truncated_report_says_it_was_truncated(reported):
    """Narasi yang berhenti mendadak terbaca seperti laporan cacat, bukan laporan dipotong."""
    report = reported.query(models.BigMoneyDailyReport).one()
    report.narrative = "Kalimat panjang tentang aliran dana asing. " * 200

    assert "dipotong" in format_report(report)


def test_truncation_never_leaves_half_an_html_entity(reported):
    """'&amp;' yang terpangkas jadi '&am' membuat Telegram menolak seluruh pesan."""
    report = reported.query(models.BigMoneyDailyReport).one()
    report.narrative = "PT Aneka Tambang & Mitra menyerap dana asing hari ini. " * 150

    text = format_report(report)

    assert all(";" in text[i:i + 8] for i, c in enumerate(text) if c == "&")


def test_short_report_is_left_alone(reported):
    """Laporan normal tak boleh ikut ditandai terpotong."""
    text = format_report(reported.query(models.BigMoneyDailyReport).one())

    assert "dipotong" not in text
    assert "Paragraf kedua." in text


def test_panjang_counts_the_way_telegram_does():
    """Telegram menghitung UTF-16: emoji dua satuan, huruf biasa satu."""
    assert telegram._panjang("abc") == 3
    assert telegram._panjang("📊") == 2


def test_report_message_includes_disclaimer(reported):
    text = format_report(reported.query(models.BigMoneyDailyReport).one()).lower()

    assert "bukan nasihat investasi" in text


def test_report_message_escapes_html(reported):
    """Judul dari LLM masuk ke parse_mode HTML — tanda < harus di-escape, bukan mem-parse."""
    report = reported.query(models.BigMoneyDailyReport).one()
    report.headline = "Asing <b>kabur</b> & pasar goyah"

    text = format_report(report)

    assert "&lt;b&gt;" in text and "&amp;" in text


def test_render_top_lists_ranked_tickers(reported):
    ctx = reported.query(models.BigMoneyDailyReport).one().context

    text = render_top(TARGET, ctx["top_accumulation"])

    assert "1." in text and "CUAN" in text
    assert "2." in text and "GOTO" in text


# --- broadcast ---------------------------------------------------------------

def test_broadcast_sends_only_to_linked_dev_profiles(reported, send):
    reported.add(models.Profile(id="u-free", email="a@example.com", tier="free", telegram_chat_id="222"))
    reported.add(models.Profile(id="u-dev2", email="b@example.com", tier="dev"))   # belum menaut
    reported.commit()

    sent = broadcast_report(TARGET, reported)

    assert sent == 1
    assert send.call_count == 1
    assert send.call_args.args[0] == "111"


def test_broadcast_marks_report_as_sent(reported, send):
    broadcast_report(TARGET, reported)

    assert reported.query(models.BigMoneyDailyReport).one().sent_at is not None


def test_broadcast_is_idempotent(reported, send):
    """Actions yang di-rerun tak boleh mengirim laporan yang sama dua kali."""
    broadcast_report(TARGET, reported)
    second = broadcast_report(TARGET, reported)

    assert second == 0
    assert send.call_count == 1


def test_broadcast_force_resends(reported, send):
    broadcast_report(TARGET, reported)
    broadcast_report(TARGET, reported, force=True)

    assert send.call_count == 2


def test_broadcast_without_report_sends_nothing(db, send):
    assert broadcast_report(TARGET, db) == 0
    send.assert_not_called()


def test_broadcast_survives_one_failing_chat(reported, send):
    """Satu chat memblokir bot tak boleh menghalangi pengiriman ke yang lain."""
    reported.add(models.Profile(id="u-dev2", email="b@example.com", tier="dev", telegram_chat_id="333"))
    reported.commit()
    send.side_effect = [TelegramError("chat diblokir"), None]

    sent = broadcast_report(TARGET, reported)

    assert sent == 1               # yang kedua tetap terkirim
    assert send.call_count == 2


def test_broadcast_skipped_without_token(reported, send, monkeypatch):
    """Token belum diset: diam-diam lewati, jangan jatuhkan pipeline harian."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    assert broadcast_report(TARGET, reported) == 0
    send.assert_not_called()


# --- penautan akun -----------------------------------------------------------

def test_issue_link_code_stores_code_with_expiry(db):
    db.add(models.Profile(id="u-dev", email="dev@example.com", tier="dev"))
    db.commit()

    code = issue_link_code("u-dev", db)

    profile = db.query(models.Profile).filter_by(id="u-dev").one()
    assert profile.telegram_link_code == code
    assert profile.telegram_code_expires_at > datetime.utcnow()


def test_link_chat_binds_chat_id_and_burns_the_code(db):
    db.add(models.Profile(id="u-dev", email="dev@example.com", tier="dev"))
    db.commit()
    code = issue_link_code("u-dev", db)

    assert link_chat(code, "999", db) is True

    profile = db.query(models.Profile).filter_by(id="u-dev").one()
    assert profile.telegram_chat_id == "999"
    assert profile.telegram_link_code is None   # sekali pakai


def test_link_chat_rejects_wrong_code(db):
    db.add(models.Profile(id="u-dev", email="dev@example.com", tier="dev"))
    db.commit()
    issue_link_code("u-dev", db)

    assert link_chat("SALAH123", "999", db) is False


def test_link_chat_rejects_expired_code(db):
    db.add(models.Profile(id="u-dev", email="dev@example.com", tier="dev"))
    db.commit()
    code = issue_link_code("u-dev", db)
    profile = db.query(models.Profile).filter_by(id="u-dev").one()
    profile.telegram_code_expires_at = datetime.utcnow() - timedelta(minutes=1)
    db.commit()

    assert link_chat(code, "999", db) is False
    assert db.query(models.Profile).filter_by(id="u-dev").one().telegram_chat_id is None


def test_link_code_is_not_guessable(db):
    """Kode sekali pakai adalah satu-satunya bukti kepemilikan — jangan pendek atau berpola."""
    db.add(models.Profile(id="u-dev", email="dev@example.com", tier="dev"))
    db.commit()

    codes = {issue_link_code("u-dev", db) for _ in range(20)}

    assert all(len(c) >= 8 for c in codes)
    assert len(codes) == 20   # tak ada tabrakan; bukan penghitung berurutan
