"""Pipeline harian Big Money: ingest → skor → laporan.

Tiga tahap dengan tingkat kepentingan yang berbeda, dan pipeline memperlakukannya
begitu. Ingest dan scoring adalah datanya — kalau gagal, galatnya naik ke pemanggil
dan job-nya merah. Laporan Gemini adalah narasinya — kalau gagal atau key-nya belum
ada, tahap itu dilewati dan skor yang sudah tersimpan tetap berdiri.

Kebalikannya, membiarkan LLM menjatuhkan seluruh pipeline berarti kehilangan data
sehari hanya karena kuota habis. Itu tukar-tambah yang buruk.
"""
import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from services.bigmoney.agents.supervisor import run_report
from services.bigmoney.engine import compute_scores
from services.bigmoney.ingest import ingest_stock_summary
from services.bigmoney.llm import LlmError, is_configured
from services.bigmoney.telegram import broadcast_report

logger = logging.getLogger("bigmoney.pipeline")


@dataclass(frozen=True)
class PipelineResult:
    date: date
    trading_day: bool
    ingested: int = 0
    updated: int = 0
    scored: int = 0
    strong: int = 0
    watch: int = 0
    headline: str | None = None
    report_skipped: bool = False
    report_error: str | None = None
    broadcast_sent: int = 0


def run_daily_pipeline(target: date, db: Session, with_report: bool = True) -> PipelineResult:
    """Jalankan satu hari penuh: ambil data IDX, hitung skor, tulis laporan.

    Hari non-bursa berhenti setelah ingest: tak ada yang bisa diskor, dan memanggil
    Gemini untuk hari kosong cuma membakar kuota.
    """
    ingested = ingest_stock_summary(target, db)
    if not ingested.trading_day:
        logger.info("%s bukan hari bursa — pipeline berhenti", target)
        return PipelineResult(date=target, trading_day=False)

    logger.info("%s ingest: +%d baru, %d diperbarui", target, ingested.inserted, ingested.updated)

    scores = compute_scores(target, db)
    logger.info("%s skor: %d saham | STRONG %d | WATCH %d",
                target, scores.scored, scores.strong, scores.watch)

    base = dict(
        date=target,
        trading_day=True,
        ingested=ingested.inserted,
        updated=ingested.updated,
        scored=scores.scored,
        strong=scores.strong,
        watch=scores.watch,
    )

    if not with_report:
        return PipelineResult(**base, report_skipped=True)

    if not is_configured():
        logger.warning("%s laporan dilewati: GEMINI_API_KEY belum diset", target)
        return PipelineResult(**base, report_skipped=True)

    try:
        report = run_report(target, db)
    except LlmError as exc:
        # Skor sudah ter-commit oleh compute_scores; kegagalan LLM tak boleh menghapusnya.
        logger.error("%s laporan GAGAL: %s", target, exc)
        return PipelineResult(**base, report_error=str(exc))

    headline = report.headline if report else None
    logger.info("%s laporan: %s", target, headline)

    # Supervisor memutuskan hari ini layak dikabarkan atau tidak. Hari yang membosankan
    # tetap tersimpan dan tetap terbaca di halaman — cuma tak mengganggu siapa pun.
    broadcast = ((report.context or {}).get("broadcast") if report else None) or {}
    if broadcast.get("worthy") is False:
        logger.info("%s tak di-broadcast: %s", target, broadcast.get("reason"))
        return PipelineResult(**base, headline=headline)

    # Telegram adalah lapisan pemberitahuan, bukan data. Kegagalannya dicatat, tak
    # pernah dilempar: laporan yang tak terkirim jauh lebih ringan daripada pipeline
    # yang tumbang dan meninggalkan hari tanpa skor.
    try:
        sent = broadcast_report(target, db)
    except Exception as exc:   # noqa: BLE001
        logger.error("%s broadcast Telegram gagal: %s", target, exc)
        sent = 0

    return PipelineResult(**base, headline=headline, broadcast_sent=sent)
