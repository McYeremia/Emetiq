"""Endpoint AI Porto (khusus tier dev).

POST /ai-porto/chat  -> dev memerintah AI mengelola porto; AI langsung eksekusi.
GET  /ai-porto/portfolio -> snapshot porto AI.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import CurrentUser, require_dev
from database import get_db
from services.advisor import groq_client
from services.ai_porto import pipeline, data

log = logging.getLogger("ai_porto.endpoint")

router = APIRouter(prefix="/ai-porto", tags=["ai-porto"])

CONFIG_REPLY = "AI Porto belum aktif: GROQ_API_KEY belum diatur di server."
BUSY_REPLY = "AI sedang sibuk. Coba lagi sebentar lagi."


class Turn(BaseModel):
    role: str
    content: str


class ManageRequest(BaseModel):
    message: str
    history: Optional[List[Turn]] = None


@router.get("/portfolio")
def get_ai_portfolio(db: Session = Depends(get_db),
                     _: CurrentUser = Depends(require_dev)):
    return data.portfolio_state(db)


@router.post("/chat")
def manage(req: ManageRequest, db: Session = Depends(get_db),
           _: CurrentUser = Depends(require_dev)):
    try:
        return pipeline.run_manage(db, req.message)
    except groq_client.GroqConfigError:
        return _fallback(db, CONFIG_REPLY)
    except groq_client.GroqError:
        return _fallback(db, BUSY_REPLY)


def _fallback(db: Session, msg: str) -> dict:
    return {"reply": msg, "regime": None, "guardrails": None, "strategy_note": "",
            "auto_exits": [], "executed": [], "skipped": [], "snapshot": data.portfolio_state(db)}
