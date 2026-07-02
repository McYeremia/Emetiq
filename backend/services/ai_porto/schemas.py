"""Skema trading plan yang dihasilkan LLM untuk AI Porto."""
from typing import List
from pydantic import BaseModel, Field, field_validator


class Order(BaseModel):
    action: str
    ticker: str
    lots: int = Field(gt=0)
    reason: str = ""

    @field_validator("action")
    @classmethod
    def _action(cls, v: str) -> str:
        v = (v or "").upper()
        if v not in ("BUY", "SELL"):
            raise ValueError("action harus BUY atau SELL")
        return v

    @field_validator("ticker")
    @classmethod
    def _ticker(cls, v: str) -> str:
        return (v or "").upper().strip()


class TradingPlan(BaseModel):
    orders: List[Order] = []
    strategy_note: str = ""
