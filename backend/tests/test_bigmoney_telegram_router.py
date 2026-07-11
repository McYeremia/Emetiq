"""Tes endpoint Telegram: kode tautan (butuh login dev) dan webhook (publik, ber-secret).

Webhook TIDAK bisa memakai auth Supabase — Telegram yang memanggilnya, bukan browser
user. Penggantinya secret_token yang hanya diketahui Telegram dan kita. Tanpa itu,
siapa pun di internet bisa memberi perintah atas nama chat mana pun.
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import CurrentUser, get_current_user
from database import Base, get_db
import main
import models

SECRET = "rahasia-webhook"


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-palsu")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Factory = sessionmaker(bind=engine)
    db = Factory()
    db.add(models.Profile(id="u-dev", email="dev@example.com", tier="dev"))
    db.commit()
    db.close()
    return Factory


@pytest.fixture
def make_client(session_factory):
    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def _make(tier="dev"):
        main.app.dependency_overrides[get_db] = override_db
        main.app.dependency_overrides[get_current_user] = lambda: CurrentUser("u-dev", None, tier)
        return TestClient(main.app)

    yield _make
    main.app.dependency_overrides.clear()


@pytest.fixture
def send(mocker):
    return mocker.patch("services.bigmoney.telegram.send_message")


def _update(text: str, chat_id: str = "555") -> dict:
    return {"message": {"chat": {"id": int(chat_id)}, "text": text}}


# --- kode tautan -------------------------------------------------------------

def test_issue_code_requires_dev_tier(make_client):
    assert make_client(tier="pro").post("/bigmoney/telegram/code").status_code == 403


def test_issue_code_returns_code_for_dev(make_client):
    body = make_client().post("/bigmoney/telegram/code").json()

    assert len(body["code"]) >= 8
    assert body["expires_in_minutes"] > 0


# --- webhook -----------------------------------------------------------------

def test_webhook_rejects_request_without_secret(make_client, send):
    """Tanpa secret, siapa pun di internet bisa menyamar jadi Telegram."""
    response = make_client().post("/bigmoney/telegram/webhook", json=_update("/report"))

    assert response.status_code == 403
    send.assert_not_called()


def test_webhook_rejects_wrong_secret(make_client, send):
    response = make_client().post(
        "/bigmoney/telegram/webhook",
        json=_update("/report"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "salah"},
    )

    assert response.status_code == 403
    send.assert_not_called()


def _post(client, update):
    return client.post(
        "/bigmoney/telegram/webhook",
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )


def test_start_with_valid_code_links_chat(make_client, send, session_factory):
    client = make_client()
    code = client.post("/bigmoney/telegram/code").json()["code"]

    assert _post(client, _update(f"/start {code}", chat_id="555")).status_code == 200

    db = session_factory()
    assert db.query(models.Profile).filter_by(id="u-dev").one().telegram_chat_id == "555"
    db.close()
    assert "terhubung" in send.call_args.args[1].lower()


def test_start_with_bad_code_does_not_link(make_client, send, session_factory):
    client = make_client()
    client.post("/bigmoney/telegram/code")

    _post(client, _update("/start KODESALAH", chat_id="555"))

    db = session_factory()
    assert db.query(models.Profile).filter_by(id="u-dev").one().telegram_chat_id is None
    db.close()
    assert "tidak valid" in send.call_args.args[1].lower()


def test_start_without_code_explains_how_to_link(make_client, send):
    _post(make_client(), _update("/start"))

    assert "kode" in send.call_args.args[1].lower()


def test_report_command_requires_linked_chat(make_client, send):
    """Chat asing tak boleh memanen laporan cuma dengan mengetik /report."""
    _post(make_client(), _update("/report", chat_id="999"))

    assert "belum terhubung" in send.call_args.args[1].lower()


def test_report_command_sends_latest_report_to_linked_chat(make_client, send, session_factory):
    db = session_factory()
    db.query(models.Profile).filter_by(id="u-dev").one().telegram_chat_id = "555"
    db.add(models.BigMoneyDailyReport(
        date=date(2026, 7, 10), headline="Asing keluar dari Finance", narrative="Isi laporan.",
        model="gemini-2.0-flash", context={"regime": {}, "top_accumulation": []}))
    db.commit()
    db.close()

    _post(make_client(), _update("/report", chat_id="555"))

    assert "Asing keluar dari Finance" in send.call_args.args[1]


def test_unknown_command_is_answered_not_ignored(make_client, send):
    _post(make_client(), _update("halo bot", chat_id="555"))

    assert send.called


def test_webhook_always_returns_200_so_telegram_stops_retrying(make_client, send):
    """Galat internal tak boleh membuat Telegram mengulang update yang sama tanpa henti."""
    send.side_effect = RuntimeError("bot diblokir")

    assert _post(make_client(), _update("/report", chat_id="555")).status_code == 200
