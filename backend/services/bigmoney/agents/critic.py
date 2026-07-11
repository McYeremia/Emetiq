"""Kritikus: mencocokkan draf laporan dengan angka mentah.

Menutup lubang paling berbahaya di pipeline sebelumnya: laporan ditulis sekali jalan
lalu langsung disimpan, dan tak ada yang menangkap saat model menulis "asing memborong"
di hari net asing minus Rp285 miliar. Laporan yang salah tapi terdengar meyakinkan lebih
buruk daripada tak ada laporan — orang bertindak atas dasar itu.

Kritikus hanya boleh menuduh berdasarkan angka yang tersedia. Ia bukan sensor gaya
bahasa dan bukan penilai kualitas prosa.
"""
import logging
from dataclasses import dataclass

from services.bigmoney.llm import generate_text
from services.bigmoney.report_generator import render_prompt as render_numbers

logger = logging.getLogger("bigmoney.agents.critic")

_PASS = "LOLOS"


@dataclass(frozen=True)
class Verdict:
    passed: bool
    issues: str | None = None
    skipped: bool = False   # kritikus tak bisa dijalankan; draf disimpan apa adanya


def render_prompt(draft: str, context: dict) -> str:
    return "\n".join([
        "Kamu pemeriksa fakta. Di bawah ada ANGKA RESMI, lalu DRAF LAPORAN yang ditulis "
        "model lain. Tugasmu memeriksa apakah draf itu bertentangan dengan angka.",
        "",
        "=== ANGKA RESMI ===",
        render_numbers(context),
        "",
        "=== DRAF LAPORAN ===",
        draft,
        "",
        "=== TUGASMU ===",
        f"Bila draf konsisten dengan angka, balas satu kata: {_PASS}",
        "Bila ada klaim yang bertentangan dengan angka, atau angka yang dikarang dan tidak "
        "ada di daftar resmi, tulis daftar masalahnya (satu baris per masalah).",
        "",
        "Yang WAJIB kamu tangkap:",
        "- Menyebut asing membeli padahal net asing pasar negatif (atau sebaliknya).",
        "- Angka yang tidak ada di ANGKA RESMI.",
        "- Menyebut skor sebagai kepastian, padahal skor bersifat relatif terhadap hari itu.",
        "- Rekomendasi membeli atau menjual. Laporan ini bukan nasihat investasi.",
        "",
        "JANGAN mengkritik gaya bahasa, panjang kalimat, atau pilihan kata. "
        "Hanya fakta yang bertentangan dengan angka.",
    ])


def review(draft: str, context: dict) -> Verdict:
    """Periksa draf. Kritikus yang gagal TIDAK memblokir laporan — ia hanya berhenti menjaga.

    Menjatuhkan laporan karena pemeriksanya mati akan membuat kegagalan kecil jadi
    kehilangan besar; yang benar adalah menyimpan draf sambil menandai bahwa ia belum diperiksa.
    """
    try:
        response = generate_text(render_prompt(draft, context))
    except Exception as exc:   # noqa: BLE001
        logger.warning("Kritikus gagal, draf disimpan tanpa pemeriksaan: %s", exc)
        return Verdict(passed=True, skipped=True)

    text = (response or "").strip()
    if text.upper().startswith(_PASS):
        return Verdict(passed=True)

    logger.warning("Kritikus menemukan masalah: %s", text[:200])
    return Verdict(passed=False, issues=text)
