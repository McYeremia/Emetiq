"""Pantauan portofolio AI — baca saja, untuk tier `pro` ke atas.

Ini BUKAN AI Porto. AI Porto (`routers/ai_porto.py`) adalah permukaan tier `dev`
yang mengeksekusi trade sungguhan lewat LLM; router ini hanya memperlihatkan
hasilnya kepada tier berbayar.

Kenapa router terpisah, bukan melonggarkan pagar yang sudah ada:

- Syarat pemilik repo saat fitur ini diminta adalah **jangan menyentuh AI Porto yang
  sudah ada sama sekali**, supaya kinerja dan perilakunya tak berubah sedikit pun.
  Menyunting `require_dev` di sana berarti menyentuhnya.
- Memisahkan router membuat batasnya bisa dibaca sekali lihat: berkas ini tak punya
  satu pun jalur tulis dan tak mengimpor pipeline AI-nya, jadi tak ada cara
  memicu trade dari sini — bahkan kalau seseorang salah pasang pagar nanti.

Yang dipakai bersama hanyalah `data.portfolio_state`, fungsi layanan yang murni
MEMBACA (kueri holdings + harga terakhir, tanpa tulis, tanpa LLM). Memakai fungsi
yang sama disengaja: kalau pantauan ini menghitung ulang dengan caranya sendiri,
suatu saat ia akan menampilkan angka yang berbeda dari yang dilihat pemiliknya.
Ada tes yang menuntut keduanya identik (`tests/test_ai_porto_monitor.py`).

Histori jual/beli TIDAK diduplikasi di sini: `GET /trades/history?agent=AI` sudah
terbuka untuk semua pengguna yang login sejak sebelum fitur ini ada.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import require_tier_minimal
from database import get_db
from services.ai_porto import data

router = APIRouter(prefix="/ai-porto-monitor", tags=["ai-porto-monitor"])

# Tier terendah yang boleh memantau. Diletakkan sebagai konstanta supaya kalau
# suatu saat dibuka ke `basic`, yang berubah satu baris dan tesnya ikut menyebutnya.
TIER_MINIMAL = "pro"


@router.get("/portfolio", dependencies=[Depends(require_tier_minimal(TIER_MINIMAL))])
def lihat_portofolio(db: Session = Depends(get_db)):
    """Snapshot bucket AI: kas, holdings, dan P&L — sama persis dengan yang dilihat
    tier dev di halaman AI Porto."""
    return data.portfolio_state(db)
