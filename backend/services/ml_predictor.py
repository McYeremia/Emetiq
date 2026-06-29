"""
ML Price Prediction Service — IDXAnalyst Phase 6
Model: GradientBoostingClassifier (sklearn)
Target: Apakah harga naik >1% dalam 5 hari ke depan?
"""
import os
import json
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
import ta as ta_lib
from sqlalchemy.orm import Session

import models
from services.indicators import get_ohlcv_df

# Direktori penyimpanan model, relatif terhadap file ini
_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml_models")

FEATURE_LABELS = {
    "rsi":            "RSI (14)",
    "macd_hist":      "MACD Histogram",
    "macd_line":      "MACD Line",
    "bb_position":    "Bollinger Position",
    "ma20_ratio":     "Jarak MA20",
    "ma50_ratio":     "Jarak MA50",
    "stoch_k":        "Stochastic %K",
    "stoch_d":        "Stochastic %D",
    "vol_ratio":      "Volume Ratio",
    "ret_1d":         "Return 1 Hari",
    "ret_3d":         "Return 3 Hari",
    "ret_5d":         "Return 5 Hari",
    "ret_10d":        "Return 10 Hari",
    "ret_20d":        "Return 20 Hari",
    "vol_10d":        "Volatilitas 10H",
    "atr_ratio":      "ATR Ratio",
    "pe_ratio":       "P/E Ratio",
    "pbv_ratio":      "P/B Ratio",
    "dividend_yield": "Dividend Yield",
}


def _model_path(ticker: str) -> str:
    return os.path.join(_MODEL_DIR, f"{ticker}.pkl")


def _meta_path(ticker: str) -> str:
    return os.path.join(_MODEL_DIR, f"{ticker}_meta.json")


def _ensure_model_dir():
    os.makedirs(_MODEL_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Feature Engineering
# ---------------------------------------------------------------------------

def build_features(df: pd.DataFrame, stock=None) -> pd.DataFrame:
    """Bangun feature matrix dari OHLCV. Hasilnya satu baris per hari."""
    close  = df["close"]
    high   = df["high"]
    low    = df["low"]
    volume = df["volume"]

    feat = pd.DataFrame(index=df.index)

    # --- Oscillators ---
    feat["rsi"] = ta_lib.momentum.RSIIndicator(close=close, window=14).rsi()

    macd = ta_lib.trend.MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    feat["macd_hist"] = macd.macd_diff()
    feat["macd_line"] = macd.macd()

    stoch = ta_lib.momentum.StochasticOscillator(high=high, low=low, close=close, window=14, smooth_window=3)
    feat["stoch_k"] = stoch.stoch()
    feat["stoch_d"] = stoch.stoch_signal()

    # --- Bollinger Bands position (0 = di BB low, 1 = di BB high) ---
    bb       = ta_lib.volatility.BollingerBands(close=close, window=20, window_dev=2)
    bb_upper = bb.bollinger_hband()
    bb_lower = bb.bollinger_lband()
    feat["bb_position"] = (close - bb_lower) / (bb_upper - bb_lower + 1e-9)

    # --- MA distance (% dari harga) ---
    ma20 = ta_lib.trend.SMAIndicator(close=close, window=20).sma_indicator()
    ma50 = ta_lib.trend.SMAIndicator(close=close, window=50).sma_indicator()
    feat["ma20_ratio"] = (close / (ma20 + 1e-9)) - 1
    feat["ma50_ratio"] = (close / (ma50 + 1e-9)) - 1

    # --- Volume ratio (volume hari ini vs rata-rata 20 hari) ---
    vol_ma20 = ta_lib.trend.SMAIndicator(close=volume, window=20).sma_indicator()
    feat["vol_ratio"] = volume / (vol_ma20 + 1e-9)

    # --- Lag returns ---
    for n in [1, 3, 5, 10, 20]:
        feat[f"ret_{n}d"] = close.pct_change(n)

    # --- Volatilitas & ATR ---
    daily_ret       = close.pct_change()
    feat["vol_10d"] = daily_ret.rolling(10).std()

    atr              = ta_lib.volatility.AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range()
    feat["atr_ratio"] = atr / (close + 1e-9)

    # --- Fundamental (konstanta per saham) ---
    if stock is not None:
        feat["pe_ratio"]       = float(stock.pe_ratio or 15.0)
        feat["pbv_ratio"]      = float(stock.pbv_ratio or 1.5)
        feat["dividend_yield"] = float(stock.dividend_yield or 0.0)

    return feat


def build_target(df: pd.DataFrame, horizon: int = 5, threshold: float = 0.01) -> pd.Series:
    """Binary: 1 jika harga naik >threshold% dalam horizon hari ke depan."""
    future_ret = df["close"].shift(-horizon) / df["close"] - 1
    return (future_ret > threshold).astype(int)


# ---------------------------------------------------------------------------
# Train
# ---------------------------------------------------------------------------

def train_model(ticker: str, db: Session) -> dict:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import accuracy_score, roc_auc_score

    _ensure_model_dir()

    stock = db.query(models.Stock).filter(models.Stock.ticker == ticker.upper()).first()
    if not stock:
        return {"status": "error", "message": f"Saham {ticker} tidak ditemukan"}

    df = get_ohlcv_df(db, stock.id)
    if len(df) < 150:
        return {"status": "error", "message": f"Data tidak cukup — dibutuhkan minimal 150 bar, tersedia {len(df)}"}

    X = build_features(df, stock)
    y = build_target(df, horizon=5, threshold=0.01)

    # Gabung dan buang NaN; hilangkan 5 baris terakhir (future unknown)
    combined = pd.concat([X, y.rename("target")], axis=1).dropna().iloc[:-5]
    if len(combined) < 100:
        return {"status": "error", "message": "Setelah preprocessing data terlalu sedikit (<100 sampel)"}

    X_clean = combined.drop("target", axis=1)
    y_clean = combined["target"]

    # Train / test split temporal (80/20)
    split    = int(len(X_clean) * 0.8)
    X_train, X_test = X_clean.iloc[:split], X_clean.iloc[split:]
    y_train, y_test = y_clean.iloc[:split], y_clean.iloc[split:]

    model = GradientBoostingClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, min_samples_leaf=10, random_state=42
    )
    model.fit(X_train, y_train)

    y_pred  = model.predict(X_test)
    y_prob  = model.predict_proba(X_test)[:, 1]
    acc     = float(accuracy_score(y_test, y_pred))
    try:
        auc = float(roc_auc_score(y_test, y_prob))
    except Exception:
        auc = 0.5

    # Simpan model
    joblib.dump(model, _model_path(ticker))

    # Simpan metadata
    importance = {
        FEATURE_LABELS.get(k, k): round(float(v), 5)
        for k, v in zip(X_clean.columns, model.feature_importances_)
    }
    meta = {
        "ticker":         ticker.upper(),
        "trained_at":     datetime.now().isoformat(),
        "samples_train":  int(len(X_train)),
        "samples_test":   int(len(X_test)),
        "accuracy":       round(acc, 4),
        "auc":            round(auc, 4),
        "feature_importance": importance,
        "class_balance":  {
            "pct_up":   round(float(y_clean.mean()), 4),
            "pct_down": round(1 - float(y_clean.mean()), 4),
        },
    }
    with open(_meta_path(ticker), "w") as f:
        json.dump(meta, f, indent=2)

    return {"status": "trained", **meta}


# ---------------------------------------------------------------------------
# Predict
# ---------------------------------------------------------------------------

def predict(ticker: str, db: Session) -> dict:
    mp = _model_path(ticker)
    if not os.path.exists(mp):
        return {
            "status": "not_trained",
            "message": "Model belum dilatih. Klik tombol TRAIN terlebih dahulu.",
        }

    model = joblib.load(mp)

    # Load metadata (accuracy, trained_at, dll)
    meta = {}
    if os.path.exists(_meta_path(ticker)):
        with open(_meta_path(ticker)) as f:
            meta = json.load(f)

    stock = db.query(models.Stock).filter(models.Stock.ticker == ticker.upper()).first()
    if not stock:
        return {"status": "error", "message": f"Saham {ticker} tidak ditemukan"}

    df = get_ohlcv_df(db, stock.id)
    if len(df) < 60:
        return {"status": "error", "message": "Data tidak cukup untuk prediksi"}

    X = build_features(df, stock)

    # Ambil baris terakhir yang tidak NaN
    latest = X.dropna()
    if latest.empty:
        return {"status": "error", "message": "Tidak bisa menghitung features dari data terbaru"}
    latest = latest.iloc[[-1]]

    # Pastikan kolom sama dengan saat training
    try:
        proba = model.predict_proba(latest)[0]
    except Exception as e:
        return {"status": "error", "message": f"Prediksi gagal: {e}"}

    prob_up   = float(proba[1])
    prob_down = float(proba[0])

    # Klasifikasi arah
    if prob_up >= 0.60:
        direction      = "BULLISH"
        recommendation = "BUY"
        dir_color      = "green"
    elif prob_up <= 0.40:
        direction      = "BEARISH"
        recommendation = "WAIT"
        dir_color      = "red"
    else:
        direction      = "NEUTRAL"
        recommendation = "HOLD"
        dir_color      = "yellow"

    # Confidence: seberapa jauh dari 50% (0–100)
    confidence = round(abs(prob_up - 0.5) * 200, 1)

    # Top 5 feature importance (human-readable)
    raw_imp    = dict(zip(model.feature_names_in_, model.feature_importances_))
    top_feats  = sorted(
        [{"name": FEATURE_LABELS.get(k, k), "importance": round(float(v), 4)}
         for k, v in raw_imp.items()],
        key=lambda x: x["importance"], reverse=True
    )[:5]

    return {
        "status":          "ok",
        "ticker":          ticker.upper(),
        "direction":       direction,
        "dir_color":       dir_color,
        "recommendation":  recommendation,
        "probability_up":  round(prob_up, 4),
        "probability_down": round(prob_down, 4),
        "confidence":      confidence,
        "horizon_days":    5,
        "top_features":    top_feats,
        "model_accuracy":  meta.get("accuracy"),
        "model_auc":       meta.get("auc"),
        "trained_at":      meta.get("trained_at"),
        "samples_train":   meta.get("samples_train"),
    }


def get_model_status(ticker: str) -> dict:
    """Cek apakah model sudah ada dan kapan di-train."""
    if not os.path.exists(_model_path(ticker)):
        return {"trained": False}
    meta = {}
    if os.path.exists(_meta_path(ticker)):
        with open(_meta_path(ticker)) as f:
            meta = json.load(f)
    return {
        "trained":    True,
        "trained_at": meta.get("trained_at"),
        "accuracy":   meta.get("accuracy"),
        "auc":        meta.get("auc"),
    }
