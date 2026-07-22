from sqlalchemy.pool import NullPool

from database import build_engine


def test_postgres_memeriksa_koneksi_sebelum_dipakai():
    """Container HF dibekukan saat idle dan Supavisor memutus koneksi diam.
    Tanpa pre-ping, soket mati dibagikan ke request berikutnya dan psycopg2
    menulis ke sana sampai TCP menyerah — 'could not send data to server'."""
    engine = build_engine("postgresql://u:p@host:5432/db")
    assert engine.pool._pre_ping is True


def test_postgres_membuang_koneksi_yang_sudah_lama():
    engine = build_engine("postgresql://u:p@host:5432/db")
    assert 0 < engine.pool._recycle <= 1800


def test_sqlite_tetap_tanpa_pool():
    engine = build_engine("sqlite:///:memory:")
    assert isinstance(engine.pool, NullPool)
