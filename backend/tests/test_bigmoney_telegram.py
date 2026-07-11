"""Tes services/bigmoney/telegram — format pesan, broadcast idempoten, penautan akun.

Bot API di-mock di semua tes; tak ada yang menyentuh jaringan atau butuh
TELEGRAM_BOT_TOKEN.
"""
from datetime import date, datetime, timedelta

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


# --- format pesan ------------------------------------------------------------

def test_report_message_carries_headline_and_top_picks(reported):
    text = format_report(reported.query(models.BigMoneyDailyReport).one())

    assert "Asing keluar dari Finance" in text
    assert "CUAN" in text and "GOTO" in text
    assert "2026-07-10" in text


def test_report_message_warns_on_pump_dump(reported):
    """Saham berbendera risiko harus tampil sebagai peringatan, bukan peluang."""
    text = format_report(reported.query(models.BigMoneyDailyReport).one())

    assert "RISIKO" in text.upper()


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
