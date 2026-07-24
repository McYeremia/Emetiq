"""Istilah engine Big Money → bahasa sehari-hari.

Engine berbicara dengan kata yang lahir dari analisis teknikal: rezim, fase,
divergensi, AKUMULASI, CALM. Pembaca laporan Telegram tak punya pegangan untuk
itu. Modul ini menerjemahkannya, dengan istilah aslinya tetap dicantumkan dalam
kurung — pembaca baru paham, pembaca lama tetap mengenali kata yang sama dengan
di halaman web dan database.

Fungsi murni: tanpa database, tanpa jaringan. Dipisah dari telegram.py supaya
halaman web bisa memakai kamus yang sama nanti tanpa menyeret kode bot.

Istilah tak dikenal dikembalikan apa adanya. Fase baru di engine tak boleh
menjatuhkan laporan harian hanya karena kamus ini belum menyusul.
"""

_VOLATILITAS = {
    "CALM": "pasar tenang",
    "VOLATILE": "pasar bergejolak",
}

_TREN = {
    "BULL": "tren naik",
    "SIDEWAYS": "harga mendatar",
    "BEAR": "tren turun",
}

_FASE = {
    "AKUMULASI": "asing sedang mengumpulkan diam-diam",
    "MARKUP": "harga mulai naik mengikuti pembelian asing",
    "DISTRIBUSI": "asing mulai melepas ke pasar",
    "MARKDOWN": "harga turun, asing masih keluar",
    "NETRAL": "belum ada pola yang jelas",
}

_KEYAKINAN = {
    "STRONG": "kuat",
    "WATCH": "layak dipantau",
    "WEAK": "lemah",
}


def _terjemah(kamus: dict[str, str], nilai) -> str:
    """Terjemahan bila dikenal, kalau tidak nilai aslinya."""
    if nilai is None:
        return "tidak diketahui"
    return kamus.get(str(nilai).upper(), str(nilai))


def kondisi_pasar(volatilitas, tren) -> str:
    """Rezim pasar → satu kalimat, istilah aslinya menyusul dalam kurung."""
    kalimat = f"{_terjemah(_VOLATILITAS, volatilitas)}, {_terjemah(_TREN, tren)}"
    asli = " · ".join(str(x) for x in (volatilitas, tren) if x)
    return f"{kalimat} ({asli})" if asli else kalimat


def fase(nilai) -> str:
    terjemahan = _terjemah(_FASE, nilai)
    if nilai and terjemahan != str(nilai):
        return f"{terjemahan} ({nilai})"
    return terjemahan


def keyakinan(nilai) -> str:
    return _terjemah(_KEYAKINAN, nilai)


def peringatan(flags: dict | None) -> str | None:
    """Bendera risiko → peringatan berbahasa manusia, atau None bila bersih.

    Pump-dump menang atas divergensi: keduanya bisa menyala bersamaan, dan yang
    lebih berbahaya harus yang terbaca.
    """
    flags = flags or {}
    if flags.get("pump_dump_risk"):
        return ("🚨 Naik cepat dengan pola yang sering jadi jebakan — "
                "perlakukan sebagai peringatan, bukan peluang")
    if flags.get("divergence"):
        return "⚠️ Harga bergerak berlawanan dengan arah uang asing"
    return None
