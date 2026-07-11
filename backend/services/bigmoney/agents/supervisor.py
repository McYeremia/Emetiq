"""Supervisor: membagi tugas ke pekerja, menggabungkan hasilnya, dan mengabari user.

Supervisor tahu urutan dan database; pekerja tidak. Pekerja menerima data dan
mengembalikan teks — mereka tak saling memanggil dan tak pernah menyentuh DB.

Keputusan kelayakan kabar sengaja DETERMINISTIK, bukan diserahkan ke LLM: "apakah hari
ini cukup penting" bisa dijawab dengan aturan yang bisa diaudit, dan aturan yang bisa
diaudit selalu lebih baik daripada tebakan yang berbiaya token.

Tiap pekerja boleh gagal sendiri-sendiri. Bila penulisnya sendiri yang gagal, supervisor
jatuh kembali ke laporan satu-panggilan yang sudah ada. Tak satu pun jalur di sini bisa
menghapus skor yang sudah tersimpan.
"""
import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

import models
from services.bigmoney.agents import critic, flow_worker, news_worker
from services.bigmoney.agents.factcheck import check_claims
from services.bigmoney.agents.news_source import fetch_news
from services.bigmoney.llm import _MODEL_NAME, LlmError, generate_text
from services.bigmoney.report_generator import (
    build_context,
    generate_report,
    render_prompt as render_numbers,
    split_report,
)

logger = logging.getLogger("bigmoney.agents.supervisor")

_NEWS_TICKERS = 5

# Ambang "layak dikabari". Hari yang membosankan tetap disimpan, tapi tidak dikirim:
# notifikasi harian yang membosankan akan diabaikan, dan alarm yang diabaikan sama
# saja tak ada.
_EXTREME_FOREIGN_FLOW = 500_000_000_000   # Rp — net asing pasar sebesar ini layak dikabarkan


def _company_names(tickers: list[str], db: Session) -> dict[str, str | None]:
    rows = db.query(models.Stock.ticker, models.Stock.name).filter(models.Stock.ticker.in_(tickers)).all()
    names = {ticker: name for ticker, name in rows}
    return {ticker: names.get(ticker) for ticker in tickers}


def gather_news(context: dict, db: Session) -> dict[str, list[dict]]:
    """Berita untuk saham teratas. Saham tanpa berita tetap muncul dengan daftar kosong."""
    tickers = [pick["ticker"] for pick in context["top_accumulation"][:_NEWS_TICKERS]]
    if not tickers:
        return {}

    names = _company_names(tickers, db)
    return {ticker: fetch_news(ticker, names.get(ticker)) for ticker in tickers}


def render_writer_prompt(context: dict, news: str | None, flow: str | None,
                         issues: str | None = None) -> str:
    """Prompt penulis: angka + hasil kerja para pekerja.

    `issues` diisi pada percobaan kedua, setelah kritikus menolak draf pertama.
    """
    lines = [render_numbers(context)]

    if flow:
        lines += ["", "=== TAFSIRAN PEKERJA ALIRAN DANA ===", flow]
    if news:
        lines += ["", "=== KONTEKS BERITA (7 hari terakhir) ===", news,
                  "",
                  "Bila sebuah berita menjelaskan aliran dana, sebutkan kaitannya. "
                  "Bila tidak ada berita yang relevan, jangan mengarang sebab."]

    if issues:
        lines += [
            "",
            "=== PERBAIKI INI ===",
            "Draf sebelumnya ditolak pemeriksa fakta karena bertentangan dengan angka:",
            issues,
            "Tulis ulang laporan tanpa mengulangi kesalahan itu.",
        ]

    return "\n".join(lines)


def _newsworthy(target: date, context: dict, db: Session) -> tuple[bool, str]:
    """Layak dikirim ke Telegram? Aturan, bukan tebakan LLM."""
    reasons: list[str] = []

    strong = [p for p in context["top_accumulation"] if p["conviction"] == "STRONG"]
    if strong:
        reasons.append(f"{len(strong)} saham berkeyakinan STRONG")

    flow = context["regime"].get("total_foreign_net_value") or 0
    if abs(flow) >= _EXTREME_FOREIGN_FLOW:
        arah = "masuk" if flow > 0 else "keluar"
        reasons.append(f"aliran asing ekstrem: dana {arah} {abs(flow) / 1e12:.2f} triliun")

    previous = (
        db.query(models.BigMoneyMarketRegime)
          .filter(models.BigMoneyMarketRegime.date < target)
          .order_by(models.BigMoneyMarketRegime.date.desc())
          .first()
    )
    if previous and previous.weight_set != context["regime"]["weight_set"]:
        reasons.append(f"rezim berubah: {previous.weight_set} → {context['regime']['weight_set']}")

    if reasons:
        return True, "; ".join(reasons)
    return False, "hari tenang: tak ada STRONG, rezim tetap, aliran asing biasa"


def run_report(target: date, db: Session) -> models.BigMoneyDailyReport | None:
    """Jalankan tim agen untuk `target`, simpan laporannya.

    Mengembalikan None bila hari itu belum di-skor. Bila penulis gagal, jatuh kembali
    ke laporan satu-panggilan `generate_report`.
    """
    context = build_context(target, db)
    if context is None:
        return None

    news_articles = gather_news(context, db)
    news_summary = news_worker.summarize(news_articles)
    flow_reading = flow_worker.interpret(context)

    try:
        draft = generate_text(render_writer_prompt(context, news_summary, flow_reading))
    except LlmError as exc:
        # Penulis adalah satu-satunya pekerja yang tak tergantikan. Kalau ia jatuh,
        # pakai jalur laporan lama daripada tak melaporkan apa pun.
        logger.error("Penulis gagal (%s) — jatuh kembali ke laporan satu-panggilan", exc)
        return generate_report(target, db)

    # Dua lapis pemeriksaan, dan yang deterministik didahulukan dengan sengaja: klaim
    # yang bisa dihitung tak boleh bergantung pada model yang bisa diblokir atau kehabisan
    # kuota. Kritikus LLM menangani sisanya — kesalahan yang tak bisa dirumuskan.
    hard_issues = check_claims(draft, context)
    # Kritikus harus melihat berita juga: tanpa itu ia akan menuduh setiap fakta berita
    # sebagai karangan — dan justru membuang bagian laporan yang paling berharga.
    verdict = critic.review(draft, context, news=news_summary)

    all_issues = hard_issues + ([verdict.issues] if verdict.issues else [])
    if all_issues:
        joined = "\n".join(all_issues)
        try:
            draft = generate_text(
                render_writer_prompt(context, news_summary, flow_reading, issues=joined))
        except LlmError as exc:
            logger.warning("Revisi gagal (%s) — draf awal disimpan dengan catatan pemeriksa", exc)
        else:
            # Jejak audit harus mencerminkan draf yang BENAR-BENAR disimpan, bukan draf
            # pertama yang sudah dibuang. Revisi yang masih melanggar dicatat keras.
            hard_issues = check_claims(draft, context)
            if hard_issues:
                logger.error("Revisi MASIH melanggar fakta: %s", "; ".join(hard_issues))

    headline, narrative = split_report(draft)
    worthy, reason = _newsworthy(target, context, db)

    # Jejak audit: apa yang dilihat tiap pekerja dan apa kata kritikus. Tanpa ini,
    # laporan lama tak bisa diperiksa ulang saat isinya ternyata keliru.
    context["agents"] = {
        "news": {ticker: articles for ticker, articles in news_articles.items()},
        "news_summary": news_summary,
        "flow_reading": flow_reading,
        "critic": {
            "passed": verdict.passed,
            "skipped": verdict.skipped,
            "issues": verdict.issues,
        },
        "factcheck": {
            "passed": not hard_issues,
            "issues": hard_issues,
        },
    }
    context["broadcast"] = {"worthy": worthy, "reason": reason}

    report = (
        db.query(models.BigMoneyDailyReport)
          .filter(models.BigMoneyDailyReport.date == target)
          .one_or_none()
    )
    if report is None:
        report = models.BigMoneyDailyReport(date=target)
        db.add(report)

    report.headline = headline
    report.narrative = narrative
    report.context = context
    report.model = f"{_MODEL_NAME} (tim agen)"

    db.commit()
    db.refresh(report)

    logger.info("%s laporan agen tersimpan | layak kabar: %s (%s)", target, worthy, reason)
    return report
