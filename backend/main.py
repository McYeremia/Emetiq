import math
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from database import Base, engine
import models  # noqa: F401 — register ORM models

Base.metadata.create_all(bind=engine)


def _sanitize(obj):
    """Ganti float non-finite (NaN/Inf) jadi None secara rekursif.

    yfinance kadang mengisi fundamental (mis. pe_ratio) dengan Inf/NaN. Starlette
    men-serialisasi respons dengan allow_nan=False, jadi nilai seperti itu bikin
    seluruh endpoint 500. Sanitasi di sini menutup semua endpoint sekaligus.
    """
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


class SafeJSONResponse(JSONResponse):
    """JSONResponse yang membersihkan NaN/Inf sebelum encode."""

    def render(self, content) -> bytes:
        return super().render(_sanitize(content))


app = FastAPI(title="IDXAnalyst API", version="1.0.0", default_response_class=SafeJSONResponse)

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
from routers.ai_porto import router as ai_porto_router  # noqa: E402
from routers.admin import router as admin_router  # noqa: E402
from routers.bigmoney import router as bigmoney_router  # noqa: E402
app.include_router(stocks_router)
app.include_router(trades_router)
app.include_router(backtest_router)
app.include_router(broker_router)
app.include_router(advisor_router)
app.include_router(watchlist_router)
app.include_router(account_router)
app.include_router(ai_porto_router)
app.include_router(admin_router)
app.include_router(bigmoney_router)
