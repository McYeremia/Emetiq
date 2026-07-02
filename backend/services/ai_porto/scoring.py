"""Skor kandidat deterministik (0-100) — 'otak kuant' AI Porto.

Menggabungkan sinyal watcher (berbasis strategi backtest), tren, RSI, dan valuasi.
Murni fungsi angka -> mudah diuji, tidak memanggil LLM.
"""
from typing import Any, Dict


def score_candidate(c: Dict[str, Any]) -> float:
    """Skor 0-100 untuk satu kandidat. Makin tinggi makin menarik untuk BELI."""
    s = 50.0

    # Kekuatan sinyal watcher (0-100) — bobot terbesar (berbasis backtest)
    sig = c.get("signal_strength")
    if sig:
        s += min(float(sig), 100.0) * 0.30  # hingga +30

    # Tren: harga di atas MA50 = uptrend
    trend = c.get("trend")
    if trend == "up":
        s += 12
    elif trend == "down":
        s -= 8

    # RSI: oversold = potensi rebound; overbought = hindari
    rsi = c.get("rsi")
    if rsi is not None:
        if rsi < 30:
            s += 10
        elif rsi > 72:
            s -= 12
        elif 45 <= rsi <= 60:
            s += 6

    # Valuasi ringan
    pe = c.get("pe")
    if pe and 0 < pe < 12:
        s += 6
    dy = c.get("dividend_yield")
    if dy and dy >= 3:
        s += 4

    return max(0.0, min(100.0, round(s, 1)))
