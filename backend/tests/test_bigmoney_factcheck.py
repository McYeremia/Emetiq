"""Tes agents/factcheck — pemeriksaan klaim yang bisa dihitung, tanpa LLM.

Lahir dari kegagalan nyata: pada 2026-07-10, penulis menuduh WBSA, INET, dan ASPR
"rentan pump-and-dump" padahal flags.pump_dump_risk ketiganya False. Kritikus LLM
yang seharusnya menangkapnya justru diblokir Gemini (finish_reason RECITATION).

Tuduhan manipulasi harga terhadap emiten nyata adalah kesalahan paling berbahaya yang
bisa dibuat produk ini. Pemeriksaannya bisa dirumuskan — jadi harus dirumuskan, bukan
dititipkan ke model yang bisa diblokir.
"""
from services.bigmoney.agents.factcheck import check_claims


def _ctx(picks, total_foreign=-285_000_000_000):
    return {
        "date": "2026-07-10",
        "regime": {"total_foreign_net_value": total_foreign, "weight_set": "VOLATILE"},
        "top_accumulation": picks,
    }


def _pick(ticker, *, pump=False, divergence=False, conviction="WATCH"):
    return {
        "rank": 1, "ticker": ticker, "composite": 80.0, "conviction": conviction,
        "phase": "AKUMULASI", "days_confirmed": 3, "foreign_net_value": 1_000_000_000,
        "flags": {"pump_dump_risk": pump, "divergence": divergence},
    }


def test_flags_false_pump_dump_accusation():
    """Kasus nyata 2026-07-10: WBSA dituduh pump-dump padahal flagnya False."""
    draft = "Investor perlu waspada terhadap WBSA yang rentan risiko pump-and-dump."

    issues = check_claims(draft, _ctx([_pick("WBSA", pump=False)]))

    assert any("WBSA" in i and "pump" in i.lower() for i in issues)


def test_allows_pump_dump_claim_when_flag_is_true():
    draft = "PUMP menyala bendera risiko pump-and-dump."

    assert check_claims(draft, _ctx([_pick("PUMP", pump=True)])) == []


def test_ignores_pump_word_far_from_any_ticker():
    """Pembahasan umum soal pump-and-dump tanpa menuduh emiten tertentu itu sah."""
    draft = "Saham likuiditas rendah secara umum rentan pump-and-dump."

    assert check_claims(draft, _ctx([_pick("WBSA")])) == []


def test_flags_false_divergence_accusation():
    draft = "CUAN menunjukkan divergensi antara harga dan aliran asing."

    issues = check_claims(draft, _ctx([_pick("CUAN", divergence=False)]))

    assert any("CUAN" in i and "divergensi" in i.lower() for i in issues)


def test_flags_false_strong_conviction_claim():
    """Menaikkan WATCH jadi STRONG berarti menjual keyakinan yang tak dimiliki engine."""
    draft = "GOTO masuk kategori STRONG hari ini."

    issues = check_claims(draft, _ctx([_pick("GOTO", conviction="WATCH")]))

    assert any("GOTO" in i and "STRONG" in i for i in issues)


def test_allows_strong_claim_when_engine_says_strong():
    draft = "GOTO masuk kategori STRONG hari ini."

    assert check_claims(draft, _ctx([_pick("GOTO", conviction="STRONG")])) == []


def test_flags_buy_narrative_when_market_is_net_seller():
    """Bilang asing memborong pasar di hari outflow Rp285 miliar adalah kebalikan fakta."""
    draft = "Asing memborong pasar saham Indonesia hari ini."

    issues = check_claims(draft, _ctx([_pick("CUAN")], total_foreign=-285_000_000_000))

    assert any("net asing pasar negatif" in i.lower() for i in issues)


def test_allows_selective_inflow_phrasing_on_outflow_day():
    """'Paling sedikit ditinggalkan' justru pembacaan yang benar — jangan dihukum."""
    draft = ("Asing keluar dari pasar, tetapi CUAN termasuk yang paling sedikit "
             "ditinggalkan dan masih mencatat net buy.")

    assert check_claims(draft, _ctx([_pick("CUAN")], total_foreign=-285_000_000_000)) == []


def test_clean_draft_passes():
    draft = "Asing keluar dari sektor keuangan; energi menjadi penadah utama."

    assert check_claims(draft, _ctx([_pick("CUAN")])) == []


def test_check_survives_missing_flags():
    """Skor lama tanpa flags tak boleh membuat pemeriksa meledak."""
    pick = _pick("CUAN")
    pick["flags"] = None

    assert check_claims("CUAN rentan pump-and-dump.", _ctx([pick])) == []
