import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine
import models  # noqa: F401 — register ORM models

Base.metadata.create_all(bind=engine)

app = FastAPI(title="IDXAnalyst API", version="1.0.0")

# Origins yang diizinkan — dari env (comma-separated) saat deploy; default localhost dev.
_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
ALLOWED_ORIGINS = [o.strip() for o in _origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers.stocks import router as stocks_router    # noqa: E402
from routers.trades import router as trades_router    # noqa: E402
from routers.backtest import router as backtest_router  # noqa: E402
from routers.broker import router as broker_router    # noqa: E402
from routers.advisor import router as advisor_router  # noqa: E402
from routers.watchlist import router as watchlist_router  # noqa: E402
from routers.account import router as account_router    # noqa: E402
app.include_router(stocks_router)
app.include_router(trades_router)
app.include_router(backtest_router)
app.include_router(broker_router)
app.include_router(advisor_router)
app.include_router(watchlist_router)
app.include_router(account_router)
