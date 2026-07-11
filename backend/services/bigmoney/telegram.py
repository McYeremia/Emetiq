"""Pengiriman laporan Big Money ke Telegram.

Bot ini mendorong laporan keluar; ia bukan lawan bicara. Karena itu tak ada
proses bot yang berjalan terus-menerus dan tak ada dependensi baru — cukup Bot
API lewat httpx yang sudah terpasang, dipanggil dari pipeline harian.

Penautan akun memakai KODE SEKALI PAKAI yang dibuat saat user sudah login, bukan
dengan mengetik email di bot seperti spec lama. Email adalah identitas, bukan
bukti kepemilikan: kalau email jadi kuncinya, siapa pun yang tahu email orang
lain bisa membajak notifikasinya.
"""
import html
import logging
import os
import secrets
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy.orm import Session

import models

logger = logging.getLogger("bigmoney.telegram")

_API = "https://api.telegram.org/bot{token}/sendMessage"
_TIMEOUT = 15
_CODE_TTL_MINUTES = 15
_CODE_BYTES = 6          # ~10 karakter base32 — cukup panjang untuk tak bisa ditebak
_TOP_IN_MESSAGE = 5

DISCLAIMER = "⚠️ Estimasi, bukan nasihat investasi."


class TelegramError(RuntimeError):
    """Bot API menolak atau tak bisa dihubungi."""


def is_configured() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN"))


def send_message(chat_id: str, text: str) -> None:
    """Kirim satu pesan HTML. Melempar TelegramError bila gagal."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise TelegramError("TELEGRAM_BOT_TOKEN belum diset")

    try:
        response = httpx.post(
            _API.format(token=token),
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=_TIMEOUT,
        )
    except Exception as exc:   # noqa: BLE001 — httpx melempar aneka galat jaringan
        raise TelegramError(f"Gagal menghubungi Telegram: {exc}") from exc

    if response.status_code >= 400:
        raise TelegramError(f"Telegram menolak: HTTP {response.status_code} {response.text[:200]}")


def _rupiah(value) -> str:
    if value is None:
        return "n/a"
    miliar = value / 1_000_000_000
    return f"Rp {miliar:,.1f} M"


def _pick_line(pick: dict) -> str:
    flags = pick.get("flags") or {}
    ticker = html.escape(str(pick["ticker"]))
    line = (f"{pick['rank']}. <b>{ticker}</b> · skor {pick['composite']:.0f} · "
            f"{html.escape(pick['phase'])} · asing {_rupiah(pick.get('foreign_net_value'))}")
    if flags.get("pump_dump_risk"):
        line += "\n   🚨 RISIKO PUMP-DUMP — perlakukan sebagai peringatan, bukan peluang"
    elif flags.get("divergence"):
        line += "\n   ⚠️ divergensi harga vs aliran asing"
    return line


def format_report(report: models.BigMoneyDailyReport) -> str:
    """Laporan harian → pesan HTML Telegram.

    Teks dari LLM di-escape: judul yang kebetulan memuat `<` atau `&` akan
    membuat Telegram menolak seluruh pesan bila dikirim mentah.
    """
    context = report.context or {}
    regime = context.get("regime") or {}
    top = context.get("top_accumulation") or []

    lines = [
        f"📊 <b>Big Money — {report.date}</b>",
        "",
        f"<b>{html.escape(report.headline or '')}</b>",
    ]

    if report.narrative:
        lines += ["", html.escape(report.narrative)]

    lines += [
        "",
        f"🔎 <b>Rezim:</b> {html.escape(str(regime.get('volatility_regime')))} · "
        f"{html.escape(str(regime.get('trend_regime')))}",
        f"Net asing pasar: {_rupiah(regime.get('total_foreign_net_value'))}",
    ]

    if top:
        lines += ["", "🏆 <b>Top Akumulasi</b>"]
        lines += [_pick_line(p) for p in top[:_TOP_IN_MESSAGE]]

    lines += ["", DISCLAIMER]
    return "\n".join(lines)


def render_top(target: date, picks: list[dict]) -> str:
    """Daftar top akumulasi tanpa narasi — jawaban untuk perintah /top."""
    if not picks:
        return f"Belum ada peringkat untuk {target}."

    lines = [f"🏆 <b>Top Akumulasi — {target}</b>", ""]
    lines += [_pick_line(p) for p in picks[:_TOP_IN_MESSAGE]]
    lines += ["", DISCLAIMER]
    return "\n".join(lines)


def _linked_dev_chats(db: Session) -> list[str]:
    """Chat yang berhak menerima: tertaut DAN tier dev (fitur masih dev-mode)."""
    rows = (
        db.query(models.Profile.telegram_chat_id)
          .filter(models.Profile.telegram_chat_id.isnot(None))
          .filter(models.Profile.tier == "dev")
          .all()
    )
    return [chat_id for (chat_id,) in rows]


def broadcast_report(target: date, db: Session, force: bool = False) -> int:
    """Kirim laporan `target` ke semua chat dev yang tertaut. Mengembalikan jumlah terkirim.

    Idempoten lewat `sent_at`: workflow yang di-rerun tak mengirim ulang laporan
    yang sama. `force=True` menembusnya.

    Tanpa TELEGRAM_BOT_TOKEN, fungsi ini diam dan mengembalikan 0 — Telegram adalah
    lapisan pemberitahuan, dan ketiadaannya tak boleh menjatuhkan pipeline data.
    """
    if not is_configured():
        logger.warning("Broadcast dilewati: TELEGRAM_BOT_TOKEN belum diset")
        return 0

    report = (
        db.query(models.BigMoneyDailyReport)
          .filter(models.BigMoneyDailyReport.date == target)
          .one_or_none()
    )
    if report is None:
        logger.info("%s belum punya laporan — tak ada yang dikirim", target)
        return 0
    if report.sent_at is not None and not force:
        logger.info("%s sudah pernah dikirim", target)
        return 0

    text = format_report(report)

    sent = 0
    for chat_id in _linked_dev_chats(db):
        try:
            send_message(chat_id, text)
        except TelegramError as exc:
            # Satu chat memblokir bot tak boleh menghentikan pengiriman ke yang lain.
            logger.error("Gagal kirim ke chat %s: %s", chat_id, exc)
        else:
            sent += 1

    report.sent_at = datetime.utcnow()
    db.commit()

    logger.info("%s laporan terkirim ke %d chat", target, sent)
    return sent


def issue_link_code(user_id: str, db: Session) -> str:
    """Buat kode tautan sekali pakai untuk user yang SEDANG LOGIN.

    Kodenya acak-kriptografis, bukan penghitung: ia satu-satunya bukti kepemilikan
    yang dipegang bot, dan kode yang bisa ditebak berarti akun yang bisa dibajak.
    """
    code = secrets.token_hex(_CODE_BYTES).upper()

    profile = db.query(models.Profile).filter(models.Profile.id == user_id).one()
    profile.telegram_link_code = code
    profile.telegram_code_expires_at = datetime.utcnow() + timedelta(minutes=_CODE_TTL_MINUTES)
    db.commit()

    return code


def link_chat(code: str, chat_id: str, db: Session) -> bool:
    """Tautkan `chat_id` ke profil pemilik `code`. False bila kode salah atau kedaluwarsa.

    Kode dibakar setelah dipakai: satu kode, satu chat.
    """
    profile = (
        db.query(models.Profile)
          .filter(models.Profile.telegram_link_code == (code or "").strip().upper())
          .one_or_none()
    )
    if profile is None:
        return False

    expired = (
        profile.telegram_code_expires_at is None
        or profile.telegram_code_expires_at < datetime.utcnow()
    )
    if expired:
        logger.info("Kode tautan kedaluwarsa untuk profil %s", profile.id)
        return False

    profile.telegram_chat_id = str(chat_id)
    profile.telegram_link_code = None
    profile.telegram_code_expires_at = None
    db.commit()

    return True
