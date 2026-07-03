"""Parameter risiko adaptif AI Porto — semua angka terpusat & tunable.

Rezim ditentukan dari return vs modal & drawdown dari puncak equity:
  DEFENSIVE  bila return <= DEF_RETURN  ATAU drawdown >= DEF_MAX_DD
  AGGRESSIVE bila return >= AGG_RETURN  DAN  drawdown <  AGG_MAX_DD
  NORMAL     selain itu
"""
import os

MAX_ORDERS = 10  # batas order LLM yang dieksekusi per perintah

# Reasoning effort untuk panggilan "buat rencana trade".
# WAJIB rendah: payload AI Porto besar (holdings + belasan kandidat) dan output
# terstruktur besar (array order). Diukur pada gpt-oss-120b: effort "high"
# menghabiskan seluruh anggaran token utk reasoning lalu mengembalikan OUTPUT
# KOSONG (json_validate_failed) -> "AI sedang sibuk"; "medium" ~40s (lambat);
# "low" ~1.7s dengan rencana valid. Reasoning berat tak perlu di sini — scoring
# kandidat & guardrail risiko semuanya sudah dihitung oleh kode.
PLAN_EFFORT = os.getenv("AIPORTO_PLAN_EFFORT", "low")

# Pemicu rezim (fraksi, bukan persen)
AGG_RETURN = 0.08   # cuan >= +8%
AGG_MAX_DD = 0.05   # dan drawdown < 5%
DEF_RETURN = -0.03  # rugi <= -3%
DEF_MAX_DD = 0.10   # atau drawdown >= 10%

# Guardrail per rezim. Semua pct sebagai fraksi (0.35 = 35%).
REGIMES = {
    "AGGRESSIVE": {
        "max_position_pct": 0.35,  # nilai maks 1 saham thd total equity
        "max_deploy_pct":   1.00,  # maks porsi equity yang diinvestasikan
        "max_positions":    6,
        "take_profit":      0.20,  # auto jual bila untung >= +20%
        "cut_loss":         0.10,  # auto jual bila rugi <= -10%
    },
    "NORMAL": {
        "max_position_pct": 0.22,
        "max_deploy_pct":   0.85,
        "max_positions":    8,
        "take_profit":      0.15,
        "cut_loss":         0.08,
    },
    "DEFENSIVE": {
        "max_position_pct": 0.12,
        "max_deploy_pct":   0.55,
        "max_positions":    6,
        "take_profit":      0.10,
        "cut_loss":         0.06,
    },
}
