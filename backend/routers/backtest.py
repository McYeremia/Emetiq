from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import services.backtester as bt_svc

router = APIRouter(prefix="/backtest", tags=["backtest"])

@router.get("/run/{ticker}/{strategy_id}")
def run_backtest_endpoint(
    ticker: str,
    strategy_id: str,
    capital: float = 10_000_000,
    db: Session = Depends(get_db),
):
    result = bt_svc.run_backtest(db, ticker.upper(), strategy_id, initial_capital=capital)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.get("/screen/{strategy_id}")
def screen_stocks_endpoint(strategy_id: str, db: Session = Depends(get_db)):
    import services.watcher as watcher
    matches = watcher.screen_by_strategy(db, strategy_id)
    return {"strategy_id": strategy_id, "matches": matches}
