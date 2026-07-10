"""Pemetaan respons IDX GetStockSummary → baris BigMoneyStockDaily.

Fungsi murni: tanpa jaringan, tanpa database. Seluruh logika turunan ada di sini
sehingga bisa diuji dengan angka nyata tanpa I/O.

Satuan (terverifikasi dari IDX 2026-07-09): Volume dan ForeignBuy/ForeignSell
dalam LEMBAR, Value dalam RUPIAH. Bukti: BBCA Value/Volume = 6148,91 yang
berdempetan dengan Close 6200.
"""
from datetime import date


def _to_float(value) -> float | None:
    """Angka IDX datang sebagai float; None dan string kosong jadi None."""
    if value is None or value == "":
        return None
    return float(value)


def _to_int(value) -> int:
    """Kolom pencacah: None diperlakukan sebagai 0."""
    if value is None or value == "":
        return 0
    return int(float(value))


def to_row(raw: dict, target: date) -> dict | None:
    """Ubah satu baris mentah IDX jadi dict siap-ORM.

    Mengembalikan None bila baris tak layak simpan (StockCode kosong).

    Turunan berpembagi bernilai None ketika pembagi nol — bukan 0 — supaya
    fungsi agregat SQL mengabaikannya alih-alih menariknya turun.
    """
    ticker = str(raw.get("StockCode") or "").strip().upper()
    if not ticker:
        return None

    prev_close = _to_float(raw.get("Previous"))
    close = _to_float(raw.get("Close"))

    volume = _to_int(raw.get("Volume"))
    value = _to_int(raw.get("Value"))
    frequency = _to_int(raw.get("Frequency"))
    foreign_buy = _to_int(raw.get("ForeignBuy"))
    foreign_sell = _to_int(raw.get("ForeignSell"))

    foreign_net = foreign_buy - foreign_sell
    vwap = value / volume if volume else None

    # Estimasi: IDX tak memberi harga rata-rata sisi asing, jadi VWAP pasar
    # dipakai sebagai penggantinya. Wajib kena disclaimer di UI dan laporan.
    foreign_net_value = round(foreign_net * vwap) if vwap is not None else None

    avg_ticket = value / frequency if frequency else None

    # Pembagi 2: tiap transaksi punya sisi beli dan sisi jual, sedangkan Volume
    # menghitungnya sekali. Tanpa itu BBCA keluar 162% partisipasi asing.
    foreign_participation = (foreign_buy + foreign_sell) / (2 * volume) if volume else None

    if prev_close and close is not None:
        change_pct = (close - prev_close) / prev_close * 100
    else:
        change_pct = None

    return {
        "ticker": ticker,
        "date": target,
        "prev_close": prev_close,
        "open_price": _to_float(raw.get("OpenPrice")),
        "high": _to_float(raw.get("High")),
        "low": _to_float(raw.get("Low")),
        "close": close,
        "volume": volume,
        "value": value,
        "frequency": frequency,
        "listed_shares": _to_int(raw.get("ListedShares")),
        "foreign_buy": foreign_buy,
        "foreign_sell": foreign_sell,
        "foreign_net": foreign_net,
        "vwap": vwap,
        "foreign_net_value": foreign_net_value,
        "avg_ticket": avg_ticket,
        "foreign_participation": foreign_participation,
        "change_pct": change_pct,
    }
