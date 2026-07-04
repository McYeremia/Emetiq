"""Pembulatan angka untuk data yang disuntikkan ke prompt LLM.

LLM diminta mengutip angka apa adanya dari DATA. Bila DATA berisi angka berekor
panjang (mis. RSI 28.42351), jawaban ke user ikut berantakan. `round_numbers`
membulatkan semua float (termasuk yang bersarang di dict/list) ke 2 desimal di
titik injeksi, sehingga LLM hanya pernah melihat angka rapi. Int/str/None/bool
tidak disentuh; struktur asli tidak dimutasi (mengembalikan salinan baru).
"""
from typing import Any


def round_numbers(obj: Any, ndigits: int = 2) -> Any:
    """Kembalikan salinan `obj` dengan semua float dibulatkan ke `ndigits` desimal.

    Menelusuri dict & list secara rekursif. bool bukan angka di sini (walau
    subclass int) sehingga True/False tidak berubah.
    """
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: round_numbers(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_numbers(v, ndigits) for v in obj]
    return obj
