"""Watchlist per user. Semua endpoint butuh login (get_current_user).

Sebelumnya watchlist disimpan di localStorage frontend; kini per user di DB.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel

import models
from auth import CurrentUser, get_current_user
from database import get_db

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistItem(BaseModel):
    ticker: str


@router.get("")
def get_watchlist(db: Session = Depends(get_db),
                  user: CurrentUser = Depends(get_current_user)):
    rows = (
        db.query(models.Watchlist)
        .filter(models.Watchlist.user_id == user.id)
        .order_by(models.Watchlist.created_at)
        .all()
    )
    return {"tickers": [r.ticker for r in rows]}


@router.post("")
def add_watchlist(item: WatchlistItem, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(get_current_user)):
    ticker = item.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker kosong.")
    exists = (
        db.query(models.Watchlist)
        .filter(models.Watchlist.user_id == user.id, models.Watchlist.ticker == ticker)
        .first()
    )
    if exists:
        return {"status": "ok", "ticker": ticker}  # idempoten
    row = models.Watchlist(user_id=user.id, ticker=ticker)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # ada race; tetap dianggap sukses karena sudah ada
    return {"status": "ok", "ticker": ticker}


@router.delete("/{ticker}")
def remove_watchlist(ticker: str, db: Session = Depends(get_db),
                     user: CurrentUser = Depends(get_current_user)):
    ticker = ticker.strip().upper()
    deleted = (
        db.query(models.Watchlist)
        .filter(models.Watchlist.user_id == user.id, models.Watchlist.ticker == ticker)
        .delete()
    )
    db.commit()
    return {"status": "ok", "removed": deleted}
