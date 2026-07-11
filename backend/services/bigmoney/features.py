"""Jendela riwayat bigmoney_stock_daily → fitur per ticker.

Fungsi murni: tanpa database, tanpa jaringan. Seluruh aritmatika jendela hidup
di sini supaya bisa diuji dengan angka buatan tangan.

Baseline (volume rata-rata, tertinggi jendela) dihitung dari hari-hari SEBELUM
tanggal target, bukan termasuk target. Kalau target ikut masuk pembagi, lonjakan
volume akan mengencerkan baselinenya sendiri dan breakout jadi mustahil dideteksi.

Pembagi nol dan data hilang menghasilkan None, bukan 0 — nol adalah nilai sah di
data IDX (13,7% baris punya volume = 0) dan akan menyesatkan peringkat persentil.
"""
from datetime import date
from statistics import median

_PERSISTENCE_WINDOW = 5   # hari bursa untuk foreign_net_days
_FLAT_PRICE_BAND = 3.0    # % — di atas ini, faktor volume_price jadi nol


def _median_or_none(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    return median(clean) if clean else None


def _mean_or_none(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else None


def _ratio(numerator, denominator) -> float | None:
    """None bila salah satu sisi hilang atau pembaginya nol."""
    if numerator is None or not denominator:
        return None
    return numerator / denominator


def _feature_row(rows: list[dict], target: date) -> dict:
    """`rows` = seluruh riwayat satu ticker dalam jendela, urut menaik, ada baris target."""
    today = rows[-1]
    prior = rows[:-1]

    recent = rows[-_PERSISTENCE_WINDOW:]
    foreign_net_days = sum(1 for r in recent if (r["foreign_net"] or 0) > 0)
    foreign_net_days_sell = sum(1 for r in recent if (r["foreign_net"] or 0) < 0)

    # Beruntun mundur dari target; berhenti di hari pertama yang bukan net beli.
    days_confirmed = 0
    for row in reversed(rows):
        if (row["foreign_net"] or 0) > 0:
            days_confirmed += 1
        else:
            break

    volume_baseline = _mean_or_none([r["volume"] for r in prior])
    vol_spike = _ratio(today["volume"], volume_baseline)

    avg_ticket_median = _median_or_none([r["avg_ticket"] for r in prior])
    big_ticket_ratio = _ratio(today["avg_ticket"], avg_ticket_median)

    # VWAP tertimbang volume pada hari-hari asing net beli — estimasi harga masuk
    # asing. IDX tak memberi harga per sisi asing, jadi ini yang terdekat.
    buy_days = [r for r in rows if (r["foreign_net"] or 0) > 0]
    accum_volume = sum(r["volume"] or 0 for r in buy_days)
    accum_vwap = _ratio(sum(r["value"] or 0 for r in buy_days), accum_volume)

    close = today["close"]
    cost_basis_gap = _ratio(accum_vwap - close, accum_vwap) if accum_vwap and close is not None else None

    change_pct = today["change_pct"]
    if vol_spike is None or change_pct is None:
        volume_price = None
    else:
        volume_price = max(0.0, vol_spike * (1 - abs(change_pct) / _FLAT_PRICE_BAND))

    return {
        "ticker": today["ticker"],
        "date": target,
        # mentah — dipakai klasifikasi fase dan filter, bukan cuma peringkat
        "close": close,
        "volume": today["volume"],
        "value": today["value"],
        "change_pct": change_pct,
        "foreign_net": today["foreign_net"],
        "foreign_net_value": today["foreign_net_value"],
        "avg_ticket": today["avg_ticket"],
        # turunan jendela
        "foreign_net_days": foreign_net_days,
        "foreign_net_days_sell": foreign_net_days_sell,
        "days_confirmed": days_confirmed,
        "volume_baseline": volume_baseline,
        "vol_spike": vol_spike,
        "avg_ticket_median": avg_ticket_median,
        "big_ticket_ratio": big_ticket_ratio,
        "accum_vwap": accum_vwap,
        "cost_basis_gap": cost_basis_gap,
        "volume_price": volume_price,
        "value_median": _median_or_none([r["value"] for r in rows]),
        "high_prior": max([r["close"] for r in prior if r["close"] is not None], default=None),
    }


def build_features(history: list[dict], target: date) -> dict[str, dict]:
    """Kelompokkan riwayat per ticker, hitung fitur untuk yang punya baris di `target`.

    `history` adalah baris bigmoney_stock_daily sepanjang jendela (urutan bebas).
    Ticker tanpa baris di `target` dilewati: saham yang berhenti diperdagangkan
    tak boleh muncul di skor hari ini.
    """
    by_ticker: dict[str, list[dict]] = {}
    for row in history:
        by_ticker.setdefault(row["ticker"], []).append(row)

    features: dict[str, dict] = {}
    for ticker, rows in by_ticker.items():
        rows.sort(key=lambda r: r["date"])
        if rows[-1]["date"] != target:
            continue
        features[ticker] = _feature_row(rows, target)

    return features
