from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func
import yfinance as yf

import models
import services.data_fetcher as fetcher
import services.indicators as ind_svc
from auth import CurrentUser, get_current_user
from database import get_db

router = APIRouter(prefix="/stocks", tags=["stocks"])

# Endpoint BACA di router ini sengaja tetap publik — landing dan dashboard
# memanggilnya dari Server Component tanpa token, dan header CACHE_PASAR di
# bawah hanya sah selama jawabannya sama untuk semua orang.
#
# Endpoint TULIS butuh login (`POST /{ticker}` dan `POST /{ticker}/refresh`).
# Keduanya menyentuh satu saham saja.
#
# `POST /refresh`, `POST /scan`, dan `GET /sync-status` DIHAPUS 3 Sep 2026 beserta
# mesin `_sync_state`-nya (137 baris). Ketiganya tak pernah dipanggil frontend, dan
# pekerjaannya sudah dilakukan `scripts/daily_sync.py` di runner GitHub — tempat
# yang benar untuk pekerjaan berpuluh menit. Menjalankannya lewat HTTP berarti
# menyandera worker Space yang sedang melayani pengunjung, dan untuk `scan` itu
# berbahaya: ia menghapus seluruh tabel `signals` LEBIH DULU lalu menghitung ulang,
# jadi run yang terpotong (Space gratis tidur saat idle) meninggalkan tabel kosong
# — yang juga dibaca AI Porto lewat `services/ai_porto/data.py`.
#
# Kemampuan yang hilang bersamanya — menarik harga dari tanggal terakhir tiap saham,
# bukan `period="5d"` — dipindahkan ke `daily_sync.py --penuh`, dapat dijalankan
# lewat tombol "Run workflow" pada `daily-sync.yml` dengan mode `penuh`.

# Harga di aplikasi ini berasal dari `daily_sync` yang jalan sekali sehari setelah
# bursa tutup, jadi jawaban yang sama diulang sepanjang hari. Tanpa header ini
# browser tak punya izin menyimpan apa pun: tiap siklus `usePollingSaatTerlihat`
# (5 menit) mengunduh ulang seluruh payload — 78 KB per siklus untuk dashboard,
# ~7,4 MB sehari untuk satu tab yang dibiarkan terbuka.
#
# 300 detik disamakan dengan jeda polling frontend dan `revalidate` ISR, jadi tak
# ada lapisan yang lebih basi daripada lapisan lain. `stale-while-revalidate`
# memberi satu jam tambahan: saat kedaluwarsa, salinan lama boleh dipakai sementara
# yang segar diambil di latar — layar tak pernah kosong menunggu jaringan.
#
# `public` (bukan `private`) sengaja: kelima endpoint di bawah tak membaca user
# sama sekali, jawabannya identik untuk semua orang. Ini penting karena `apiFetch`
# frontend tetap menyertakan header Authorization saat user login, dan tanpa
# `public` yang eksplisit cache bersama dilarang menyimpan respons semacam itu.
#
# JANGAN dipasang di endpoint yang membaca user. Kalau kelimanya nanti dipagari
# login, nilai ini harus berubah jadi `private`.
CACHE_PASAR = "public, max-age=300, stale-while-revalidate=3600"

# Segmen jalur yang bukan kode saham. Dipakai `add_custom_stock` — lihat alasannya
# di sana. Tambahkan ke sini setiap kali ada rute statis baru di bawah /stocks.
NAMA_RUTE_BUKAN_TICKER = {"IHSG", "SIGNALS", "SCAN", "REFRESH", "SYNC-STATUS"}


def cache_pasar(response: Response):
    """Tandai respons sebagai data pasar yang boleh disimpan 5 menit.

    Dipasang lewat `dependencies=[...]` di dekorator, bukan sebagai parameter
    endpoint, supaya tanda tangan fungsi yang sudah ada tak perlu diubah.
    """
    response.headers["Cache-Control"] = CACHE_PASAR


@router.get("", dependencies=[Depends(cache_pasar)])
def list_stocks(
    db: Session = Depends(get_db),
    ringkas: bool = Query(
        False,
        description="Kirim hanya ticker, name, last_price, change_pct — yang "
                    "benar-benar ditampilkan dashboard dan overview.",
    ),
):
    # Space HF gratis mengirim ~35 KB/detik, jadi payload penuh 179 KB berarti
    # lima detik layar kosong — dan dashboard mengulangnya tiap siklus polling.
    # Dashboard dan overview tak pernah menyentuh sector, prev_close, last_date,
    # maupun kolom fundamental; hanya screener yang membacanya. Membuangnya
    # memangkas payload jadi 64 KB.
    kolom_saham = [models.Stock.id, models.Stock.ticker, models.Stock.name]
    if not ringkas:
        kolom_saham += [
            models.Stock.sector,
            models.Stock.market_cap, models.Stock.pe_ratio,
            models.Stock.pbv_ratio, models.Stock.dividend_yield,
        ]
    stocks = db.query(*kolom_saham).order_by(models.Stock.ticker).all()

    # Dua baris terakhir per saham — untuk harga terkini dan pembanding harian.
    #
    # Dulu ini tiga query: satu agregat max(date), satu join balik untuk baris
    # terkini, lalu sepasang lagi untuk baris sebelumnya. Empat pindaian penuh
    # atas ~800 ribu baris tiap kali dashboard dimuat, dan tiap baris ditarik
    # lengkap 9 kolom padahal hanya date dan close yang dibaca di bawah.
    #
    # row_number() menyelesaikannya dalam satu pindaian, dan indeks
    # (stock_id, date) yang sudah ada melayaninya langsung. Sengaja TIDAK
    # dibatasi rentang tanggal: ~131 saham suspensi terakhir berdagang berbulan
    # lalu, dan jendela pendek akan menghapus harganya dari daftar.
    peringkat = (
        db.query(
            models.OHLCVDaily.stock_id.label("stock_id"),
            models.OHLCVDaily.date.label("date"),
            models.OHLCVDaily.close.label("close"),
            func.row_number()
            .over(
                partition_by=models.OHLCVDaily.stock_id,
                order_by=models.OHLCVDaily.date.desc(),
            )
            .label("rn"),
        )
        .subquery()
    )

    latest_map: dict = {}
    prev_map: dict = {}
    for row in db.query(peringkat).filter(peringkat.c.rn <= 2).all():
        target = latest_map if row.rn == 1 else prev_map
        target[row.stock_id] = row

    result = []
    for stock in stocks:
        latest = latest_map.get(stock.id)
        prev = prev_map.get(stock.id)
        last_price = latest.close if latest else None
        prev_close = prev.close if prev else None
        if last_price and prev_close and prev_close > 0:
            change_pct = round((last_price - prev_close) / prev_close * 100, 2)
        else:
            change_pct = None
        baris = {
            "ticker": stock.ticker,
            "name": stock.name,
            "last_price": last_price,
            "change_pct": change_pct,
        }
        if not ringkas:
            baris.update({
                "sector": stock.sector,
                "prev_close": prev_close,
                "last_date": str(latest.date) if latest else None,
                "market_cap": stock.market_cap,
                "pe_ratio": stock.pe_ratio,
                "pbv_ratio": stock.pbv_ratio,
                "dividend_yield": stock.dividend_yield,
            })
        result.append(baris)
    return result


# Static paths must come BEFORE parameterized /{ticker} routes
@router.get("/ihsg", dependencies=[Depends(cache_pasar)])
def get_ihsg(db: Session = Depends(get_db)):
    """Returns IHSG composite index latest price and daily change — from local DB."""
    stock = db.query(models.Stock).filter(models.Stock.ticker == "^JKSE").first()
    if stock:
        rows = (
            db.query(models.OHLCVDaily)
            .filter(models.OHLCVDaily.stock_id == stock.id)
            .order_by(desc(models.OHLCVDaily.date))
            .limit(2)
            .all()
        )
        if len(rows) >= 2:
            latest, prev = rows[0], rows[1]
            change     = latest.close - prev.close
            change_pct = (change / prev.close * 100) if prev.close > 0 else 0
            return {
                "price":      round(latest.close, 2),
                "change":     round(change, 2),
                "change_pct": round(change_pct, 2),
                "date":       str(latest.date),
            }

    # Fallback: fetch live from Yahoo Finance if ^JKSE not in DB
    try:
        df = fetcher.fetch_ohlcv("^JKSE", period="5d")
        if df is None or df.empty or len(df) < 2:
            return {"price": None, "change": None, "change_pct": None, "date": None}

        def to_f(val):
            return float(val.iloc[0]) if hasattr(val, "iloc") else float(val)

        latest_close = to_f(df["Close"].iloc[-1])
        prev_close   = to_f(df["Close"].iloc[-2])
        change       = latest_close - prev_close
        change_pct   = (change / prev_close * 100) if prev_close > 0 else 0
        latest_idx   = df.index[-1]
        date_str     = latest_idx.strftime("%Y-%m-%d") if hasattr(latest_idx, "strftime") else str(latest_idx)
        return {
            "price":      round(latest_close, 2),
            "change":     round(change, 2),
            "change_pct": round(change_pct, 2),
            "date":       date_str,
        }
    except Exception:
        return {"price": None, "change": None, "change_pct": None, "date": None}


@router.get("/signals", dependencies=[Depends(cache_pasar)])
def get_ai_signals(db: Session = Depends(get_db)):
    # joinedload menghindari N+1 (dulu tiap s.stock jadi query terpisah — 400+
    # round-trip ke pooler bikin endpoint hang belasan detik).
    signals = (
        db.query(models.Signal)
        .options(joinedload(models.Signal.stock))
        .order_by(desc(models.Signal.created_at))
        .all()
    )
    grouped: dict = {}
    for s in signals:
        ticker = s.stock.ticker
        if ticker not in grouped:
            grouped[ticker] = {
                "ticker": ticker,
                "name": s.stock.name,
                "type": s.type,
                "strategies": [],
                "max_strength": 0,
                "date": s.created_at.strftime("%Y-%m-%d %H:%M"),
                "market_cap": s.stock.market_cap,
            }
        grouped[ticker]["strategies"].append(s.strategy_id)
        if s.strength > grouped[ticker]["max_strength"]:
            grouped[ticker]["max_strength"] = s.strength
    return [
        g for g in sorted(grouped.values(), key=lambda x: x["max_strength"], reverse=True)
        if g["max_strength"] >= 80
    ]


# Parameterized routes after static ones
@router.post("/{ticker}")
def add_custom_stock(ticker: str, db: Session = Depends(get_db),
                     _: CurrentUser = Depends(get_current_user)):
    """Tambah saham baru ke semesta aplikasi. Butuh login.

    Cukup `get_current_user` (bukan dev): dampaknya satu baris `stocks` dan satu
    panggilan yfinance, bukan seluruh pasar.
    """
    ticker = ticker.upper()

    # `POST /stocks/apa-pun` jatuh ke sini. Rute statis di router ini semuanya GET,
    # jadi POST ke jalur yang sama TIDAK terhalang olehnya — `POST /stocks/ihsg`
    # sudah sejak dulu berarti "tambah saham bernama IHSG". Sejak `/refresh`,
    # `/scan`, dan `/sync-status` dihapus (3 Sep 2026), tiga nama itu ikut jatuh
    # ke sini: klien lama yang memanggil `POST /stocks/scan` akan mendapat
    # "Stock not found on Yahoo Finance" — pesan yang menyesatkan untuk endpoint
    # yang sebenarnya sudah tidak ada.
    if ticker in NAMA_RUTE_BUKAN_TICKER:
        raise HTTPException(
            status_code=404,
            detail=f"'{ticker}' bukan kode saham. Endpoint /stocks/{ticker.lower()} "
                   f"sudah tidak ada — lihat scripts/daily_sync.py.",
        )

    existing = db.query(models.Stock).filter(models.Stock.ticker == ticker).first()
    if existing:
        return {"status": "exists", "ticker": ticker}

    try:
        yf_ticker = yf.Ticker(f"{ticker}.JK")
        info = yf_ticker.info

        if not info or 'longName' not in info:
            yf_ticker = yf.Ticker(ticker)
            info = yf_ticker.info

        if not info or 'longName' not in info:
            raise HTTPException(status_code=404, detail="Stock not found on Yahoo Finance")

        new_stock = models.Stock(
            ticker=ticker,
            name=info.get('longName', ticker),
            sector=info.get('sector', 'Unknown'),
            market_cap_cat="custom"
        )
        db.add(new_stock)
        db.commit()
        db.refresh(new_stock)

        df = fetcher.fetch_ohlcv(ticker)
        fetcher.save_ohlcv(db, new_stock, df)

        return {"status": "added", "ticker": ticker, "name": new_stock.name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{ticker}/ohlcv", dependencies=[Depends(cache_pasar)])
def get_ohlcv(
    ticker: str,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    stock = db.query(models.Stock).filter(models.Stock.ticker == ticker.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker.upper()} not found")

    query = db.query(models.OHLCVDaily).filter(models.OHLCVDaily.stock_id == stock.id)
    if from_date:
        query = query.filter(models.OHLCVDaily.date >= from_date)
    if to_date:
        query = query.filter(models.OHLCVDaily.date <= to_date)

    rows = query.order_by(models.OHLCVDaily.date).all()
    return {
        "ticker": stock.ticker,
        "name": stock.name,
        # Sektor ikut di sini supaya halaman detail saham tak perlu mengunduh
        # daftar saham payload PENUH (174 KB) hanya demi satu kolom. Endpoint ini
        # memang sudah mengembalikan metadata saham (`name`), jadi menambah satu
        # field lagi konsisten — dan biayanya belasan byte, bukan puluhan kilobyte.
        "sector": stock.sector,
        "data": [
            {"date": str(r.date), "open": r.open, "high": r.high,
             "low": r.low, "close": r.close, "volume": r.volume}
            for r in rows
        ],
    }


@router.get("/{ticker}/indicators", dependencies=[Depends(cache_pasar)])
def get_indicators(ticker: str, db: Session = Depends(get_db)):
    stock = db.query(models.Stock).filter(models.Stock.ticker == ticker.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker.upper()} not found")
    return {"ticker": stock.ticker, "indicators": ind_svc.calculate_indicators(db, stock)}


@router.post("/{ticker}/refresh")
def refresh_stock(ticker: str, db: Session = Depends(get_db),
                  _: CurrentUser = Depends(get_current_user)):
    """Tarik ulang harga satu saham. Butuh login.

    Tidak disebut di AUDIT-OPTIMALISASI.md §9 — terlewat di sana. Bentuknya sama
    dengan `POST /{ticker}`: yfinance + tulis ke `ohlcv_daily`.
    """
    stock = db.query(models.Stock).filter(models.Stock.ticker == ticker.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker.upper()} not found")
    try:
        df = fetcher.fetch_ohlcv(stock.ticker)
        count = fetcher.save_ohlcv(db, stock, df)
        return {"ticker": stock.ticker, "status": "ok", "new_rows": count}
    except Exception as e:
        return {"ticker": stock.ticker, "status": "error", "error": str(e)}
