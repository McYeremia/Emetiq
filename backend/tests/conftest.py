"""Pagar keselamatan: tes tidak boleh menyentuh basis data produksi.

Masalah yang ditutup berkas ini
-------------------------------
`main.py` menjalankan `Base.metadata.create_all(bind=engine)` saat modul diimpor,
dan `database.py` membaca `DATABASE_URL` dari `.env`. Berkas `.env` di mesin
pengembang memuat DATABASE_URL DUA KALI — sqlite lalu postgresql — dan yang
belakangan menang. Akibatnya `pytest tests/ -q` polos menyambung ke Supabase
produksi hanya untuk mengimpor modul, tanpa seorang pun menyadarinya.

Kenapa berkas ini yang menyelesaikannya
---------------------------------------
pytest mengimpor conftest.py SEBELUM modul tes mana pun, jadi penetapan di bawah
sudah ada di os.environ sebelum `database.py` pertama kali diimpor. `load_dotenv()`
tidak menimpa variabel yang sudah ada di environment, sehingga nilai di sini
menang atas `.env`.

`setdefault`, bukan penetapan paksa: CI atau pengukuran manual tetap boleh
mengarahkan ke basis data lain lewat environment, mis.

    DATABASE_URL="sqlite:///./idxanalyst.db" pytest tests/ -q

Perhatikan ini hanya mengatur engine BAWAAN yang dipakai saat impor. Tes endpoint
tetap membuat engine SQLite in-memory sendiri dan memasangnya lewat
`app.dependency_overrides[get_db]` — perilaku itu tidak berubah.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
