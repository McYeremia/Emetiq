"""Fitur seluruh universe satu hari → subskor, composite, fase, flags, conviction.

Fungsi murni: tanpa database, tanpa jaringan.

Subskor adalah peringkat persentil di antara universe HARI ITU, bukan ambang
absolut. Dengan 77 hari data, ambang tebakan tak punya dasar empiris dan basi
begitu skala pasar bergeser; persentil juga kebal terhadap ekor panjang aliran
dana IDX, di mana BBCA sendirian bisa mendominasi mean dan stdev.

Konsekuensinya, skor bersifat relatif: sesuatu selalu meraih peringkat ~100
bahkan di hari terburuk. Karena itu STRONG tidak pernah bergantung pada skor
semata — ia menuntut fase yang benar, tiga hari inflow beruntun, dan bebas dari
kecurigaan gorengan.
"""

WEIGHTS = {
    "CALM": {
        "relative_foreign_flow": 0.35,
        "foreign_persistence": 0.25,
        "big_ticket": 0.15,
        "cost_basis": 0.20,
        "volume_price": 0.05,
    },
    "VOLATILE": {
        "relative_foreign_flow": 0.25,
        "foreign_persistence": 0.25,
        "big_ticket": 0.15,
        "cost_basis": 0.30,   # saat volatil, harga masuk lebih menentukan daripada arah aliran
        "volume_price": 0.05,
    },
}

# Metrik mentah yang diperingkat untuk tiap sinyal.
_SIGNAL_METRIC = {
    "relative_foreign_flow": "foreign_net_value",
    "foreign_persistence": "foreign_net_days",
    "big_ticket": "big_ticket_ratio",
    "cost_basis": "cost_basis_gap",
    "volume_price": "volume_price",
}

_MIN_MEDIAN_VALUE = 1_000_000_000    # Rp — ambang likuiditas universe

_MIN_DAYS_CONFIRMED = 3              # hari inflow beruntun sebelum boleh STRONG
_STRONG_SCORE = 75.0
_WATCH_SCORE = 55.0

_ACCUM_PRICE_TOLERANCE = 1.03        # close boleh 3% di atas VWAP akumulasi
_FLAT_PRICE_LIMIT = 1.5              # % — batas "harga sideways"
_VOL_SPIKE_LIMIT = 1.5

_PUMP_VOL_SPIKE = 5.0
_PUMP_CHANGE_PCT = 10.0
_PUMP_MAX_MEDIAN_VALUE = 5_000_000_000

_DIVERGENCE_MIN_VALUE = 1_000_000_000   # Rp — di bawah ini, arah aliran cuma kebisingan
_DIVERGENCE_PRICE_MOVE = 3.0            # %
_DIVERGENCE_PENALTY = 0.85

_ACCUMULATION_PHASES = ("AKUMULASI", "MARKUP")
_SELLING_PHASES = ("DISTRIBUSI", "MARKDOWN")


def percentile_ranks(metrics: dict[str, float | None]) -> dict[str, float]:
    """Peringkat persentil 0-100 per ticker, ikatan berbagi peringkat yang sama.

    Nilai None mendapat 0.0: metrik yang tak terdefinisi (mis. cost basis saham
    yang asing tak pernah beli) adalah kabar buruk, bukan kabar netral.

    Universe satu saham menghasilkan 50.0 — netral, bukan pembagian nol.
    """
    known = {t: v for t, v in metrics.items() if v is not None}
    values = list(known.values())
    unknown_count = len(metrics) - len(known)
    n = len(metrics)

    ranks: dict[str, float] = {}
    for ticker in metrics:
        if ticker not in known:
            ranks[ticker] = 0.0
            continue
        value = known[ticker]
        # None dihitung sebagai di bawah nilai mana pun: peringkat diukur terhadap
        # universe penuh, bukan cuma terhadap sesama yang terdefinisi.
        below = unknown_count + sum(1 for v in values if v < value)
        equal = sum(1 for v in values if v == value)
        # Titik tengah kelompok ikatan: adil bagi nilai yang identik.
        ranks[ticker] = (below + equal / 2) / n * 100
    return ranks


def select_universe(features: dict[str, dict]) -> dict[str, dict]:
    """Saham yang cukup likuid untuk di-skor.

    Menolak "top N market cap" dari spec lama: saham kecil justru paling sering
    jadi sasaran akumulasi. Yang berbahaya bukan saham kecil, melainkan saham
    yang tak bisa dijual — dan itu yang disaring di sini.
    """
    return {
        ticker: feat
        for ticker, feat in features.items()
        if (feat["value_median"] or 0) >= _MIN_MEDIAN_VALUE and (feat["volume"] or 0) > 0
    }


def classify_phase(feat: dict) -> str:
    """Fase dari metrik MENTAH, bukan dari subskor.

    Persentil tak punya makna absolut: peringkat 90 tak berarti asing benar-benar
    membeli, cuma berarti saham lain lebih parah. Fase harus tahu bedanya.

    Aturan dievaluasi berurutan. DISTRIBUSI sengaja diperiksa sebelum AKUMULASI:
    bila keduanya cocok, sinyal jual yang menang.
    """
    foreign_net = feat["foreign_net"] or 0
    change_pct = feat["change_pct"]
    vol_spike = feat["vol_spike"] or 0.0     # saham baru IPO: tanpa baseline, anggap tak ada lonjakan
    close = feat["close"]
    accum_vwap = feat["accum_vwap"]
    high_prior = feat["high_prior"]

    if change_pct is None or close is None:
        return "NETRAL"

    breakout = high_prior is not None and close > high_prior
    if foreign_net > 0 and vol_spike > _VOL_SPIKE_LIMIT and change_pct > 0 and breakout:
        return "MARKUP"

    if (feat["foreign_net_days_sell"] >= _MIN_DAYS_CONFIRMED
            and vol_spike > _VOL_SPIKE_LIMIT and change_pct <= 0):
        return "DISTRIBUSI"

    if foreign_net < 0 and change_pct < 0 and vol_spike > 1.0:
        return "MARKDOWN"

    if (feat["foreign_net_days"] >= _MIN_DAYS_CONFIRMED
            and abs(change_pct) < _FLAT_PRICE_LIMIT
            and accum_vwap is not None
            and close <= accum_vwap * _ACCUM_PRICE_TOLERANCE):
        return "AKUMULASI"

    return "NETRAL"


def run_filters(feat: dict) -> dict:
    """Dua jebakan yang harus ditandai sebelum skor dipercaya.

    `pump_dump_risk` memblokir STRONG. `divergence` cuma memotong skor: asing dan
    harga bergerak berlawanan berarti satu sisi sedang dilepas ke pihak lain —
    mencurigakan, tapi belum tentu salah.

    Flag `illiquid` dari spec lama sengaja tak ada: likuiditas sudah disaring di
    select_universe, jadi flag itu akan selalu bernilai false.
    """
    vol_spike = feat["vol_spike"] or 0.0
    change_pct = feat["change_pct"] or 0.0
    flow = feat["foreign_net_value"] or 0

    pump_dump_risk = (
        vol_spike > _PUMP_VOL_SPIKE
        and change_pct > _PUMP_CHANGE_PCT
        and (feat["value_median"] or 0) < _PUMP_MAX_MEDIAN_VALUE
    )

    divergence = abs(flow) >= _DIVERGENCE_MIN_VALUE and (
        (flow > 0 and change_pct < -_DIVERGENCE_PRICE_MOVE)
        or (flow < 0 and change_pct > _DIVERGENCE_PRICE_MOVE)
    )

    return {"pump_dump_risk": pump_dump_risk, "divergence": divergence}


def _conviction(composite: float, phase: str, days_confirmed: int, flags: dict) -> str:
    if phase in _SELLING_PHASES:
        return "WEAK"
    if (composite >= _STRONG_SCORE
            and phase in _ACCUMULATION_PHASES
            and days_confirmed >= _MIN_DAYS_CONFIRMED
            and not flags["pump_dump_risk"]):
        return "STRONG"
    if composite >= _WATCH_SCORE:
        return "WATCH"
    return "WEAK"


def score_universe(features: dict[str, dict], weight_set: str) -> list[dict]:
    """Skor seluruh universe satu hari, urut menurun berdasarkan composite.

    `features` sudah harus disaring lewat select_universe: peringkat persentil
    hanya bermakna bila penyebutnya adalah universe yang benar.
    """
    if not features:
        return []

    weights = WEIGHTS[weight_set]
    subscores = {
        signal: percentile_ranks({t: f[metric] for t, f in features.items()})
        for signal, metric in _SIGNAL_METRIC.items()
    }

    scored: list[dict] = []
    for ticker, feat in features.items():
        composite = sum(weights[signal] * subscores[signal][ticker] for signal in weights)

        flags = run_filters(feat)
        if flags["divergence"]:
            composite *= _DIVERGENCE_PENALTY

        phase = classify_phase(feat)
        days_confirmed = feat["days_confirmed"]

        scored.append({
            "ticker": ticker,
            "date": feat["date"],
            "composite": round(composite, 2),
            "conviction": _conviction(composite, phase, days_confirmed, flags),
            "phase": phase,
            "weight_set": weight_set,
            "s_relative_foreign_flow": round(subscores["relative_foreign_flow"][ticker], 2),
            "s_foreign_persistence": round(subscores["foreign_persistence"][ticker], 2),
            "s_big_ticket": round(subscores["big_ticket"][ticker], 2),
            "s_cost_basis": round(subscores["cost_basis"][ticker], 2),
            "s_volume_price": round(subscores["volume_price"][ticker], 2),
            "days_confirmed": days_confirmed,
            "flags": flags,
        })

    scored.sort(key=lambda s: s["composite"], reverse=True)
    return scored
