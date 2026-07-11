"""Skor + rezim → laporan harian berbahasa manusia lewat Gemini.

Tiga tahap yang sengaja dipisah: `build_context` mengambil angka dari database,
`render_prompt` mengubah angka jadi kalimat perintah, `generate_report` memanggil
model dan menyimpannya. Pemisahan ini memungkinkan prompt diinspeksi (dan diuji)
tanpa memanggil Gemini sama sekali — berguna selama GEMINI_API_KEY belum ada.

Konteks yang disodorkan ke model ikut disimpan. Tanpa itu, laporan lama tak bisa
diaudit: kita takkan bisa membedakan model yang mengarang dari data yang memang
aneh.
"""
from datetime import date

from sqlalchemy.orm import Session

import models
from services.bigmoney.llm import _MODEL_NAME, generate_text

_TOP_SECTORS = 3


def _regime_dict(regime: models.BigMoneyMarketRegime) -> dict:
    return {
        "volatility_regime": regime.volatility_regime,
        "trend_regime": regime.trend_regime,
        "weight_set": regime.weight_set,
        "market_return_pct": regime.market_return_pct,
        "breadth": regime.breadth,
        "total_foreign_net_value": regime.total_foreign_net_value,
    }


def build_context(target: date, db: Session) -> dict | None:
    """Kumpulkan angka yang jadi bahan laporan. Mengembalikan None bila hari itu belum di-skor."""
    regime = (
        db.query(models.BigMoneyMarketRegime)
          .filter(models.BigMoneyMarketRegime.date == target)
          .one_or_none()
    )
    if regime is None:
        return None

    rows = (
        db.query(models.BigMoneyTopAccumulation)
          .filter(models.BigMoneyTopAccumulation.date == target)
          .order_by(models.BigMoneyTopAccumulation.rank)
          .all()
    )

    top: list[dict] = []
    for row in rows:
        score = (
            db.query(models.BigMoneyScore)
              .filter_by(date=target, ticker=row.ticker)
              .one_or_none()
        )
        daily = (
            db.query(models.BigMoneyStockDaily)
              .filter_by(date=target, ticker=row.ticker)
              .one_or_none()
        )
        top.append({
            "rank": row.rank,
            "ticker": row.ticker,
            "composite": row.composite,
            "conviction": row.conviction,
            "phase": row.phase,
            "days_confirmed": score.days_confirmed if score else None,
            "flags": score.flags if score else None,
            "foreign_net_value": daily.foreign_net_value if daily else None,
            "change_pct": daily.change_pct if daily else None,
            "close": daily.close if daily else None,
        })

    rotation = regime.sector_rotation or {}
    ranked = sorted(rotation.items(), key=lambda kv: kv[1], reverse=True)
    inflow = [{"sector": s, "foreign_net_value": v} for s, v in ranked[:_TOP_SECTORS] if v > 0]
    outflow = [{"sector": s, "foreign_net_value": v} for s, v in reversed(ranked[-_TOP_SECTORS:]) if v < 0]

    previous = (
        db.query(models.BigMoneyMarketRegime)
          .filter(models.BigMoneyMarketRegime.date < target)
          .order_by(models.BigMoneyMarketRegime.date.desc())
          .first()
    )

    return {
        "date": target.isoformat(),
        "regime": _regime_dict(regime),
        "previous": _regime_dict(previous) if previous else None,
        "top_accumulation": top,
        "sector_inflow": inflow,
        "sector_outflow": outflow,
    }


def _rupiah(value) -> str:
    if value is None:
        return "n/a"
    miliar = value / 1_000_000_000
    return f"Rp {miliar:,.1f} miliar"


def render_prompt(context: dict) -> str:
    """Susun prompt Gemini dari konteks. Fungsi murni — bisa diinspeksi tanpa API key.

    Prompt memikul tiga kewajiban yang tak boleh hilang: laporan bukan nasihat
    investasi, cost basis cuma estimasi, dan skor bersifat relatif terhadap hari
    itu (di hari outflow, "top akumulasi" berarti paling sedikit dijual — bukan
    diborong).
    """
    regime = context["regime"]
    previous = context["previous"]

    lines = [
        "Kamu analis pasar saham Indonesia. Tulis laporan harian aliran dana besar (big money) di IDX.",
        "",
        f"TANGGAL: {context['date']}",
        "",
        "REZIM PASAR:",
        f"- Volatilitas: {regime['volatility_regime']} | Tren: {regime['trend_regime']}",
        f"- Return pasar (tertimbang nilai transaksi): {regime['market_return_pct']:.2f}%"
        if regime["market_return_pct"] is not None else "- Return pasar: n/a",
        f"- Breadth (rasio saham naik): {regime['breadth']:.2f}"
        if regime["breadth"] is not None else "- Breadth: n/a",
        f"- Net asing seluruh pasar: {_rupiah(regime['total_foreign_net_value'])}",
    ]

    if previous:
        lines.append(f"- Net asing hari bursa sebelumnya: {_rupiah(previous['total_foreign_net_value'])}")

    if context["sector_inflow"]:
        lines.append("")
        lines.append("SEKTOR PENERIMA DANA ASING:")
        lines += [f"- {s['sector']}: {_rupiah(s['foreign_net_value'])}" for s in context["sector_inflow"]]

    if context["sector_outflow"]:
        lines.append("")
        lines.append("SEKTOR DITINGGALKAN ASING:")
        lines += [f"- {s['sector']}: {_rupiah(s['foreign_net_value'])}" for s in context["sector_outflow"]]

    lines.append("")
    lines.append("TOP AKUMULASI (peringkat hasil engine, bukan rekomendasi):")
    for row in context["top_accumulation"]:
        flags = row["flags"] or {}
        catatan = []
        if flags.get("divergence"):
            catatan.append("divergensi harga vs aliran asing")
        if flags.get("pump_dump_risk"):
            catatan.append("RISIKO PUMP-DUMP")
        suffix = f" [{'; '.join(catatan)}]" if catatan else ""
        lines.append(
            f"{row['rank']}. {row['ticker']} — skor {row['composite']:.1f} ({row['conviction']}, "
            f"fase {row['phase']}) | net asing {_rupiah(row['foreign_net_value'])} | "
            f"{row['days_confirmed']} hari inflow beruntun{suffix}"
        )

    lines += [
        "",
        "ATURAN PENULISAN:",
        "1. Jawab tiga hal: ke mana arah big money hari ini, berdasarkan bukti apa, dan saham mana yang sedang top akumulasi.",
        "2. Baris pertama adalah judul (maksimal 12 kata, tanpa markdown). Baris berikutnya isi laporan, 3-4 paragraf.",
        "3. Skor bersifat RELATIF terhadap saham lain hari itu. Bila net asing seluruh pasar negatif, "
        "'top akumulasi' berarti paling sedikit ditinggalkan, BUKAN diborong besar-besaran. Katakan apa adanya.",
        "4. Nilai net asing adalah ESTIMASI (net lembar dikali VWAP pasar) — IDX tak menyediakan harga per sisi asing. "
        "Jangan menyebutnya sebagai harga beli bandar yang presisi.",
        "5. Sebut saham berbendera risiko pump-dump sebagai peringatan, bukan peluang.",
        "6. Ini alat bantu analisis, BUKAN NASIHAT INVESTASI. Jangan menyuruh membeli atau menjual apa pun.",
        "7. Bahasa Indonesia, lugas, tanpa jargon berlebihan. Tanpa emoji.",
    ]

    return "\n".join(lines)


def split_report(text: str) -> tuple[str, str]:
    """Pisahkan keluaran model jadi (judul, isi). Baris pertama adalah judulnya.

    Model kadang tetap menempelkan markdown heading meski dilarang; itu dibersihkan
    di sini daripada memaksa prompt makin panjang.
    """
    stripped = text.strip()
    lines = stripped.split("\n", 1)

    headline = lines[0].lstrip("#").strip().strip("*").strip()
    narrative = lines[1].strip() if len(lines) > 1 and lines[1].strip() else stripped

    return headline, narrative


def generate_report(target: date, db: Session) -> models.BigMoneyDailyReport | None:
    """Hasilkan dan simpan laporan Gemini untuk `target`. Idempoten pada tanggal.

    Mengembalikan None bila hari itu belum di-skor — Gemini tak dipanggil sama
    sekali, supaya kuota tak terbakar untuk hari tanpa data.

    Melempar LlmNotConfigured bila GEMINI_API_KEY belum ada, dan LlmError bila
    Gemini gagal. Dalam kedua kasus tak ada baris yang tersimpan: laporan separuh
    lebih buruk daripada tak ada laporan.
    """
    context = build_context(target, db)
    if context is None:
        return None

    headline, narrative = split_report(generate_text(render_prompt(context)))

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
    report.model = _MODEL_NAME

    db.commit()
    db.refresh(report)
    return report
