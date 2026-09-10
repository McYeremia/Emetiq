"""Skor kecocokan kandidat screening — penentu URUTAN hasil.

Fungsi murni: tidak menyentuh DB, tidak memanggil LLM, mudah diuji.

Kenapa modul ini ada
--------------------
Sebelumnya kriteria user hanya dipakai sebagai gerbang lolos/tidak, lalu hasilnya
diurutkan **murni per kapitalisasi pasar** dan dipotong. Akibatnya 15 kursi yang
dikirim ke LLM selalu ditempati perusahaan terbesar yang lolos filter — berapa pun
jauh kandidat lain melampaui kriteria yang diminta. Screening "PE di bawah 15"
mengembalikan bank raksasa ber-PE 12 di urutan atas, sementara emiten ber-PE 4
mendarat di buncit dan sering tak pernah sampai ke LLM.

Modul ini menjadikan **seberapa jauh sebuah saham MELAMPAUI batas yang diminta**
sebagai penentu peringkat. Kapitalisasi tidak dibuang — ia turun pangkat dari
satu-satunya penentu menjadi satu bahan berbobot kecil, karena saham yang terlalu
kecil memang berisiko sulit dijual.

Hubungannya dengan AI Porto
---------------------------
Skor ini MILIK ADVISOR dan sengaja TIDAK memakai ulang `services/ai_porto/scoring.py`.
Alasannya teknis, bukan sekadar kehati-hatian: skor di sini harus mengikuti kriteria
yang **diketik user** dan berubah tiap permintaan, sementara skor AI Porto punya
selera tetap (momentum ber-sinyal) yang tak bergantung pada input siapa pun.
AI Porto tidak disentuh sama sekali oleh modul ini.

Semua bobot terpusat di `config.SKOR_BOBOT` supaya menyetelnya tak menyentuh logika.
"""
import math
from typing import Any, Dict, Optional

from services.advisor import config


def _jepit(x: float, bawah: float = 0.0, atas: float = 1.0) -> float:
    return max(bawah, min(atas, x))


def margin_kriteria(c: Dict[str, Any], filters: Dict[str, Any]) -> Optional[float]:
    """Rata-rata 0-1 "seberapa jauh melampaui batas" untuk kriteria bernilai angka.

    Mengembalikan None bila user tidak menyebut satu pun kriteria bermargin — itu
    sinyal bagi `skor_kecocokan` untuk membagikan bobotnya ke komponen kualitas.

    Hanya `pe_max`, `pbv_max`, dan `div_min` yang dinilai di sini. `price_max` dan
    `price_min` sengaja DIKECUALIKAN: keduanya batasan anggaran, bukan pernyataan
    kualitas — saham yang harganya jauh di bawah plafon tidak lantas lebih baik.
    `rsi`, `trend`, dan `sector` juga dikecualikan karena sudah disaring keras di
    `data_provider.screen`; menilainya lagi di sini berarti menghitung ganda.
    """
    nilai = []

    pe_max = filters.get("pe_max")
    pe = c.get("pe")
    if pe_max is not None and pe_max > 0 and pe is not None:
        nilai.append(_jepit((pe_max - pe) / pe_max))

    pbv_max = filters.get("pbv_max")
    pbv = c.get("pbv")
    if pbv_max is not None and pbv_max > 0 and pbv is not None:
        nilai.append(_jepit((pbv_max - pbv) / pbv_max))

    div_min = filters.get("div_min")
    dy = c.get("dividend_yield")
    if div_min is not None and dy is not None:
        # Pembagi (div_min + 3) bukan div_min: kalau user minta "dividen di atas 0",
        # pembagi div_min saja akan nol. Angka 3 membuat kurvanya landai — dividen
        # 9% terhadap permintaan 3% mencapai nilai penuh, 3,1% nyaris nol.
        nilai.append(_jepit((dy - div_min) / (div_min + 3.0)))

    if not nilai:
        return None
    return sum(nilai) / len(nilai)


def skor_tren(trend: Optional[str]) -> float:
    """Tren naik bernilai penuh, turun bernilai nol, tak diketahui di tengah."""
    if trend == "up":
        return 1.0
    if trend == "down":
        return 0.0
    return 0.5


def skor_rsi(rsi: Optional[float]) -> float:
    """RSI sehat (45-60) bernilai penuh; jenuh beli dihukum paling berat.

    Jenuh jual TIDAK diberi nilai tertinggi: ia memang peluang pantul, tapi sama
    seringnya adalah saham yang masih jatuh. Nilainya di tengah, bukan di puncak.
    """
    if rsi is None:
        return 0.5
    if rsi > 70:
        return 0.10
    if rsi > 60:
        return 0.50
    if rsi >= 45:
        return 1.00
    if rsi >= 30:
        return 0.75
    return 0.60


def skor_likuiditas(market_cap: Optional[float]) -> float:
    """Kapitalisasi pada skala logaritma antara lantai dan atap di config.

    Skala log, bukan linier: selisih 1 triliun vs 10 triliun jauh lebih berarti
    daripada 900 triliun vs 909 triliun. Tanpa log, satu-dua raksasa akan menekan
    seluruh kandidat lain ke nol dan kita kembali ke masalah semula.
    """
    if not market_cap or market_cap <= 0:
        return 0.0
    bawah = math.log10(config.SKOR_LIKUIDITAS_LANTAI)
    atas = math.log10(config.SKOR_LIKUIDITAS_ATAP)
    if atas <= bawah:
        return 0.0
    return _jepit((math.log10(market_cap) - bawah) / (atas - bawah))


def skor_kecocokan(c: Dict[str, Any], filters: Dict[str, Any]) -> float:
    """Skor 0-100 untuk satu kandidat terhadap kriteria yang diminta user.

    Makin tinggi makin pantas berada di peringkat atas. Dipakai HANYA untuk
    mengurutkan — bukan untuk menyaring; penyaringan keras tetap di `screen()`.
    """
    bobot = dict(config.SKOR_BOBOT)
    margin = margin_kriteria(c, filters)

    if margin is None:
        # User tak menyebut kriteria bernilai angka (mis. "cari saham bagus", atau
        # hanya menyebut sektor). Bobot kriteria dibagikan rata ke komponen kualitas
        # supaya skalanya tetap 0-100 dan hasilnya tetap masuk akal.
        sisa = bobot["tren"] + bobot["rsi"] + bobot["likuiditas"]
        faktor = (sisa + bobot["kriteria"]) / sisa if sisa > 0 else 1.0
        bobot = {
            "kriteria": 0.0,
            "tren": bobot["tren"] * faktor,
            "rsi": bobot["rsi"] * faktor,
            "likuiditas": bobot["likuiditas"] * faktor,
        }
        margin = 0.0

    total = (
        margin * bobot["kriteria"]
        + skor_tren(c.get("trend")) * bobot["tren"]
        + skor_rsi(c.get("rsi")) * bobot["rsi"]
        + skor_likuiditas(c.get("market_cap")) * bobot["likuiditas"]
    )
    return round(_jepit(total, 0.0, 100.0), 1)
