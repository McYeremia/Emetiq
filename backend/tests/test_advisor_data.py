"""Tes deterministik untuk services/advisor/data_provider.py (TANPA LLM).

Menjamin akurasi angka: filter screening, perhitungan analisa, dan agregasi
portofolio harus benar sebelum LLM menalar di atasnya.
"""
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
import models
from services.advisor import data_provider as dp


def _add_stock(s, ticker, name, sector, pe, pbv, div, mcap):
    st = models.Stock(ticker=ticker, name=name, sector=sector,
                      pe_ratio=pe, pbv_ratio=pbv, dividend_yield=div, market_cap=mcap)
    s.add(st)
    s.flush()
    return st


def _add_series(s, stock, start, step, n=60):
    d0 = date(2026, 1, 1)
    for i in range(n):
        price = start + step * i
        s.add(models.OHLCVDaily(
            stock_id=stock.id, date=d0 + timedelta(days=i),
            open=price, high=price * 1.01, low=price * 0.99, close=price, volume=1_000_000,
        ))


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()

    bbri = _add_stock(s, "BBRI", "Bank BRI", "Finance", pe=9.0, pbv=2.0, div=4.0, mcap=800_000_000_000_000)
    tlkm = _add_stock(s, "TLKM", "Telkom", "Telco", pe=18.0, pbv=3.0, div=5.0, mcap=400_000_000_000_000)
    goto = _add_stock(s, "GOTO", "GoTo", "Tech", pe=None, pbv=2.0, div=0.0, mcap=100_000_000_000_000)

    _add_series(s, bbri, start=4000, step=10)    # uptrend
    _add_series(s, tlkm, start=5000, step=-10)    # downtrend
    _add_series(s, goto, start=100, step=1)       # uptrend
    s.commit()
    yield s
    s.close()


# ── Screening ────────────────────────────────────────────────────────────────

def test_screen_pe_filter(db):
    res = dp.screen(db, pe_max=10)
    tickers = {r["ticker"] for r in res}
    assert tickers == {"BBRI"}              # TLKM pe=18 keluar, GOTO pe=None keluar


def test_screen_dividend_filter(db):
    res = dp.screen(db, div_min=4.5)
    tickers = {r["ticker"] for r in res}
    assert tickers == {"TLKM"}              # hanya TLKM div>=4.5


def test_screen_sector_filter(db):
    res = dp.screen(db, sector="Tech")
    assert [r["ticker"] for r in res] == ["GOTO"]


def test_screen_trend_filter(db):
    res = dp.screen(db, trend="up")
    tickers = {r["ticker"] for r in res}
    assert "BBRI" in tickers and "GOTO" in tickers
    assert "TLKM" not in tickers            # downtrend tersaring


def test_screen_empty_when_impossible(db):
    assert dp.screen(db, pe_max=1) == []    # tak ada yang PE<=1


def test_screen_price_max_filter(db):
    # harga kini: BBRI 4590, TLKM 4410, GOTO 159
    res = dp.screen(db, price_max=1000)
    assert {r["ticker"] for r in res} == {"GOTO"}


def test_screen_price_min_filter(db):
    res = dp.screen(db, price_min=4500)
    assert {r["ticker"] for r in res} == {"BBRI"}   # hanya BBRI >= 4500


# ── Analisa 1 saham ──────────────────────────────────────────────────────────

def test_analyze_found_numbers(db):
    a = dp.analyze(db, "bbri")              # case-insensitive
    assert a["found"] is True
    assert a["ticker"] == "BBRI"
    assert a["last_price"] == 4590          # 4000 + 10*59
    assert a["fundamentals"]["pe"] == 9.0
    assert a["indicators"]["RSI_14"] is not None
    assert a["trend"] == "up"


def test_analyze_not_found(db):
    a = dp.analyze(db, "ZZZZ")
    assert a["found"] is False


def test_analyze_rounds_messy_numbers(db):
    st = _add_stock(db, "MESS", "Messy", "Tech",
                    pe=12.345678, pbv=3.987654, div=1.111111, mcap=1_000_000_000_000)
    _add_series(db, st, start=200, step=3)
    db.commit()
    a = dp.analyze(db, "MESS")
    assert a["fundamentals"]["pe"] == 12.35
    assert a["fundamentals"]["pbv"] == 3.99
    assert a["fundamentals"]["dividend_yield"] == 1.11
    rsi = a["indicators"]["RSI_14"]          # indikator terhitung juga rapi
    assert rsi == round(rsi, 2)


def test_screen_rounds_fundamentals(db):
    st = _add_stock(db, "MSY2", "Msy2", "Tech",
                    pe=8.123456, pbv=1.5, div=6.5, mcap=2_000_000_000_000)
    _add_series(db, st, start=300, step=2)
    db.commit()
    row = next(r for r in dp.screen(db, sector="Tech") if r["ticker"] == "MSY2")
    assert row["pe"] == 8.12


# ── Portofolio ───────────────────────────────────────────────────────────────

def test_portfolio_aggregation(db):
    bbri = db.query(models.Stock).filter_by(ticker="BBRI").first()
    db.add(models.TradeLog(stock_id=bbri.id, action="BUY", date=date(2026, 2, 1),
                           price=4000, quantity=5, trade_type="MANUAL", user_id="u1"))
    db.add(models.TradeLog(stock_id=bbri.id, action="BUY", date=date(2026, 2, 2),
                           price=4200, quantity=5, trade_type="MANUAL", user_id="u1"))
    db.commit()

    p = dp.portfolio(db, "u1")
    assert p["position_count"] == 1
    h = p["holdings"][0]
    assert h["ticker"] == "BBRI"
    assert h["shares"] == 1000
    assert h["avg_price"] == 4100.0         # (5*100*4000 + 5*100*4200) / 1000
    assert p["invested"] == 4_100_000.0
    assert p["cash"] == 10_900_000.0        # 15jt - 4.1jt + 0 realized
    # current close 4590 -> unrealized (4590-4100)*1000 = 490_000
    assert h["unrealized_pnl"] == 490_000.0


def test_portfolio_excludes_bot_trades(db):
    bbri = db.query(models.Stock).filter_by(ticker="BBRI").first()
    db.add(models.TradeLog(stock_id=bbri.id, action="BUY", date=date(2026, 2, 1),
                           price=4000, quantity=5, trade_type="AUTO_GEMINI"))
    db.commit()
    p = dp.portfolio(db, "u1")
    assert p["position_count"] == 0          # trade bot tidak masuk portofolio user


# ── Tahap 2 audit: kebenaran angka portofolio ────────────────────────────────

@pytest.fixture
def db_banyak_posisi():
    """Porto dengan posisi LEBIH BANYAK dari PORTFOLIO_MAX_POSITIONS.

    Tak ada tes yang pernah melewati batas itu — dan itulah sebabnya cacat
    `position_count` bisa hidup tenang: porto 22 posisi dilaporkan "20", sementara
    uang dari 2 posisi sisanya tetap ikut menghitung kas dan total nilai.
    """
    from services.advisor import config as advisor_config

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()

    n = advisor_config.PORTFOLIO_MAX_POSITIONS + 2
    for i in range(n):
        st = _add_stock(s, f"SHM{i:02d}", f"Saham {i}", "Uji",
                        pe=10.0, pbv=1.0, div=2.0, mcap=10 ** 12)
        _add_series(s, st, start=1000, step=1, n=40)
        # Nilai beli berbeda-beda supaya urutan pemotongan (per cost_basis) pasti.
        s.add(models.TradeLog(stock_id=st.id, action="BUY", date=date(2026, 2, 1),
                              price=1000.0 + i, quantity=1, trade_type="MANUAL",
                              user_id="u1"))
    s.commit()
    yield s, n
    s.close()


def test_position_count_melaporkan_jumlah_SEBENARNYA(db_banyak_posisi):
    s, n = db_banyak_posisi
    p = dp.portfolio(s, "u1")
    assert p["position_count"] == n, "jumlah posisi sebenarnya, bukan yang ditampilkan"
    assert p["positions_shown"] == len(p["holdings"]) < n


def test_daftar_dipotong_tidak_boleh_senyap(db_banyak_posisi):
    """LLM diminta menilai konsentrasi & alokasi kas; ia harus tahu daftarnya sebagian."""
    s, n = db_banyak_posisi
    p = dp.portfolio(s, "u1")
    catatan = p.get("catatan_pemotongan") or ""
    assert str(n) in catatan and str(p["positions_shown"]) in catatan


def test_kas_dan_total_tetap_menghitung_SELURUH_posisi(db_banyak_posisi):
    """Yang dipotong cuma daftar rinciannya — uangnya tidak boleh ikut hilang."""
    s, n = db_banyak_posisi
    p = dp.portfolio(s, "u1")
    invested_seharusnya = sum((1000.0 + i) * 100 for i in range(n))
    assert p["invested"] == pytest.approx(invested_seharusnya)
    assert p["cash"] == pytest.approx(15_000_000 - invested_seharusnya)


def test_tanpa_pemotongan_tak_ada_catatan(db):
    bbri = db.query(models.Stock).filter_by(ticker="BBRI").first()
    db.add(models.TradeLog(stock_id=bbri.id, action="BUY", date=date(2026, 2, 1),
                           price=4000, quantity=5, trade_type="MANUAL", user_id="u1"))
    db.commit()
    p = dp.portfolio(db, "u1")
    assert "catatan_pemotongan" not in p
    assert p["position_count"] == p["positions_shown"] == 1


def test_lots_bilangan_bulat(db):
    """Lot tak pernah pecahan, dan angka ini ikut masuk ke prompt."""
    bbri = db.query(models.Stock).filter_by(ticker="BBRI").first()
    db.add(models.TradeLog(stock_id=bbri.id, action="BUY", date=date(2026, 2, 1),
                           price=4000, quantity=7, trade_type="MANUAL", user_id="u1"))
    db.commit()
    lots = dp.portfolio(db, "u1")["holdings"][0]["lots"]
    assert lots == 7 and isinstance(lots, int)


def test_satu_sumber_kebenaran_dengan_trade_exec(db):
    """Advisor dan trade_exec harus SEPAKAT — dulu keduanya punya replay sendiri-sendiri.

    Tanpa tes ini, perbaikan di satu sisi tak pernah tercermin di sisi lain dan tak
    ada yang memberi tahu.
    """
    from services import trade_exec

    bbri = db.query(models.Stock).filter_by(ticker="BBRI").first()
    tlkm = db.query(models.Stock).filter_by(ticker="TLKM").first()
    for stock, aksi, harga, lot in [
        (bbri, "BUY", 4000, 5), (bbri, "BUY", 4200, 5), (bbri, "SELL", 4500, 3),
        (tlkm, "BUY", 5000, 2),
    ]:
        db.add(models.TradeLog(stock_id=stock.id, action=aksi, date=date(2026, 2, 1),
                               price=harga, quantity=lot, trade_type="MANUAL", user_id="u1"))
    db.commit()

    p = dp.portfolio(db, "u1")
    lewat_exec = trade_exec.holdings_for(db, "USER", "u1")

    assert p["cash"] == pytest.approx(trade_exec.available_cash(db, "USER", "u1"))
    assert p["position_count"] == len([x for x in lewat_exec.values() if x["shares"] > 0])
    for h in p["holdings"]:
        assert h["shares"] == lewat_exec[h["ticker"]]["shares"]
        assert h["avg_price"] == pytest.approx(lewat_exec[h["ticker"]]["avg_price"], rel=1e-9)


def test_modal_awal_tidak_diduplikasi():
    """Satu konstanta, satu makna. Dulu nilainya diketik ulang di data_provider."""
    from services import trade_exec
    assert dp.INITIAL_MODAL is trade_exec.INITIAL_MODAL
