"""Klien Gemini untuk laporan Big Money.

Terisolasi dari Groq dengan sengaja: Groq tetap milik AI Advisor EMETIQ dan tak
boleh tersentuh fitur ini. Tak ada satu pun impor lintas keduanya.

SDK di-impor malas (lazy) di dalam fungsi, bukan di puncak berkas, supaya modul
ini bisa di-impor dan diuji tanpa `google-generativeai` terpasang dan tanpa
GEMINI_API_KEY — kerangka laporan bisa dikerjakan sebelum key-nya diambil.
"""
import os

_MODEL_NAME = "gemini-2.0-flash"
_MODEL_CACHE = None   # klien di-cache: konfigurasi ulang tiap panggilan itu pemborosan


class LlmError(RuntimeError):
    """Gemini dipanggil tapi gagal menghasilkan teks yang bisa dipakai."""


class LlmNotConfigured(LlmError):
    """GEMINI_API_KEY belum diset — dibedakan supaya pemanggil bisa memilih diam."""


def is_configured() -> bool:
    """True bila Gemini siap dipanggil. Pemanggil memakai ini untuk melewati laporan dengan anggun."""
    return bool(os.getenv("GEMINI_API_KEY"))


def _get_model():
    """Bangun (sekali) model Gemini. Dipisah supaya tes bisa menggantinya tanpa SDK."""
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    try:
        import google.generativeai as genai
    except ImportError as exc:   # pragma: no cover — bergantung lingkungan
        raise LlmNotConfigured(
            "Paket google-generativeai belum terpasang. Tambahkan ke requirements.txt."
        ) from exc

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    _MODEL_CACHE = genai.GenerativeModel(_MODEL_NAME)
    return _MODEL_CACHE


def generate_text(prompt: str) -> str:
    """Kirim prompt ke Gemini, kembalikan teksnya.

    Melempar LlmNotConfigured bila key belum ada, LlmError bila Gemini gagal atau
    membalas kosong. Respons kosong (mis. tersaring filter keamanan) diperlakukan
    sebagai kegagalan — menyimpan laporan kosong lebih buruk daripada tak menyimpan.
    """
    if not is_configured():
        raise LlmNotConfigured(
            "GEMINI_API_KEY belum diset. Ambil key di https://aistudio.google.com/apikey "
            "lalu tambahkan ke .env backend."
        )

    try:
        response = _get_model().generate_content(prompt)
    except LlmError:
        raise
    except Exception as exc:   # noqa: BLE001 — SDK melempar aneka galat; pemanggil cuma perlu tahu Gemini gagal
        raise LlmError(f"Gemini gagal merespons: {exc}") from exc

    text = (getattr(response, "text", "") or "").strip()
    if not text:
        raise LlmError("Gemini mengembalikan teks kosong")

    return text
