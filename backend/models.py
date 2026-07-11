import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Float, Date, DateTime, ForeignKey, UniqueConstraint, func, JSON, Text
from sqlalchemy.orm import relationship
from database import Base

class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    sector = Column(String(50), nullable=False)
    market_cap_cat = Column(String(10))
    last_updated = Column(DateTime)

    # Fundamentals
    market_cap = Column(BigInteger)
    pe_ratio = Column(Float)
    pbv_ratio = Column(Float)
    dividend_yield = Column(Float)
    forward_pe = Column(Float)

    ohlcv = relationship("OHLCVDaily", back_populates="stock", cascade="all, delete-orphan")
    indicators = relationship("IndicatorCache", back_populates="stock", cascade="all, delete-orphan")
    trades = relationship("TradeLog", back_populates="stock", cascade="all, delete-orphan")

class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    strategy_id = Column(String(50), nullable=False)
    type = Column(String(10), nullable=False) # BUY / SELL
    price = Column(Float)
    strength = Column(Float) # Score 0-100
    description = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())
    is_read = Column(Integer, default=0)

    stock = relationship("Stock")

class OHLCVDaily(Base):
    __tablename__ = "ohlcv_daily"
    __table_args__ = (UniqueConstraint("stock_id", "date", name="uq_ohlcv_stock_date"),)

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float, nullable=False)
    volume = Column(BigInteger)
    adj_close = Column(Float)

    stock = relationship("Stock", back_populates="ohlcv")

class IndicatorCache(Base):
    __tablename__ = "indicators_cache"
    __table_args__ = (UniqueConstraint("stock_id", "date", "indicator_type", name="uq_indicator"),)

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    indicator_type = Column(String(30), nullable=False)
    value = Column(Float)
    calculated_at = Column(DateTime, server_default=func.now())

    stock = relationship("Stock", back_populates="indicators")

class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    conditions = Column(JSON, nullable=False)  # Entry/Exit conditions
    parameters = Column(JSON)                 # SL, TP, Capital, etc.
    created_at = Column(DateTime, server_default=func.now())

    backtests = relationship("BacktestRun", back_populates="strategy")

class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=False)
    
    # Metrics
    total_trades = Column(Integer)
    win_rate = Column(Float)
    profit_factor = Column(Float)
    max_drawdown = Column(Float)
    sharpe_ratio = Column(Float)
    total_return = Column(Float)
    
    # Detailed Data (JSON)
    equity_curve = Column(JSON)    # Array of daily portfolio values
    trades_detail = Column(JSON)   # List of all trades in this run
    created_at = Column(DateTime, server_default=func.now())

    strategy = relationship("Strategy", back_populates="backtests")
    trades = relationship("TradeLog", back_populates="backtest_run")

class TradeLog(Base):
    __tablename__ = "trade_logs"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    action = Column(String(10), nullable=False)      # BUY / SELL
    date = Column(Date, nullable=False, index=True)
    price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)       # In Lots (100 shares)
    trade_type = Column(String(20), nullable=False)  # MANUAL / AUTO_GEMINI / AUTO_CLAUDE
    strategy_id = Column(String(50), nullable=True)  # New: ID strategi yang digunakan
    notes = Column(String(255))                      # New: Alasan beli/jual (reasoning)
    backtest_run_id = Column(Integer, ForeignKey("backtest_runs.id"), nullable=True)
    # Pemilik trade. NULL = trade global/AI (AUTO_GEMINI/AUTO_CLAUDE). Trade manual user
    # diisi UUID Supabase agar portofolio ter-scope per user.
    user_id = Column(String(36), index=True, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    stock = relationship("Stock", back_populates="trades")
    backtest_run = relationship("BacktestRun", back_populates="trades")


class AgentPositionTarget(Base):
    __tablename__ = "agent_position_targets"

    id = Column(Integer, primary_key=True, index=True)
    agent_name = Column(String(20), nullable=False, index=True)   # CLAUDE / GEMINI / USER
    ticker = Column(String(10), nullable=False, index=True)
    take_profit_price = Column(Float, nullable=True)
    cut_loss_price = Column(Float, nullable=True)
    decision = Column(String(20), nullable=True)    # HOLD / BUY_MORE / WAIT / TAKE_PROFIT / CUT_LOSS
    strategy = Column(String(50), nullable=True)
    notes = Column(String(500), nullable=True)
    is_active = Column(Integer, default=1)          # 1 = posisi masih terbuka, 0 = sudah ditutup
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


class MlPrediction(Base):
    """
    Prediksi ML terbaru per saham. Satu baris per ticker dan di-overwrite (upsert)
    setiap kali daily_sync melatih ulang — jadi tabel ini tidak pernah membengkak
    (selalu ~jumlah saham, bukan bertambah tiap hari).
    """
    __tablename__ = "ml_predictions"

    ticker           = Column(String(10), primary_key=True, index=True)
    direction        = Column(String(10))   # BULLISH / BEARISH / NEUTRAL
    recommendation   = Column(String(10))    # BUY / WAIT / HOLD
    probability_up   = Column(Float)
    probability_down = Column(Float)
    confidence       = Column(Float)
    horizon_days     = Column(Integer, default=5)
    top_features     = Column(JSON)          # list[{name, importance}]
    model_accuracy   = Column(Float)
    model_auc        = Column(Float)
    samples_train    = Column(Integer)
    trained_at       = Column(String(40))    # ISO timestamp (string, sesuai output training)
    updated_at       = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AdvisorUsage(Base):
    """
    Pemakaian kuota AI Advisor per user per hari. Unik per (user_id, tanggal) — baris
    baru tiap hari (reset harian). Increment hanya saat pipeline benar-benar jalan.
    """
    __tablename__ = "advisor_usage"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_advisor_usage_user_date"),)

    id      = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    date    = Column(Date, nullable=False, index=True)
    count   = Column(Integer, default=0, nullable=False)


class Profile(Base):
    """Profil user aplikasi, 1:1 dengan user Supabase Auth (id = UUID Supabase).

    Dibuat otomatis saat user terautentikasi pertama kali (lihat auth.ensure_profile).
    Tier diatur manual oleh admin (SQL/Supabase dashboard); semua user baru = 'free'.
    """
    __tablename__ = "profiles"

    id         = Column(String(36), primary_key=True)   # = Supabase auth user UUID
    email      = Column(String(255), index=True)
    tier       = Column(String(20), nullable=False, default="free")
    created_at = Column(DateTime, server_default=func.now())

    # Tautan Telegram (fitur Big Money). Penautan memakai kode sekali pakai yang
    # dibuat saat user SUDAH login — bukan dengan mengetik email di bot. Email itu
    # identitas, bukan bukti kepemilikan: siapa pun yang tahu email orang lain akan
    # bisa membajak notifikasinya.
    telegram_chat_id         = Column(String(32), index=True)
    telegram_link_code       = Column(String(12))
    telegram_code_expires_at = Column(DateTime)


class Watchlist(Base):
    """Watchlist per user (sebelumnya localStorage di frontend). Unik per (user, ticker)."""
    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),)

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(String(36), nullable=False, index=True)
    ticker     = Column(String(10), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class BrokerFlow(Base):
    """
    Ringkasan aktivitas broker harian dari IDX (aggregate seluruh pasar, bukan per-saham).
    Source: idx.co.id/primary/TradingSummary/GetBrokerSummary
    """
    __tablename__ = "broker_flows"
    __table_args__ = (UniqueConstraint("date", "broker_code", name="uq_broker_flow"),)

    id          = Column(Integer, primary_key=True, index=True)
    date        = Column(Date, nullable=False, index=True)
    broker_code = Column(String(10), nullable=False)
    broker_name = Column(String(200))
    total_value = Column(BigInteger, default=0)   # total nilai transaksi (beli+jual) dalam Rupiah
    volume      = Column(BigInteger, default=0)    # total volume dalam lot
    frequency   = Column(Integer, default=0)       # jumlah transaksi
    scraped_at  = Column(DateTime, server_default=func.now())


class BigMoneyStockDaily(Base):
    """Snapshot harian per saham dari IDX GetStockSummary + metrik turunan.

    `ticker` sengaja bukan ForeignKey: IDX memuat saham yang belum ada di tabel
    `stocks`, dan agregat pasar (penyebut relative foreign flow) harus dihitung
    dari seluruh pasar agar tidak bias.

    Kolom turunan bernilai NULL bila pembaginya nol — bukan 0 — supaya fungsi
    agregat SQL mengabaikannya. Sekitar 13,7% baris IDX punya volume = 0.
    """
    __tablename__ = "bigmoney_stock_daily"
    __table_args__ = (UniqueConstraint("ticker", "date", name="uq_bmsd_ticker_date"),)

    id            = Column(Integer, primary_key=True, index=True)
    ticker        = Column(String(10), nullable=False, index=True)
    date          = Column(Date, nullable=False, index=True)

    # mentah dari IDX GetStockSummary
    prev_close    = Column(Float)
    open_price    = Column(Float)
    high          = Column(Float)
    low           = Column(Float)
    close         = Column(Float)
    volume        = Column(BigInteger, default=0)   # lembar, bukan lot
    value         = Column(BigInteger, default=0)   # Rupiah
    frequency     = Column(Integer, default=0)
    listed_shares = Column(BigInteger)
    foreign_buy   = Column(BigInteger, default=0)   # lembar
    foreign_sell  = Column(BigInteger, default=0)   # lembar

    # turunan, dihitung saat ingest
    foreign_net           = Column(BigInteger)  # lembar
    vwap                  = Column(Float)
    foreign_net_value     = Column(BigInteger)  # Rupiah — ESTIMASI (foreign_net * VWAP pasar)
    avg_ticket            = Column(Float)       # value/frequency — proxy aktivitas institusi
    foreign_participation = Column(Float)
    change_pct            = Column(Float)

    scraped_at    = Column(DateTime, server_default=func.now())


class BigMoneyMarketRegime(Base):
    """Rezim pasar harian, diturunkan dari agregat bigmoney_stock_daily.

    Sengaja tidak memakai OHLCV `^JKSE`: tabel itu tertinggal berminggu-minggu
    dari data bigmoney, sehingga rezimnya akan salah. Deret pasar di sini selalu
    sesegar ingest terakhir.

    `weight_set` memilih himpunan bobot sinyal di services/bigmoney/scoring.py.
    """
    __tablename__ = "bigmoney_market_regime"
    __table_args__ = (UniqueConstraint("date", name="uq_bmmr_date"),)

    id                      = Column(Integer, primary_key=True, index=True)
    date                    = Column(Date, nullable=False, index=True)

    volatility_regime       = Column(String(10))   # CALM | VOLATILE
    trend_regime            = Column(String(10))   # BULL | SIDEWAYS | BEAR
    weight_set              = Column(String(10))   # CALM | VOLATILE

    market_return_pct       = Column(Float)        # return pasar tertimbang nilai transaksi
    market_volatility_20d   = Column(Float)        # stdev return harian, 20 hari
    breadth                 = Column(Float)        # rasio saham naik terhadap yang bergerak
    total_foreign_net_value = Column(BigInteger)   # Rupiah — ESTIMASI
    sector_rotation         = Column(JSON)         # {sektor: foreign_net_value}

    computed_at             = Column(DateTime, server_default=func.now())


class BigMoneyScore(Base):
    """Skor big money per saham per hari, hanya untuk saham yang lolos filter likuiditas.

    Subskor adalah peringkat persentil (0-100) di antara universe HARI ITU, bukan
    ambang absolut: dengan 77 hari data, ambang tebakan tak punya dasar dan basi
    begitu skala pasar bergeser.

    Karena skor bersifat relatif, sesuatu selalu meraih peringkat ~100 bahkan di
    hari terburuk. `days_confirmed` yang menahan itu — STRONG mustahil tanpa tiga
    hari inflow asing beruntun.
    """
    __tablename__ = "bigmoney_score"
    __table_args__ = (UniqueConstraint("ticker", "date", name="uq_bms_ticker_date"),)

    id             = Column(Integer, primary_key=True, index=True)
    ticker         = Column(String(10), nullable=False, index=True)
    date           = Column(Date, nullable=False, index=True)

    composite      = Column(Float)       # 0-100, sudah dipotong bila divergence
    conviction     = Column(String(10))  # STRONG | WATCH | WEAK
    phase          = Column(String(12))  # AKUMULASI | MARKUP | DISTRIBUSI | MARKDOWN | NETRAL
    weight_set     = Column(String(10))  # rezim yang berlaku saat skor dihitung

    s_relative_foreign_flow = Column(Float)
    s_foreign_persistence   = Column(Float)
    s_big_ticket            = Column(Float)
    s_cost_basis            = Column(Float)
    s_volume_price          = Column(Float)

    days_confirmed = Column(Integer, default=0)  # hari beruntun foreign_net > 0
    flags          = Column(JSON)                # {divergence, pump_dump_risk}

    computed_at    = Column(DateTime, server_default=func.now())


class BigMoneyTopAccumulation(Base):
    """Peringkat 10 besar per tanggal — target baca API dan laporan AI.

    Tabel tipis ini ada supaya konsumen tak perlu memindai bigmoney_score.
    Ditulis ulang seluruhnya tiap kali skor dihitung ulang: peringkat harus
    konsisten dengan skor yang melahirkannya.
    """
    __tablename__ = "bigmoney_top_accumulation"
    __table_args__ = (UniqueConstraint("date", "rank", name="uq_bmta_date_rank"),)

    id          = Column(Integer, primary_key=True, index=True)
    date        = Column(Date, nullable=False, index=True)
    rank        = Column(Integer, nullable=False)

    ticker      = Column(String(10), nullable=False, index=True)
    composite   = Column(Float)
    conviction  = Column(String(10))
    phase       = Column(String(12))

    computed_at = Column(DateTime, server_default=func.now())


class BigMoneyPosition(Base):
    """Akumulasi asing yang sedang berjalan pada satu saham — bukan peringkat harian.

    Peringkat harian berganti 6-9 nama tiap hari; itu membuat perkembangan sebuah
    akumulasi mustahil diikuti. Posisi menjawab itu: saham MASUK ketika akumulasinya
    terbukti (asing net beli >= 3 dari 5 hari terakhir dan skor >= 55), lalu BERTAHAN
    meski peringkat hariannya turun.

    Keluarnya dibandingkan dengan akumulasinya sendiri, bukan dengan skor: posisi
    ditutup ketika dana yang keluar sejak puncak melampaui separuh dari yang pernah
    masuk, atau ketika fase distribusi/markdown bertahan dua hari beruntun.

    `peak_value` adalah akumulasi bersih tertinggi yang pernah dicapai; `accumulated_value`
    adalah posisinya sekarang. Selisih keduanya adalah dana yang sudah ditarik keluar.
    """
    __tablename__ = "bigmoney_position"

    id                = Column(Integer, primary_key=True, index=True)
    ticker            = Column(String(10), nullable=False, index=True)

    opened_on         = Column(Date, nullable=False, index=True)
    closed_on         = Column(Date, index=True)
    status            = Column(String(10), nullable=False, default="ACTIVE", index=True)  # ACTIVE | CLOSED

    entry_close       = Column(Float)    # harga saat masuk — pembanding perkembangan harga
    last_close        = Column(Float)
    last_date         = Column(Date)

    accumulated_value = Column(BigInteger, default=0)  # Rupiah, ESTIMASI — net asing sejak masuk
    peak_value        = Column(BigInteger, default=0)  # akumulasi tertinggi yang pernah dicapai
    inflow_days       = Column(Integer, default=0)     # hari asing net beli sejak masuk
    distribution_days = Column(Integer, default=0)     # fase jual beruntun; 2 = keluar

    entry_score       = Column(Float)
    last_score        = Column(Float)
    close_reason      = Column(String(40))   # DISTRIBUSI | OUTFLOW | (NULL selama aktif)

    updated_at        = Column(DateTime, server_default=func.now())


class BigMoneyDailyReport(Base):
    """Laporan harian berbahasa manusia, ditulis Gemini dari skor dan rezim.

    `context` menyimpan angka persis yang disodorkan ke model. Tanpa itu, laporan
    lama tak bisa diaudit: kita takkan tahu apakah kalimatnya salah karena
    modelnya mengarang atau karena datanya memang begitu.

    Gemini di sini terpisah total dari Groq, yang tetap milik AI Advisor EMETIQ.
    """
    __tablename__ = "bigmoney_daily_report"
    __table_args__ = (UniqueConstraint("date", name="uq_bmdr_date"),)

    id           = Column(Integer, primary_key=True, index=True)
    date         = Column(Date, nullable=False, index=True)

    headline     = Column(String(300))
    narrative    = Column(Text)
    context      = Column(JSON)      # angka yang disodorkan ke model — untuk audit
    model        = Column(String(50))

    generated_at = Column(DateTime, server_default=func.now())
    sent_at      = Column(DateTime)  # penanda broadcast Telegram; NULL = belum terkirim
