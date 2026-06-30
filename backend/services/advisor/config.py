"""Konfigurasi AI Advisor — semua angka/model ID terpusat di sini agar mudah diganti.

Groq sering men-deprecate model, jadi ID model sengaja dibuat 1 baris ubah
(dan bisa di-override lewat environment variable).
"""
import os

# ── Model Groq ──────────────────────────────────────────────────────────────
# Router & tugas ringan pakai model kecil; sintesis/kritik pakai model reasoning.
ROUTER_MODEL    = os.getenv("ADVISOR_ROUTER_MODEL", "openai/gpt-oss-20b")
REASONING_MODEL = os.getenv("ADVISOR_REASONING_MODEL", "openai/gpt-oss-120b")

# ── Reasoning effort per stage (hemat token: HIGH hanya saat benar-benar perlu) ──
REASONING_EFFORT = {
    "router":     "low",
    "specialist": "low",
    "synthesis":  "high",
    "critique":   "high",
}

# ── Kuota harian per tier (reset tengah malam). None = unlimited. ────────────
TIER_LIMITS = {
    "free":    1,
    "basic":   3,
    "pro":     5,
    "premium": 10,
    "dev":     None,
}

# ── Tuning panggilan Groq ────────────────────────────────────────────────────
REQUEST_TIMEOUT = float(os.getenv("ADVISOR_TIMEOUT", "30"))      # detik per panggilan
MAX_RETRIES     = int(os.getenv("ADVISOR_MAX_RETRIES", "2"))     # retry saat 5xx/timeout
RETRY_BACKOFF   = float(os.getenv("ADVISOR_RETRY_BACKOFF", "0.8"))  # detik, dikali eksponensial

# ── Batas pipeline ───────────────────────────────────────────────────────────
# Screening: hanya N kandidat teratas (lolos filter keras) yang dihitung indikator
# penuh & diberi ke LLM untuk ranking — hemat CPU & token.
SCREEN_MAX_CANDIDATES = int(os.getenv("ADVISOR_SCREEN_MAX", "40"))
# Batas berapa saham (urut market cap desc) yang dihitung indikatornya saat screening,
# agar latency terjaga walau filter fundamental longgar.
SCREEN_WORKING_SET = int(os.getenv("ADVISOR_SCREEN_WORKING_SET", "250"))
# Portofolio: batasi jumlah posisi yang dianalisa per-posisi (stage termahal).
PORTFOLIO_MAX_POSITIONS = int(os.getenv("ADVISOR_PORTFOLIO_MAX", "20"))

# Ringkasan N giliran percakapan terakhir yang dikirim ke router (multi-turn).
HISTORY_TURNS = int(os.getenv("ADVISOR_HISTORY_TURNS", "6"))


def tier_limit(tier: str):
    """Kembalikan batas harian untuk sebuah tier. Tier tak dikenal -> 'free'."""
    return TIER_LIMITS.get((tier or "free").lower(), TIER_LIMITS["free"])
