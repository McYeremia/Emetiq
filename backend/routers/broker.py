from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

import models
from database import get_db
from services.broker_scraper import scrape_broker_flow

router = APIRouter(prefix="/broker-flow", tags=["broker-flow"])


def _latest_date(db: Session) -> date | None:
    return db.query(func.max(models.BrokerFlow.date)).scalar()


@router.get("")
def get_broker_flow(
    date_param: Optional[date] = Query(None, alias="date"),
    db: Session = Depends(get_db),
):
    """Ambil semua data broker flow untuk satu hari (default: hari terbaru tersedia)."""
    target = date_param or _latest_date(db)
    if not target:
        return {"date": None, "data": []}

    rows = (
        db.query(models.BrokerFlow)
        .filter(models.BrokerFlow.date == target)
        .order_by(desc(models.BrokerFlow.total_value))
        .all()
    )
    return {
        "date": str(target),
        "data": [
            {
                "broker_code": r.broker_code,
                "broker_name": r.broker_name,
                "total_value": r.total_value,
                "volume":      r.volume,
                "frequency":   r.frequency,
            }
            for r in rows
        ],
    }


@router.get("/available-dates")
def get_available_dates(db: Session = Depends(get_db)):
    """Daftar tanggal yang sudah tersedia di database."""
    dates = (
        db.query(models.BrokerFlow.date)
        .distinct()
        .order_by(desc(models.BrokerFlow.date))
        .limit(30)
        .all()
    )
    return {"dates": [str(d[0]) for d in dates]}


@router.post("/scrape")
def scrape(
    date_param: Optional[date] = Query(None, alias="date"),
    db: Session = Depends(get_db),
):
    """Scrape IDX untuk data broker harian. Default: hari ini."""
    target = date_param or date.today()
    try:
        n = scrape_broker_flow(target, db)
        return {"status": "ok", "date": str(target), "brokers_saved": n}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


def _scrape_bg(target: date):
    from database import SessionLocal
    db = SessionLocal()
    try:
        n = scrape_broker_flow(target, db)
        print(f"LOG: broker scrape done — {n} brokers saved for {target}")
    except RuntimeError as e:
        print(f"LOG: broker scrape failed — {e}")
    finally:
        db.close()


@router.post("/scrape/background")
def scrape_background(
    background_tasks: BackgroundTasks,
    date_param: Optional[date] = Query(None, alias="date"),
):
    """Jalankan scrape di background (non-blocking)."""
    target = date_param or date.today()
    background_tasks.add_task(_scrape_bg, target)
    return {"status": "started", "date": str(target)}
