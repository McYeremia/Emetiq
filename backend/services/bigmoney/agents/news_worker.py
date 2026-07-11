"""Pekerja berita: judul mentah → konteks yang menjelaskan aliran dana.

Ini satu-satunya pekerja yang menambah INFORMASI BARU ke sistem. Engine tahu asing
masuk CUAN tiga hari beruntun; ia takkan pernah tahu bahwa pendirinya menjual 1,7
miliar lembar. Jawaban itu ada di teks, dan membaca teks tak bisa dirumuskan.

Tidak menyentuh database maupun jaringan: menerima artikel, mengembalikan teks.
"""
import logging

from services.bigmoney.llm import generate_text

logger = logging.getLogger("bigmoney.agents.news")

_MAX_TICKERS = 5


def render_prompt(articles_by_ticker: dict[str, list[dict]]) -> str:
    """Prompt murni — bisa diperiksa tanpa memanggil Gemini."""
    lines = [
        "Kamu analis berita pasar saham Indonesia.",
        "",
        "Di bawah ini judul berita 7 hari terakhir untuk saham yang sedang menerima aliran "
        "dana asing besar. Tugasmu: jelaskan apa yang terjadi pada tiap saham, dan tandai "
        "berita mana yang MENJELASKAN aliran dana tersebut.",
        "",
    ]

    for ticker, articles in list(articles_by_ticker.items())[:_MAX_TICKERS]:
        lines.append(f"{ticker}:")
        if not articles:
            lines.append("- (tidak ada berita)")
        for article in articles:
            lines.append(f"- {article['title']} ({article.get('source') or 'sumber tak dikenal'})")
        lines.append("")

    lines += [
        "ATURAN:",
        "1. Maksimal 2 kalimat per saham. Saham tanpa berita relevan: lewati, jangan dikarang.",
        "2. Bila sebuah berita masuk akal menjelaskan aliran dana (akuisisi, aksi korporasi, "
        "masuk indeks, penjualan pemegang saham besar), katakan hubungannya secara eksplisit.",
        "3. Bila beritanya tak berhubungan dengan aliran dana, katakan begitu. Jangan memaksakan kaitan.",
        "4. JANGAN menyimpulkan harga akan naik atau turun. Kamu melaporkan, bukan meramal.",
        "5. Bahasa Indonesia, lugas, tanpa emoji.",
    ]

    return "\n".join(lines)


def summarize(articles_by_ticker: dict[str, list[dict]]) -> str | None:
    """Ringkasan berita, atau None bila tak ada bahan / Gemini gagal.

    Kegagalan di sini tidak fatal: laporan tanpa konteks berita masih jauh lebih
    berguna daripada tak ada laporan.
    """
    if not any(articles_by_ticker.values()):
        return None

    try:
        return generate_text(render_prompt(articles_by_ticker))
    except Exception as exc:   # noqa: BLE001 — pekerja boleh gagal sendiri
        logger.warning("Pekerja berita gagal: %s", exc)
        return None
