"""Rezim pasar harian, diturunkan dari agregat bigmoney_stock_daily.

Sengaja TIDAK memakai OHLCV `^JKSE`: tabel itu tertinggal berminggu-minggu dari
data bigmoney, sehingga rezim yang dihitung darinya akan bohong. Deret pasar di
sini selalu sesegar ingest terakhir.

Konsekuensinya deret ini bukan IHSG resmi — dan itu diterima. Rezim cuma perlu
memilih antara CALM dan VOLATILE, bukan melaporkan level indeks.

`detect_regime` murni (bisa diuji tanpa DB); `market_series` dan `compute_regime`
menyentuh database.
"""
from datetime import date
from statistics import stdev

from sqlalchemy.orm import Session

import models

_WINDOW_DAYS = 20

_VOLATILE_STDEV = 1.0       # % — stdev return harian pasar di atas ini = VOLATILE
_TREND_BULL_PCT = 3.0       # % — return kumulatif jendela
_TREND_BEAR_PCT = -3.0


def market_series(db: Session, target: date, days: int = _WINDOW_DAYS) -> list[dict]:
    """Statistik pasar harian untuk `days` hari bursa terakhir sampai `target`.

    Tanggal sesudah `target` diabaikan: menghitung ulang tanggal lama tak boleh
    mengintip masa depan.
    """
    M = models.BigMoneyStockDaily
    dates = [
        d for (d,) in db.query(M.date)
                        .filter(M.date <= target)
                        .distinct()
                        .order_by(M.date.desc())
                        .limit(days)
                        .all()
    ]
    if not dates:
        return []

    rows = db.query(M).filter(M.date.in_(dates)).all()

    by_date: dict[date, list] = {}
    for row in rows:
        by_date.setdefault(row.date, []).append(row)

    series: list[dict] = []
    for day in sorted(by_date):
        day_rows = by_date[day]

        # Return tertimbang nilai transaksi: saham tipis tak boleh menggerakkan indeks.
        weight = sum(r.value or 0 for r in day_rows if r.change_pct is not None)
        weighted = sum((r.value or 0) * r.change_pct for r in day_rows if r.change_pct is not None)
        market_return = weighted / weight if weight else None

        up = sum(1 for r in day_rows if (r.change_pct or 0) > 0)
        down = sum(1 for r in day_rows if (r.change_pct or 0) < 0)
        movers = up + down

        series.append({
            "date": day,
            "market_return_pct": market_return,
            "breadth": up / movers if movers else None,
            "total_foreign_net_value": sum(r.foreign_net_value or 0 for r in day_rows),
        })

    return series


def detect_regime(series: list[dict]) -> dict | None:
    """Deret pasar → volatility_regime, trend_regime, weight_set. Fungsi murni.

    Pasar beruntun turun memaksa bobot VOLATILE meski ayunannya tenang: saat tren
    turun, harga masuk lebih menentukan daripada arah aliran dana, dan di situlah
    bobot cost basis perlu naik.
    """
    if not series:
        return None

    returns = [s["market_return_pct"] for s in series if s["market_return_pct"] is not None]
    volatility = stdev(returns) if len(returns) > 1 else None
    cumulative = sum(returns)

    volatility_regime = "VOLATILE" if volatility is not None and volatility > _VOLATILE_STDEV else "CALM"

    if cumulative >= _TREND_BULL_PCT:
        trend_regime = "BULL"
    elif cumulative <= _TREND_BEAR_PCT:
        trend_regime = "BEAR"
    else:
        trend_regime = "SIDEWAYS"

    weight_set = "VOLATILE" if volatility_regime == "VOLATILE" or trend_regime == "BEAR" else "CALM"

    today = series[-1]
    return {
        "volatility_regime": volatility_regime,
        "trend_regime": trend_regime,
        "weight_set": weight_set,
        "market_return_pct": today["market_return_pct"],
        "market_volatility_20d": volatility,
        "breadth": today["breadth"],
        "total_foreign_net_value": today["total_foreign_net_value"],
    }


def _sector_rotation(db: Session, target: date) -> dict:
    """Agregat foreign_net_value per sektor pada `target`.

    Saham yang tak ada di tabel `stocks` (IDX memuat ~964, stocks ~737) dilewati
    diam-diam — mengarang sektor untuk mereka lebih buruk daripada tak melaporkan.
    """
    sectors = {ticker: sector for ticker, sector in db.query(models.Stock.ticker, models.Stock.sector).all()}

    rotation: dict[str, int] = {}
    M = models.BigMoneyStockDaily
    for row in db.query(M).filter(M.date == target).all():
        sector = sectors.get(row.ticker)
        if not sector:
            continue
        rotation[sector] = rotation.get(sector, 0) + (row.foreign_net_value or 0)

    return rotation


def compute_regime(target: date, db: Session) -> models.BigMoneyMarketRegime | None:
    """Hitung dan simpan rezim untuk `target`. Idempoten: memperbarui, tak menggandakan.

    Mengembalikan None bila `target` bukan hari bursa (tak ada baris sama sekali).
    """
    detected = detect_regime(market_series(db, target))
    if detected is None:
        return None

    detected["sector_rotation"] = _sector_rotation(db, target)

    regime = (
        db.query(models.BigMoneyMarketRegime)
          .filter(models.BigMoneyMarketRegime.date == target)
          .one_or_none()
    )
    if regime is None:
        regime = models.BigMoneyMarketRegime(date=target)
        db.add(regime)

    for column, value in detected.items():
        setattr(regime, column, value)

    db.commit()
    db.refresh(regime)
    return regime
