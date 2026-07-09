"""Konfigurasi AI Advisor — semua angka/model ID terpusat di sini agar mudah diganti.

Groq sering men-deprecate model, jadi ID model sengaja dibuat 1 baris ubah
(dan bisa di-override lewat environment variable).
"""
import os

# ── Model Groq ──────────────────────────────────────────────────────────────
# Router & tugas ringan pakai model kecil; sintesis/kritik pakai model reasoning.
ROUTER_MODEL    = os.getenv("ADVISOR_ROUTER_MODEL", "openai/gpt-oss-20b")
REASONING_MODEL = os.getenv("ADVISOR_REASONING_MODEL", "openai/gpt-oss-120b")

# ── Reasoning effort per stage ───────────────────────────────────────────────
# Effort tinggi = banyak token nalar. Di Groq free tier (8k TPM), token nalar itu
# ikut dihitung ke keluaran DAN ke kuota per menit, jadi "high" gampang menembus
# limit -> 413 "request too large". Turunkan ke medium/low: cukup untuk menalar di
# atas angka yang sudah pasti, hemat token, dan JSON tak terpotong.
REASONING_EFFORT = {
    "router":     "low",
    "specialist": "low",
    "synthesis":  "medium",
    "critique":   "medium",
    "rank":       "low",
}

# Batas token keluaran per panggilan. PENTING: Groq me-reserve `max_completion_tokens`
# ke kuota tokens-per-minute (TPM) SETIAP request. Free tier gpt-oss = 8000 TPM, jadi
# nilai >= 8000 (dulu 8192) membuat SETIAP panggilan reasoning kena 413
# `rate_limit_exceeded` ("Request too large ... TPM: Limit 8000, Requested >8000")
# sebelum 1 token input pun dihitung -> user lihat "AI sedang sibuk" terus.
# 4096 memberi headroom ~3900 token untuk prompt input di bawah plafon 8000.
MAX_COMPLETION_TOKENS = int(os.getenv("ADVISOR_MAX_COMPLETION_TOKENS", "4096"))

# ── Kuota harian per tier (reset tengah malam). None = unlimited. ────────────
TIER_LIMITS = {
    "free":    1,
    "basic":   3,
    "pro":     5,
    "premium": 10,
    "dev":     None,
}

# ── Tuning panggilan Groq ────────────────────────────────────────────────────
# Diturunkan dari 30s/2 retry: worst-case 1 panggilan dulu bisa ~122s (json-mode +
# 3x fallback teks @30s + backoff), dan 1 stage pipeline (initial+repair) sampai
# ~244s — makanya user lihat "AI sedang sibuk" setelah menunggu lama. Nilai baru
# menekan worst-case per panggilan ke ~41s agar gagal cepat, bukan menumpuk retry.
REQUEST_TIMEOUT = float(os.getenv("ADVISOR_TIMEOUT", "20"))      # detik per panggilan
MAX_RETRIES     = int(os.getenv("ADVISOR_MAX_RETRIES", "1"))     # retry saat 5xx/timeout
RETRY_BACKOFF   = float(os.getenv("ADVISOR_RETRY_BACKOFF", "0.8"))  # detik, dikali eksponensial

# Anggaran waktu total 1 pipeline (router + semua stage). Begitu terlampaui, stage
# berikutnya dilewati (langsung fallback) alih-alih menambah panggilan Groq baru —
# membatasi ekor terburuk (worst-case) tanpa mengubah perilaku jalur normal/cepat.
PIPELINE_BUDGET_SECONDS = float(os.getenv("ADVISOR_PIPELINE_BUDGET", "55"))

# ── Batas pipeline ───────────────────────────────────────────────────────────
# Screening: hanya N kandidat teratas (lolos filter keras) yang dihitung indikator
# penuh & diberi ke LLM untuk ranking — hemat CPU & token.
SCREEN_MAX_CANDIDATES = int(os.getenv("ADVISOR_SCREEN_MAX", "40"))
# Berapa banyak saham yang DITAMPILKAN ke user bila ia tidak menyebut jumlah.
# (Ranking tetap memakai pool lebar di atas; ini hanya batas hasil akhir.)
SCREEN_DEFAULT_COUNT = int(os.getenv("ADVISOR_SCREEN_DEFAULT_COUNT", "5"))
# Batas ATAS jumlah saham yang diberikan, berapa pun yang diminta user — jaga hasil tetap
# ringkas & fokus (mis. minta 10 -> tetap 5 terbaik).
SCREEN_MAX_COUNT = int(os.getenv("ADVISOR_SCREEN_MAX_COUNT", "5"))
# Berapa banyak kandidat (teratas per kapitalisasi) yang benar-benar dikirim ke LLM
# untuk di-ranking. Jauh lebih kecil dari SCREEN_MAX_CANDIDATES agar keluaran ringkas
# (LLM hanya perlu memilih beberapa terbaik, bukan menilai 40 saham satu per satu).
SCREEN_RANK_POOL = int(os.getenv("ADVISOR_SCREEN_RANK_POOL", "15"))
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
