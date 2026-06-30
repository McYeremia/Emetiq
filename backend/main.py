from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine
import models  # noqa: F401 — register ORM models

Base.metadata.create_all(bind=engine)

app = FastAPI(title="IDXAnalyst API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers.stocks import router as stocks_router    # noqa: E402
from routers.trades import router as trades_router    # noqa: E402
from routers.backtest import router as backtest_router  # noqa: E402
from routers.broker import router as broker_router    # noqa: E402
from routers.advisor import router as advisor_router  # noqa: E402
app.include_router(stocks_router)
app.include_router(trades_router)
app.include_router(backtest_router)
app.include_router(broker_router)
app.include_router(advisor_router)
