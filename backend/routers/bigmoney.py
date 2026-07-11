"""Endpoint Big Money — report-only, khusus tier dev.

Report-only dengan sengaja: tak ada endpoint yang menyuruh membeli atau menjual.
Fitur ini alat bantu analisis, bukan nasihat investasi, dan tiap respons memikul
disclaimer-nya sendiri supaya UI tak bisa "lupa" menampilkannya.

Dikunci ke tier dev (`require_dev`) sampai Broker Flow siap rilis: sinyal setengah
matang yang bocor ke publik lebih berbahaya daripada tak ada sinyal sama sekali.

Router ini hanya MEMBACA. Perhitungan dijalankan lewat scripts/bigmoney_score.py
dan scripts/bigmoney_report.py — tak ada endpoint yang memicu pipeline, supaya
satu permintaan HTTP tak bisa menyandera worker selama berpuluh detik.
"""
import logging
import os
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import CurrentUser, require_dev
from database import get_db
import models
from services.bigmoney import telegram

log = logging.getLogger("bigmoney.router")

router = APIRouter(prefix="/bigmoney", tags=["bigmoney"])

DISCLAIMER = (
    "Nilai aliran dana asing adalah ESTIMASI (net lembar dikali VWAP pasar) — IDX tidak "
    "menyediakan harga per sisi asing. Skor bersifat relatif terhadap saham lain pada hari "
    "yang sama. Alat bantu analisis, BUKAN NASIHAT INVESTASI."
)


def _latest_date(db: Session, column) -> date | None:
    return db.query(func.max(column)).scalar()


@router.get("/regime")
def get_regime(
    target: date | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_dev),
):
    """Rezim pasar pada satu tanggal (default: yang terakhir dihitung)."""
    target = target or _latest_date(db, models.BigMoneyMarketRegime.date)
    regime = (
        db.query(models.BigMoneyMarketRegime)
          .filter(models.BigMoneyMarketRegime.date == target)
          .one_or_none()
        if target else None
    )
    if regime is None:
        raise HTTPException(status_code=404, detail="Rezim untuk tanggal itu belum dihitung")

    return {
        "date": str(regime.date),
        "volatility_regime": regime.volatility_regime,
        "trend_regime": regime.trend_regime,
        "weight_set": regime.weight_set,
        "market_return_pct": regime.market_return_pct,
        "market_volatility_20d": regime.market_volatility_20d,
        "breadth": regime.breadth,
        "total_foreign_net_value": regime.total_foreign_net_value,
        "sector_rotation": regime.sector_rotation or {},
        "disclaimer": DISCLAIMER,
    }


@router.get("/top-accumulation")
def get_top_accumulation(
    target: date | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_dev),
):
    """Peringkat top akumulasi beserta BUKTI-nya.

    Subskor, hari inflow beruntun, dan flags ikut dikirim: halaman report-only harus
    bisa menunjukkan atas dasar apa sebuah saham naik peringkat, bukan cuma bahwa ia naik.
    """
    target = target or _latest_date(db, models.BigMoneyTopAccumulation.date)
    if target is None:
        return {"date": None, "data": [], "disclaimer": DISCLAIMER}

    rows = (
        db.query(models.BigMoneyTopAccumulation)
          .filter(models.BigMoneyTopAccumulation.date == target)
          .order_by(models.BigMoneyTopAccumulation.rank)
          .all()
    )

    scores = {
        s.ticker: s
        for s in db.query(models.BigMoneyScore).filter(models.BigMoneyScore.date == target).all()
    }
    dailies = {
        d.ticker: d
        for d in db.query(models.BigMoneyStockDaily)
                   .filter(models.BigMoneyStockDaily.date == target)
                   .all()
    }

    data = []
    for row in rows:
        score = scores.get(row.ticker)
        daily = dailies.get(row.ticker)
        data.append({
            "rank": row.rank,
            "ticker": row.ticker,
            "composite": row.composite,
            "conviction": row.conviction,
            "phase": row.phase,
            "days_confirmed": score.days_confirmed if score else None,
            "flags": score.flags if score else None,
            "subscores": {
                "relative_foreign_flow": score.s_relative_foreign_flow,
                "foreign_persistence": score.s_foreign_persistence,
                "big_ticket": score.s_big_ticket,
                "cost_basis": score.s_cost_basis,
                "volume_price": score.s_volume_price,
            } if score else None,
            "close": daily.close if daily else None,
            "change_pct": daily.change_pct if daily else None,
            "foreign_net_value": daily.foreign_net_value if daily else None,
        })

    return {"date": str(target), "data": data, "disclaimer": DISCLAIMER}


@router.get("/report/latest")
def get_latest_report(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_dev),
):
    """Laporan harian terakhir. Belum ada laporan bukan galat — kembalikan report=None."""
    report = (
        db.query(models.BigMoneyDailyReport)
          .order_by(models.BigMoneyDailyReport.date.desc())
          .first()
    )
    if report is None:
        return {"report": None, "disclaimer": DISCLAIMER}

    return {
        "report": True,
        "date": str(report.date),
        "headline": report.headline,
        "narrative": report.narrative,
        "model": report.model,
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        "disclaimer": DISCLAIMER,
    }


# ── Telegram ─────────────────────────────────────────────────────────────────
#
# Penautan akun memakai kode sekali pakai yang diterbitkan untuk user yang SEDANG
# LOGIN. Spec lama meminta user mengetik email di bot; itu tak aman — email adalah
# identitas, bukan bukti kepemilikan, dan siapa pun yang tahu email orang lain akan
# bisa membajak notifikasinya.

BOT_HELP = (
    "Perintah:\n"
    "/start &lt;kode&gt; — hubungkan akun EMETIQ\n"
    "/report — laporan Big Money terakhir\n"
    "/top — peringkat top akumulasi"
)


@router.post("/telegram/code")
def issue_telegram_code(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_dev),
):
    """Terbitkan kode tautan sekali pakai untuk user yang sedang login."""
    code = telegram.issue_link_code(user.id, db)
    return {
        "code": code,
        "expires_in_minutes": telegram._CODE_TTL_MINUTES,
        "instruction": f"Kirim /start {code} ke bot Telegram EMETIQ.",
    }


def _profile_by_chat(chat_id: str, db: Session) -> models.Profile | None:
    return (
        db.query(models.Profile)
          .filter(models.Profile.telegram_chat_id == chat_id)
          .one_or_none()
    )


def _handle_command(text: str, chat_id: str, db: Session) -> str:
    """Perintah bot → teks balasan. Tanpa I/O Telegram, supaya bisa diuji langsung."""
    command, _, argument = text.strip().partition(" ")
    command = command.lower()

    if command == "/start":
        code = argument.strip()
        if not code:
            return ("Kirim kode tautan Anda: <code>/start KODE</code>\n\n"
                    "Kode dibuat di halaman Big Money EMETIQ setelah Anda masuk.")
        if telegram.link_chat(code, chat_id, db):
            return "✅ Akun terhubung. Laporan Big Money harian akan dikirim ke sini."
        return "❌ Kode tidak valid atau sudah kedaluwarsa. Buat kode baru di halaman Big Money."

    profile = _profile_by_chat(chat_id, db)
    if profile is None:
        return ("Chat ini belum terhubung ke akun EMETIQ. "
                "Buat kode di halaman Big Money lalu kirim <code>/start KODE</code>.")

    if command == "/report":
        report = (
            db.query(models.BigMoneyDailyReport)
              .order_by(models.BigMoneyDailyReport.date.desc())
              .first()
        )
        if report is None:
            return "Belum ada laporan."
        return telegram.format_report(report)

    if command == "/top":
        latest = _latest_date(db, models.BigMoneyTopAccumulation.date)
        if latest is None:
            return "Belum ada peringkat."
        context = (
            db.query(models.BigMoneyDailyReport)
              .filter(models.BigMoneyDailyReport.date == latest)
              .one_or_none()
        )
        picks = (context.context or {}).get("top_accumulation", []) if context else []
        return telegram.render_top(latest, picks)

    return BOT_HELP


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    secret: str | None = Header(None, alias="X-Telegram-Bot-Api-Secret-Token"),
    db: Session = Depends(get_db),
):
    """Terima update dari Telegram.

    Tak bisa memakai auth Supabase — pemanggilnya Telegram, bukan browser user.
    Penggantinya secret_token yang disetel saat mendaftarkan webhook; tanpa itu,
    siapa pun di internet bisa memberi perintah atas nama chat mana pun.

    SELALU membalas 200: galat internal yang membalas 5xx membuat Telegram
    mengulang update yang sama berkali-kali.
    """
    expected = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Secret token tidak cocok")

    try:
        update = await request.json()
        message = update.get("message") or {}
        chat_id = str((message.get("chat") or {}).get("id") or "")
        text = message.get("text") or ""

        if chat_id and text:
            telegram.send_message(chat_id, _handle_command(text, chat_id, db))
    except Exception as exc:   # noqa: BLE001 — lihat docstring: jangan memancing pengulangan
        log.error("Gagal memproses update Telegram: %s", exc)

    return {"ok": True}
