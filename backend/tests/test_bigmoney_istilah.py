"""Tes kamus istilah Big Money — terjemahan awam tanpa kehilangan istilah aslinya."""
from services.bigmoney import istilah


def test_kondisi_pasar_menerjemahkan_dan_menyertakan_istilah_asli():
    hasil = istilah.kondisi_pasar("CALM", "BULL")

    assert "pasar tenang" in hasil and "tren naik" in hasil
    assert "CALM" in hasil and "BULL" in hasil


def test_fase_diterjemahkan_dengan_istilah_asli_dalam_kurung():
    assert istilah.fase("AKUMULASI") == "asing sedang mengumpulkan diam-diam (AKUMULASI)"


def test_istilah_tak_dikenal_dikembalikan_apa_adanya():
    """Fase baru di engine tak boleh menjatuhkan laporan hanya karena kamus tertinggal."""
    assert istilah.fase("FASE_BARU") == "FASE_BARU"
    assert istilah.keyakinan("ENTAH") == "ENTAH"


def test_nilai_kosong_tidak_melempar():
    assert istilah.fase(None) == "tidak diketahui"
    assert istilah.kondisi_pasar(None, None) == "tidak diketahui, tidak diketahui"


def test_pump_dump_menang_atas_divergensi():
    """Keduanya bisa menyala bersamaan; yang lebih berbahaya harus yang terbaca."""
    pesan = istilah.peringatan({"divergence": True, "pump_dump_risk": True})

    assert "jebakan" in pesan


def test_tanpa_bendera_tidak_ada_peringatan():
    assert istilah.peringatan({}) is None
    assert istilah.peringatan(None) is None
