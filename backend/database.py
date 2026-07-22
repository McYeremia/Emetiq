import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool, QueuePool
from dotenv import load_dotenv

load_dotenv()

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "idxanalyst.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_DB_PATH}")


def build_engine(url: str):
    if url.startswith("sqlite"):
        # SQLite tidak butuh connection pool — NullPool buka/tutup file langsung
        # per session
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
        )

    # Space HF gratis membekukan container saat idle, dan pooler Supabase
    # memutus koneksi yang diam. Soket di pool jadi mati tanpa sempat mengirim
    # FIN yang sampai ke sini, lalu dibagikan lagi ke request berikutnya:
    # psycopg2 menulis ke soket mati, tak ada yang meng-ACK, TCP retransmit
    # sampai menyerah ~2 menit — "could not send data to server: Connection
    # timed out", HTTP 500. Yang kebetulan dapat koneksi segar tetap jalan,
    # jadi gejalanya sebagian halaman hidup dan sebagian mati.
    #
    # pre_ping menembak probe murah sebelum koneksi dipakai dan mengganti yang
    # mati secara transparan; recycle membuang koneksi tua sebelum sempat basi.
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


engine = build_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
