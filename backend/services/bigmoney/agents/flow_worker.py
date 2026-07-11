"""Pekerja penafsir aliran dana: angka engine → maknanya.

Pekerja ini MENERJEMAHKAN, tidak menghitung. Angka yang masuk sudah benar dan sudah
teruji; menyuruh LLM menghitung ulang berarti menukar hasil yang deterministik dan
bisa diaudit dengan hasil yang berubah tiap dijalankan.

Tidak menyentuh database maupun jaringan.
"""
import logging

from services.bigmoney.llm import generate_text
from services.bigmoney.report_generator import render_prompt as render_numbers

logger = logging.getLogger("bigmoney.agents.flow")


def render_prompt(context: dict) -> str:
    """Angka yang sama yang dipakai laporan, dengan perintah berbeda: tafsirkan."""
    return "\n".join([
        render_numbers(context),
        "",
        "TUGAS KHUSUS KAMU (pekerja penafsir aliran dana):",
        "Jangan tulis laporan lengkap. Cukup jawab tiga hal, masing-masing satu kalimat:",
        "1. Apa yang sebenarnya dilakukan uang besar hari ini?",
        "2. Angka mana yang paling menentukan kesimpulan itu?",
        "3. Apa yang membantah atau melemahkan kesimpulan itu?",
        "Angka di atas sudah final — JANGAN hitung ulang, jangan mengarang angka baru.",
    ])


def interpret(context: dict) -> str | None:
    """Tafsiran aliran dana, atau None bila Gemini gagal."""
    try:
        return generate_text(render_prompt(context))
    except Exception as exc:   # noqa: BLE001 — pekerja boleh gagal sendiri
        logger.warning("Pekerja aliran dana gagal: %s", exc)
        return None
