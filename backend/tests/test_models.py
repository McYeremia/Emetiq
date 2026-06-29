from sqlalchemy import create_engine, inspect

def test_all_tables_created():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    from database import Base
    import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    tables = inspect(engine).get_table_names()
    assert "stocks" in tables
    assert "ohlcv_daily" in tables
    assert "indicators_cache" in tables
