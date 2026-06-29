# IDXAnalyst Phase 1: Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build FastAPI backend with SQLite database, yfinance EOD data pipeline, and technical indicator calculations for 80 IDX80 stocks.

**Architecture:** FastAPI serves a REST API backed by SQLite via SQLAlchemy ORM. A data fetcher service pulls EOD OHLCV from yfinance and stores it. An indicators service computes MA/EMA/RSI/MACD/BB/Stochastic/ATR on-demand using pandas-ta. Five endpoint groups expose this data to the frontend.

**Tech Stack:** Python 3.11+, FastAPI 0.115+, SQLAlchemy 2.0+, SQLite, yfinance 0.2.40+, pandas 2.0+, ta 0.11+, pytest 8+, pytest-mock, httpx

> **Note:** `pandas-ta` is deprecated/removed from PyPI. Using `ta` (Technical Analysis Library) instead — same indicators, class-based API.

---

## File Map

```
backend/
├── main.py                      FastAPI app + CORS + router registration
├── database.py                  SQLAlchemy engine + SessionLocal + Base + get_db
├── models.py                    ORM models: Stock, OHLCVDaily, IndicatorCache
├── routers/
│   ├── __init__.py              (empty)
│   └── stocks.py                All /stocks endpoints
├── services/
│   ├── __init__.py              (empty)
│   ├── data_fetcher.py          yfinance wrapper: fetch + save OHLCV
│   └── indicators.py            pandas-ta wrapper: compute indicators
├── data/
│   └── idx80.json               80 IDX80 stocks (static list)
├── requirements.txt
├── .env.example
└── tests/
    ├── __init__.py              (empty)
    ├── conftest.py              Fixtures: test DB, TestClient, sample data
    ├── test_models.py           DB table creation test
    ├── test_data_fetcher.py     Data fetcher unit tests (mocked yfinance)
    ├── test_indicators.py       Indicator calculation unit tests
    └── test_stocks_router.py    API endpoint tests
```

---

### Task 1: Bootstrap Project Structure & Requirements

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/routers/__init__.py`
- Create: `backend/services/__init__.py`
- Create: `backend/tests/__init__.py`

- [ ] **Step 1.1: Create directory structure**

```bash
mkdir -p backend/routers backend/services backend/data backend/tests
touch backend/routers/__init__.py backend/services/__init__.py backend/tests/__init__.py
```

- [ ] **Step 1.2: Write requirements.txt**

`backend/requirements.txt`:
```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
sqlalchemy>=2.0.0
python-dotenv>=1.0.0
yfinance>=0.2.40
pandas>=2.0.0
pandas-ta==0.3.14b0
numpy>=1.26.0
pytest>=8.0.0
pytest-mock>=3.14.0
httpx>=0.27.0
```

> If `pandas-ta==0.3.14b0` install fails, run instead:
> `pip install -U "git+https://github.com/twopirllc/pandas-ta.git@development"`

- [ ] **Step 1.3: Write .env.example**

`backend/.env.example`:
```
DATABASE_URL=sqlite:///./idxanalyst.db
```

- [ ] **Step 1.4: Install dependencies**

```bash
cd backend
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt
```

Expected: All packages installed with no errors.

---

### Task 2: Database Setup

**Files:**
- Create: `backend/database.py`
- Create: `backend/models.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 2.1: Write failing test**

`backend/tests/test_models.py`:
```python
from sqlalchemy import create_engine, inspect

def test_all_tables_created():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    from database import Base
    import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    tables = inspect(engine).get_table_names()
    assert "stocks" in tables
    assert "ohlcv_daily" in tables
    assert "indicators_cache" in tables
```

- [ ] **Step 2.2: Run test to confirm failure**

```bash
cd backend && pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'database'`

- [ ] **Step 2.3: Write database.py**

`backend/database.py`:
```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./idxanalyst.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2.4: Write models.py**

`backend/models.py`:
```python
import datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base

class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    sector = Column(String(50))
    market_cap_cat = Column(String(10))
    last_updated = Column(DateTime, nullable=True)

    ohlcv = relationship("OHLCVDaily", back_populates="stock", cascade="all, delete-orphan")

class OHLCVDaily(Base):
    __tablename__ = "ohlcv_daily"
    __table_args__ = (UniqueConstraint("stock_id", "date", name="uq_ohlcv_stock_date"),)

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Integer)
    adj_close = Column(Float)

    stock = relationship("Stock", back_populates="ohlcv")

class IndicatorCache(Base):
    __tablename__ = "indicators_cache"
    __table_args__ = (UniqueConstraint("stock_id", "date", "indicator_type", name="uq_indicator"),)

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    indicator_type = Column(String(30), nullable=False)
    value = Column(Float)
    calculated_at = Column(DateTime, default=datetime.datetime.utcnow)
```

- [ ] **Step 2.5: Run test to confirm pass**

```bash
pytest tests/test_models.py -v
```

Expected: `PASSED`

---

### Task 3: IDX80 Stock Data

**Files:**
- Create: `backend/data/idx80.json`

- [ ] **Step 3.1: Write idx80.json**

`backend/data/idx80.json`:
```json
[
  {"ticker": "BBCA", "name": "Bank Central Asia", "sector": "Finance"},
  {"ticker": "BBRI", "name": "Bank Rakyat Indonesia", "sector": "Finance"},
  {"ticker": "BMRI", "name": "Bank Mandiri", "sector": "Finance"},
  {"ticker": "BBNI", "name": "Bank Negara Indonesia", "sector": "Finance"},
  {"ticker": "BRIS", "name": "Bank Syariah Indonesia", "sector": "Finance"},
  {"ticker": "BNGA", "name": "Bank CIMB Niaga", "sector": "Finance"},
  {"ticker": "NISP", "name": "Bank OCBC NISP", "sector": "Finance"},
  {"ticker": "BTPS", "name": "Bank BTPN Syariah", "sector": "Finance"},
  {"ticker": "BJTM", "name": "Bank Pembangunan Daerah Jawa Timur", "sector": "Finance"},
  {"ticker": "ARTO", "name": "Bank Jago", "sector": "Finance"},
  {"ticker": "MEGA", "name": "Bank Mega", "sector": "Finance"},
  {"ticker": "PNBN", "name": "Bank Pan Indonesia", "sector": "Finance"},
  {"ticker": "BDMN", "name": "Bank Danamon Indonesia", "sector": "Finance"},
  {"ticker": "TLKM", "name": "Telkom Indonesia", "sector": "Telecom"},
  {"ticker": "EXCL", "name": "XL Axiata", "sector": "Telecom"},
  {"ticker": "ISAT", "name": "Indosat Ooredoo Hutchison", "sector": "Telecom"},
  {"ticker": "TBIG", "name": "Tower Bersama Infrastructure", "sector": "Telecom"},
  {"ticker": "TOWR", "name": "Sarana Menara Nusantara", "sector": "Telecom"},
  {"ticker": "MTEL", "name": "Dayamitra Telekomunikasi", "sector": "Telecom"},
  {"ticker": "UNVR", "name": "Unilever Indonesia", "sector": "Consumer Goods"},
  {"ticker": "ICBP", "name": "Indofood CBP Sukses Makmur", "sector": "Consumer Goods"},
  {"ticker": "INDF", "name": "Indofood Sukses Makmur", "sector": "Consumer Goods"},
  {"ticker": "HMSP", "name": "H.M. Sampoerna", "sector": "Consumer Goods"},
  {"ticker": "GGRM", "name": "Gudang Garam", "sector": "Consumer Goods"},
  {"ticker": "CPIN", "name": "Charoen Pokphand Indonesia", "sector": "Consumer Goods"},
  {"ticker": "JPFA", "name": "JAPFA Comfeed Indonesia", "sector": "Consumer Goods"},
  {"ticker": "MYOR", "name": "Mayora Indah", "sector": "Consumer Goods"},
  {"ticker": "SIDO", "name": "Industri Jamu & Farmasi Sido Muncul", "sector": "Consumer Goods"},
  {"ticker": "AMRT", "name": "Sumber Alfaria Trijaya", "sector": "Retail"},
  {"ticker": "ACES", "name": "Ace Hardware Indonesia", "sector": "Retail"},
  {"ticker": "MAPI", "name": "MAP Aktif Adiperkasa", "sector": "Retail"},
  {"ticker": "LPPF", "name": "Matahari Department Store", "sector": "Retail"},
  {"ticker": "ERAA", "name": "Erajaya Swasembada", "sector": "Retail"},
  {"ticker": "KLBF", "name": "Kalbe Farma", "sector": "Healthcare"},
  {"ticker": "MIKA", "name": "Mitra Keluarga Karyasehat", "sector": "Healthcare"},
  {"ticker": "HEAL", "name": "Medikaloka Hermina", "sector": "Healthcare"},
  {"ticker": "PRDA", "name": "Prodia Widyahusada", "sector": "Healthcare"},
  {"ticker": "ASII", "name": "Astra International", "sector": "Automotive"},
  {"ticker": "UNTR", "name": "United Tractors", "sector": "Machinery"},
  {"ticker": "AUTO", "name": "Astra Otoparts", "sector": "Automotive"},
  {"ticker": "ADRO", "name": "Adaro Energy Indonesia", "sector": "Mining"},
  {"ticker": "BYAN", "name": "Bayan Resources", "sector": "Mining"},
  {"ticker": "PTBA", "name": "Bukit Asam", "sector": "Mining"},
  {"ticker": "ITMG", "name": "Indo Tambangraya Megah", "sector": "Mining"},
  {"ticker": "HRUM", "name": "Harum Energy", "sector": "Mining"},
  {"ticker": "INDY", "name": "Indika Energy", "sector": "Mining"},
  {"ticker": "ANTM", "name": "Aneka Tambang", "sector": "Mining"},
  {"ticker": "MDKA", "name": "Merdeka Copper Gold", "sector": "Mining"},
  {"ticker": "INCO", "name": "Vale Indonesia", "sector": "Mining"},
  {"ticker": "TINS", "name": "Timah", "sector": "Mining"},
  {"ticker": "ADMR", "name": "Adaro Minerals Indonesia", "sector": "Mining"},
  {"ticker": "NCKL", "name": "Trimegah Bangun Persada", "sector": "Mining"},
  {"ticker": "MBMA", "name": "Merdeka Battery Materials", "sector": "Mining"},
  {"ticker": "BREN", "name": "Barito Renewables Energy", "sector": "Energy"},
  {"ticker": "ESSA", "name": "ESSA Industries Indonesia", "sector": "Energy"},
  {"ticker": "MEDC", "name": "Medco Energi Internasional", "sector": "Energy"},
  {"ticker": "PGAS", "name": "Perusahaan Gas Negara", "sector": "Energy"},
  {"ticker": "BSDE", "name": "Bumi Serpong Damai", "sector": "Property"},
  {"ticker": "CTRA", "name": "Ciputra Development", "sector": "Property"},
  {"ticker": "SMRA", "name": "Summarecon Agung", "sector": "Property"},
  {"ticker": "PWON", "name": "Pakuwon Jati", "sector": "Property"},
  {"ticker": "LPKR", "name": "Lippo Karawaci", "sector": "Property"},
  {"ticker": "GOTO", "name": "GoTo Gojek Tokopedia", "sector": "Technology"},
  {"ticker": "BUKA", "name": "Bukalapak.com", "sector": "Technology"},
  {"ticker": "EMTK", "name": "Elang Mahkota Teknologi", "sector": "Technology"},
  {"ticker": "DNET", "name": "Indointernet", "sector": "Technology"},
  {"ticker": "JSMR", "name": "Jasa Marga", "sector": "Infrastructure"},
  {"ticker": "WIKA", "name": "Wijaya Karya", "sector": "Construction"},
  {"ticker": "WSKT", "name": "Waskita Karya", "sector": "Construction"},
  {"ticker": "WTON", "name": "Wijaya Karya Beton Precast", "sector": "Construction"},
  {"ticker": "INTP", "name": "Indocement Tunggal Prakarsa", "sector": "Construction Materials"},
  {"ticker": "SMGR", "name": "Semen Indonesia", "sector": "Construction Materials"},
  {"ticker": "TPIA", "name": "Chandra Asri Pacific", "sector": "Chemical"},
  {"ticker": "BRPT", "name": "Barito Pacific", "sector": "Chemical"},
  {"ticker": "INKP", "name": "Indah Kiat Pulp & Paper", "sector": "Paper"},
  {"ticker": "TKIM", "name": "Pabrik Kertas Tjiwi Kimia", "sector": "Paper"},
  {"ticker": "AKRA", "name": "AKR Corporindo", "sector": "Trade"},
  {"ticker": "MNCN", "name": "Media Nusantara Citra", "sector": "Media"},
  {"ticker": "AALI", "name": "Astra Agro Lestari", "sector": "Plantation"},
  {"ticker": "LSIP", "name": "PP London Sumatra Indonesia", "sector": "Plantation"}
]
```

- [ ] **Step 3.2: Verify count**

```bash
python -c "import json; d=json.load(open('data/idx80.json')); print(len(d), 'stocks')"
```

Expected: `80 stocks`

---

### Task 4: Data Fetcher Service

**Files:**
- Create: `backend/services/data_fetcher.py`
- Create: `backend/tests/test_data_fetcher.py`

- [ ] **Step 4.1: Write failing tests**

`backend/tests/test_data_fetcher.py`:
```python
import pytest
import pandas as pd
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
import models
from services.data_fetcher import load_idx80, seed_stocks, fetch_ohlcv, save_ohlcv

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

def _mock_df(days=5):
    idx = pd.date_range(end=date.today(), periods=days, freq="B")
    return pd.DataFrame({
        "Open": [9000.0] * days, "High": [9100.0] * days,
        "Low": [8900.0] * days, "Close": [9050.0] * days,
        "Volume": [10_000_000] * days,
    }, index=idx)

def test_load_idx80_returns_80_stocks():
    stocks = load_idx80()
    assert len(stocks) == 80
    assert all("ticker" in s and "name" in s and "sector" in s for s in stocks)

def test_seed_stocks_inserts_all(db):
    seed_stocks(db)
    assert db.query(models.Stock).count() == 80

def test_seed_stocks_idempotent(db):
    seed_stocks(db)
    seed_stocks(db)
    assert db.query(models.Stock).count() == 80

def test_fetch_ohlcv_appends_jk_suffix(mocker):
    mock = mocker.patch("services.data_fetcher.yf.download", return_value=_mock_df())
    fetch_ohlcv("BBCA")
    args, kwargs = mock.call_args
    assert args[0] == "BBCA.JK"

def test_save_ohlcv_persists_rows(db):
    stock = models.Stock(ticker="BBCA", name="Bank Central Asia", sector="Finance", market_cap_cat="large")
    db.add(stock); db.commit()
    count = save_ohlcv(db, stock, _mock_df(days=5))
    assert count == 5
    assert db.query(models.OHLCVDaily).count() == 5

def test_save_ohlcv_skips_duplicates(db):
    stock = models.Stock(ticker="BBCA", name="Bank Central Asia", sector="Finance", market_cap_cat="large")
    db.add(stock); db.commit()
    df = _mock_df(days=5)
    save_ohlcv(db, stock, df)
    count2 = save_ohlcv(db, stock, df)
    assert count2 == 0
    assert db.query(models.OHLCVDaily).count() == 5
```

- [ ] **Step 4.2: Run test to confirm failure**

```bash
pytest tests/test_data_fetcher.py -v
```

Expected: `ModuleNotFoundError: No module named 'services.data_fetcher'`

- [ ] **Step 4.3: Write services/data_fetcher.py**

`backend/services/data_fetcher.py`:
```python
import os
import json
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

import models

def load_idx80() -> list[dict]:
    path = os.path.join(os.path.dirname(__file__), "../data/idx80.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def seed_stocks(db: Session) -> None:
    existing = {s.ticker for s in db.query(models.Stock).all()}
    new = [
        models.Stock(ticker=s["ticker"], name=s["name"], sector=s["sector"], market_cap_cat="large")
        for s in load_idx80() if s["ticker"] not in existing
    ]
    if new:
        db.add_all(new)
        db.commit()

def fetch_ohlcv(ticker: str, days: int = 365 * 5) -> pd.DataFrame:
    end = date.today()
    start = end - timedelta(days=days)
    df = yf.download(f"{ticker}.JK", start=start, end=end, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def save_ohlcv(db: Session, stock: models.Stock, df: pd.DataFrame) -> int:
    existing = {
        r.date for r in
        db.query(models.OHLCVDaily.date).filter(models.OHLCVDaily.stock_id == stock.id)
    }
    rows = []
    for ts, row in df.iterrows():
        d = ts.date() if hasattr(ts, "date") else ts
        if d in existing:
            continue
        rows.append(models.OHLCVDaily(
            stock_id=stock.id, date=d,
            open=float(row.get("Open") or 0),
            high=float(row.get("High") or 0),
            low=float(row.get("Low") or 0),
            close=float(row.get("Close") or 0),
            volume=int(row.get("Volume") or 0),
            adj_close=float(row.get("Adj Close") or row.get("Close") or 0),
        ))
    if rows:
        db.bulk_save_objects(rows)
        db.commit()
    return len(rows)
```

- [ ] **Step 4.4: Run tests to confirm pass**

```bash
pytest tests/test_data_fetcher.py -v
```

Expected: All 6 tests `PASSED`

---

### Task 5: Indicators Service

**Files:**
- Create: `backend/services/indicators.py`
- Create: `backend/tests/test_indicators.py`

- [ ] **Step 5.1: Write failing tests**

`backend/tests/test_indicators.py`:
```python
import random
import pytest
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
import models
from services.indicators import calculate_indicators, get_ohlcv_df

@pytest.fixture
def db_with_data():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    stock = models.Stock(ticker="BBCA", name="Bank Central Asia", sector="Finance", market_cap_cat="large")
    session.add(stock); session.commit()
    random.seed(42)
    price, current, rows, count = 9000.0, date(2023, 1, 2), [], 0
    while count < 300:
        if current.weekday() < 5:
            price *= 1 + random.uniform(-0.015, 0.015)
            rows.append(models.OHLCVDaily(
                stock_id=stock.id, date=current,
                open=round(price * 0.995, 0), high=round(price * 1.01, 0),
                low=round(price * 0.985, 0), close=round(price, 0),
                volume=random.randint(5_000_000, 20_000_000), adj_close=round(price, 0)
            ))
            count += 1
        current += timedelta(days=1)
    session.bulk_save_objects(rows); session.commit()
    yield session, stock
    session.close(); Base.metadata.drop_all(bind=engine)

def test_get_ohlcv_df_shape(db_with_data):
    session, stock = db_with_data
    df = get_ohlcv_df(session, stock.id)
    assert len(df) == 300
    assert all(c in df.columns for c in ["open", "high", "low", "close", "volume"])

def test_calculate_indicators_has_all_keys(db_with_data):
    session, stock = db_with_data
    result = calculate_indicators(session, stock)
    for key in ["MA_20", "MA_50", "MA_200", "EMA_12", "EMA_26", "RSI_14", "ATR_14",
                "VOLUME_MA_20", "MACD_LINE", "MACD_SIGNAL", "MACD_HIST",
                "BB_UPPER", "BB_MIDDLE", "BB_LOWER", "STOCH_K", "STOCH_D"]:
        assert key in result, f"Missing: {key}"

def test_rsi_in_valid_range(db_with_data):
    session, stock = db_with_data
    rsi = calculate_indicators(session, stock).get("RSI_14")
    assert rsi is not None and 0 <= rsi <= 100

def test_empty_data_returns_empty_dict():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    stock = models.Stock(ticker="X", name="X", sector="X", market_cap_cat="large")
    session.add(stock); session.commit()
    assert calculate_indicators(session, stock) == {}
    session.close()
```

- [ ] **Step 5.2: Run test to confirm failure**

```bash
pytest tests/test_indicators.py -v
```

Expected: `ModuleNotFoundError: No module named 'services.indicators'`

- [ ] **Step 5.3: Write services/indicators.py**

`backend/services/indicators.py`:
```python
import pandas as pd
import ta as ta_lib
from sqlalchemy.orm import Session
import models

def get_ohlcv_df(db: Session, stock_id: int) -> pd.DataFrame:
    rows = (
        db.query(models.OHLCVDaily)
        .filter(models.OHLCVDaily.stock_id == stock_id)
        .order_by(models.OHLCVDaily.date)
        .all()
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([{
        "date": r.date, "open": r.open, "high": r.high,
        "low": r.low, "close": r.close, "volume": float(r.volume or 0)
    } for r in rows]).set_index("date")
    return df

def _last(series):
    if series is None:
        return None
    s = series.dropna()
    return round(float(s.iloc[-1]), 4) if not s.empty else None

def calculate_indicators(db: Session, stock: models.Stock) -> dict:
    df = get_ohlcv_df(db, stock.id)
    if df.empty:
        return {}

    close, high, low, volume = df["close"], df["high"], df["low"], df["volume"]
    r: dict = {}

    r["MA_20"] = _last(ta_lib.trend.SMAIndicator(close=close, window=20).sma_indicator())
    r["MA_50"] = _last(ta_lib.trend.SMAIndicator(close=close, window=50).sma_indicator())
    r["MA_200"] = _last(ta_lib.trend.SMAIndicator(close=close, window=200).sma_indicator())
    r["EMA_12"] = _last(ta_lib.trend.EMAIndicator(close=close, window=12).ema_indicator())
    r["EMA_26"] = _last(ta_lib.trend.EMAIndicator(close=close, window=26).ema_indicator())
    r["RSI_14"] = _last(ta_lib.momentum.RSIIndicator(close=close, window=14).rsi())
    r["ATR_14"] = _last(ta_lib.volatility.AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range())
    r["VOLUME_MA_20"] = _last(ta_lib.trend.SMAIndicator(close=volume, window=20).sma_indicator())

    macd = ta_lib.trend.MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    r["MACD_LINE"] = _last(macd.macd())
    r["MACD_SIGNAL"] = _last(macd.macd_signal())
    r["MACD_HIST"] = _last(macd.macd_diff())

    bb = ta_lib.volatility.BollingerBands(close=close, window=20, window_dev=2)
    r["BB_UPPER"] = _last(bb.bollinger_hband())
    r["BB_MIDDLE"] = _last(bb.bollinger_mavg())
    r["BB_LOWER"] = _last(bb.bollinger_lband())

    stoch = ta_lib.momentum.StochasticOscillator(high=high, low=low, close=close, window=14, smooth_window=3)
    r["STOCH_K"] = _last(stoch.stoch())
    r["STOCH_D"] = _last(stoch.stoch_signal())

    return r
```

- [ ] **Step 5.4: Run tests to confirm pass**

```bash
pytest tests/test_indicators.py -v
```

Expected: All 4 tests `PASSED`

---

### Task 6: Stocks Router + main.py

**Files:**
- Create: `backend/main.py`
- Create: `backend/routers/stocks.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_stocks_router.py`

- [ ] **Step 6.1: Write conftest.py**

`backend/tests/conftest.py`:
```python
import random
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, get_db
from main import app
import models

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=_engine)
    session = _Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=_engine)

@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def stock_bbca(db):
    s = models.Stock(ticker="BBCA", name="Bank Central Asia", sector="Finance", market_cap_cat="large")
    db.add(s); db.commit(); db.refresh(s)
    return s

@pytest.fixture
def ohlcv_300(db, stock_bbca):
    random.seed(99)
    price, current, rows, count = 9000.0, date(2023, 1, 2), [], 0
    while count < 300:
        if current.weekday() < 5:
            price *= 1 + random.uniform(-0.015, 0.015)
            rows.append(models.OHLCVDaily(
                stock_id=stock_bbca.id, date=current,
                open=round(price * 0.995, 0), high=round(price * 1.01, 0),
                low=round(price * 0.985, 0), close=round(price, 0),
                volume=random.randint(5_000_000, 20_000_000), adj_close=round(price, 0)
            ))
            count += 1
        current += timedelta(days=1)
    db.bulk_save_objects(rows); db.commit()
```

- [ ] **Step 6.2: Write failing tests**

`backend/tests/test_stocks_router.py`:
```python
import pandas as pd
import pytest

def test_list_stocks_empty(client):
    r = client.get("/stocks")
    assert r.status_code == 200
    assert r.json() == []

def test_list_stocks_returns_stock(client, stock_bbca):
    r = client.get("/stocks")
    data = r.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "BBCA"

def test_list_stocks_has_last_price(client, stock_bbca, ohlcv_300):
    r = client.get("/stocks")
    assert r.json()[0]["last_price"] is not None

def test_get_ohlcv_not_found(client):
    assert client.get("/stocks/INVALID/ohlcv").status_code == 404

def test_get_ohlcv_returns_300_rows(client, stock_bbca, ohlcv_300):
    r = client.get("/stocks/BBCA/ohlcv")
    assert r.status_code == 200
    data = r.json()
    assert data["ticker"] == "BBCA"
    assert len(data["data"]) == 300
    assert all(k in data["data"][0] for k in ["date", "open", "high", "low", "close", "volume"])

def test_get_ohlcv_date_filter(client, stock_bbca, ohlcv_300):
    r = client.get("/stocks/BBCA/ohlcv?from=2023-06-01&to=2023-08-31")
    assert r.status_code == 200
    for row in r.json()["data"]:
        assert "2023-06-01" <= row["date"] <= "2023-08-31"

def test_get_ohlcv_case_insensitive(client, stock_bbca, ohlcv_300):
    assert client.get("/stocks/bbca/ohlcv").status_code == 200

def test_get_indicators_not_found(client):
    assert client.get("/stocks/INVALID/indicators").status_code == 404

def test_get_indicators_returns_values(client, stock_bbca, ohlcv_300):
    r = client.get("/stocks/BBCA/indicators")
    assert r.status_code == 200
    ind = r.json()["indicators"]
    assert "RSI_14" in ind and "MA_20" in ind and "MACD_LINE" in ind

def test_refresh_stock_not_found(client):
    assert client.post("/stocks/INVALID/refresh").status_code == 404

def test_refresh_single_stock(client, stock_bbca, mocker):
    mock_df = pd.DataFrame({
        "Open": [9000.0], "High": [9100.0], "Low": [8900.0],
        "Close": [9050.0], "Volume": [10_000_000],
    }, index=pd.date_range("2024-01-02", periods=1))
    mocker.patch("services.data_fetcher.yf.download", return_value=mock_df)
    r = client.post("/stocks/BBCA/refresh")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["new_rows"] == 1
```

- [ ] **Step 6.3: Run test to confirm failure**

```bash
pytest tests/test_stocks_router.py -v
```

Expected: `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 6.4: Write main.py**

`backend/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine
import models  # noqa: F401

Base.metadata.create_all(bind=engine)

app = FastAPI(title="IDXAnalyst API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers.stocks import router as stocks_router  # noqa: E402
app.include_router(stocks_router)
```

- [ ] **Step 6.5: Write routers/stocks.py**

`backend/routers/stocks.py`:
```python
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import models
import services.data_fetcher as fetcher
import services.indicators as ind_svc
from database import get_db

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("")
def list_stocks(db: Session = Depends(get_db)):
    stocks = db.query(models.Stock).order_by(models.Stock.ticker).all()
    result = []
    for stock in stocks:
        latest = (
            db.query(models.OHLCVDaily)
            .filter(models.OHLCVDaily.stock_id == stock.id)
            .order_by(models.OHLCVDaily.date.desc())
            .first()
        )
        result.append({
            "ticker": stock.ticker,
            "name": stock.name,
            "sector": stock.sector,
            "last_price": latest.close if latest else None,
            "last_date": str(latest.date) if latest else None,
        })
    return result


@router.get("/{ticker}/ohlcv")
def get_ohlcv(
    ticker: str,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    stock = db.query(models.Stock).filter(
        models.Stock.ticker == ticker.upper()
    ).first()
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
        "data": [
            {"date": str(r.date), "open": r.open, "high": r.high,
             "low": r.low, "close": r.close, "volume": r.volume}
            for r in rows
        ],
    }


@router.get("/{ticker}/indicators")
def get_indicators(ticker: str, db: Session = Depends(get_db)):
    stock = db.query(models.Stock).filter(
        models.Stock.ticker == ticker.upper()
    ).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker.upper()} not found")
    return {"ticker": stock.ticker, "indicators": ind_svc.calculate_indicators(db, stock)}


# /refresh must be registered before /{ticker}/refresh to avoid route collision
@router.post("/refresh")
def refresh_all(db: Session = Depends(get_db)):
    fetcher.seed_stocks(db)
    results = {}
    for stock in db.query(models.Stock).all():
        try:
            df = fetcher.fetch_ohlcv(stock.ticker)
            count = fetcher.save_ohlcv(db, stock, df)
            results[stock.ticker] = {"status": "ok", "new_rows": count}
        except Exception as e:
            results[stock.ticker] = {"status": "error", "error": str(e)}
    return results


@router.post("/{ticker}/refresh")
def refresh_stock(ticker: str, db: Session = Depends(get_db)):
    stock = db.query(models.Stock).filter(
        models.Stock.ticker == ticker.upper()
    ).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker.upper()} not found")
    try:
        df = fetcher.fetch_ohlcv(stock.ticker)
        count = fetcher.save_ohlcv(db, stock, df)
        return {"ticker": stock.ticker, "status": "ok", "new_rows": count}
    except Exception as e:
        return {"ticker": stock.ticker, "status": "error", "error": str(e)}
```

- [ ] **Step 6.6: Run all tests**

```bash
pytest tests/ -v --tb=short
```

Expected: All tests `PASSED` (17+ tests across 4 files)

---

### Task 7: Startup Verification & Initial Data Seed

**Files:** None (verification only)

- [ ] **Step 7.1: Copy .env**

```bash
cp .env.example .env
```

- [ ] **Step 7.2: Start server**

```bash
uvicorn main:app --reload --port 8000
```

Expected: `Application startup complete` with no errors.

- [ ] **Step 7.3: Seed all IDX80 stocks and fetch 5-year history**

```bash
curl -X POST http://localhost:8000/stocks/refresh
```

> This makes 80 API calls to yfinance. Takes **5–15 minutes**. Already-saved rows are skipped on re-run if interrupted.

- [ ] **Step 7.4: Verify data**

```bash
curl http://localhost:8000/stocks | python -m json.tool | head -40
curl "http://localhost:8000/stocks/BBCA/ohlcv?from=2024-01-01" | python -m json.tool | head -30
curl http://localhost:8000/stocks/BBCA/indicators | python -m json.tool
```

Expected: `/stocks` returns 80 entries with `last_price` populated. `/ohlcv` returns daily candles. `/indicators` returns all 16 indicator values.

---

Phase 1 complete. FastAPI backend is running with SQLite, all 80 IDX80 stocks seeded, OHLCV data loaded, and indicators working.

**Next phase:** `docs/superpowers/plans/2026-04-26-phase2-frontend.md` — Next.js + TradingView Lightweight Charts.
