"""Pemeriksa fakta deterministik: klaim yang bisa dihitung, diperiksa dengan aturan.

Lahir dari kegagalan nyata. Pada 2026-07-10 penulis menuduh WBSA, INET, dan ASPR
"rentan pump-and-dump" padahal ketiganya berbendera False — dan kritikus LLM yang
seharusnya menangkapnya justru diblokir Gemini (finish_reason RECITATION).

Pelajarannya: pemeriksaan yang bisa dirumuskan JANGAN dititipkan ke model yang bisa
diblokir, kehabisan kuota, atau berubah pikiran. Berkas ini tak bisa diblokir, tak
berbiaya token, dan tak pernah bohong. Kritikus LLM tetap ada untuk kesalahan yang
tak bisa dirumuskan — tapi ia bukan lagi satu-satunya penjaga.

Tanpa LLM, tanpa I/O.
"""
import re

# Jarak (karakter) antara nama ticker dan kata tuduhan agar dianggap saling merujuk.
# Kalimat khas laporan berada jauh di bawah ini; pembahasan umum di paragraf lain tidak.
_PROXIMITY = 120

_PUMP_WORDS = r"pump|manipulasi harga|goreng"
_DIVERGENCE_WORDS = r"divergensi|divergence"

# Frasa yang menyatakan asing MEMBELI pasar secara keseluruhan. Sengaja sempit:
# "paling sedikit ditinggalkan" atau net buy per-saham di hari outflow adalah
# pembacaan yang BENAR dan tak boleh dihukum.
_MARKET_BUY = re.compile(
    r"asing\s+(?:mem)?borong\s+pasar"
    r"|asing\s+(?:masuk|membeli)\s+(?:ke\s+)?pasar"
    r"|pasar\s+mencatat(?:kan)?\s+net\s+buy\s+asing"
    r"|aliran\s+dana\s+asing\s+masuk\s+ke\s+pasar",
    re.IGNORECASE,
)


def _mentions_near(draft: str, ticker: str, words: str) -> bool:
    """Ticker dan kata tuduhan muncul berdekatan → laporan menuduh saham itu."""
    for match in re.finditer(rf"\b{re.escape(ticker)}\b", draft):
        window = draft[max(0, match.start() - _PROXIMITY): match.end() + _PROXIMITY]
        if re.search(words, window, re.IGNORECASE):
            return True
    return False


def check_claims(draft: str, context: dict) -> list[str]:
    """Klaim di `draft` yang bertentangan dengan angka. Daftar kosong = bersih.

    Hanya memeriksa yang bisa dipastikan salah. Ambigu dibiarkan lolos: pemeriksa yang
    menuduh serampangan akan memicu penulisan ulang tanpa henti dan melatih kita
    mengabaikannya.
    """
    issues: list[str] = []

    for pick in context.get("top_accumulation") or []:
        ticker = pick["ticker"]
        flags = pick.get("flags")

        # Flags hilang (skor lama) → kita tak tahu. Pemeriksa yang menuduh saat tak tahu
        # sama buruknya dengan model yang mengarang: diam adalah jawaban yang jujur.
        if flags is not None:
            if not flags.get("pump_dump_risk") and _mentions_near(draft, ticker, _PUMP_WORDS):
                issues.append(
                    f"{ticker} disebut berisiko pump-and-dump, padahal flags.pump_dump_risk = False. "
                    f"Menuduh emiten nyata melakukan manipulasi harga tanpa dasar data tidak boleh terjadi."
                )

            if not flags.get("divergence") and _mentions_near(draft, ticker, _DIVERGENCE_WORDS):
                issues.append(
                    f"{ticker} disebut mengalami divergensi, padahal flags.divergence = False."
                )

        if pick.get("conviction") != "STRONG" and _mentions_near(draft, ticker, r"STRONG"):
            issues.append(
                f"{ticker} disebut STRONG, padahal engine menilainya {pick.get('conviction')}."
            )

    flow = (context.get("regime") or {}).get("total_foreign_net_value") or 0
    if flow < 0 and _MARKET_BUY.search(draft):
        issues.append(
            f"Laporan menyebut asing membeli pasar, padahal net asing pasar negatif "
            f"({flow:,} rupiah). Di hari outflow, 'top akumulasi' berarti paling sedikit "
            f"ditinggalkan — bukan diborong."
        )

    return issues
