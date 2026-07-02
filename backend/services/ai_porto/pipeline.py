"""Pipeline AI Porto: instruksi dev -> trading plan (LLM) -> eksekusi trade.

Eksekusi langsung tanpa konfirmasi (uang dummy). Order yang melanggar aturan
dana/holding dilewati & dilaporkan; order lain tetap jalan.
"""
import json
import logging
from typing import Any, Dict

from pydantic import ValidationError
from sqlalchemy.orm import Session

from services import trade_exec
from services.advisor import config, groq_client
from services.ai_porto import data
from services.ai_porto.schemas import TradingPlan

log = logging.getLogger("ai_porto.pipeline")

MAX_ORDERS = 10
TRADE_TYPE = "AUTO_AI"

SYSTEM = (
    "Kamu manajer portofolio otonom untuk saham IDX (Bursa Efek Indonesia). "
    "Tujuanmu MEMAKSIMALKAN keuntungan porto dengan strategi bebas. "
    "Kamu HANYA boleh memakai ticker dari daftar KANDIDAT atau dari HOLDINGS saat ini. "
    "Hormati kas: total pembelian tidak boleh melebihi kas tersedia. "
    "Jual hanya saham yang sedang dipegang. Satuan beli/jual adalah LOT (1 lot = 100 lembar). "
    "Balas HANYA satu objek JSON dengan skema: "
    '{"orders":[{"action":"BUY|SELL","ticker":"KODE","lots":<int>0>,"reason":"..."}],'
    '"strategy_note":"ringkas alasan strategimu"}. '
    "Jika tidak ada aksi yang layak, kembalikan orders kosong. Jangan mengarang harga atau ticker."
)


def _dumps(obj: Any) -> str:
    return json.dumps(obj, default=str, ensure_ascii=False)


def _make_plan(instruction: str, state: Dict, cands: Dict) -> TradingPlan:
    """Panggil Groq -> validasi TradingPlan; 1x repair; fallback plan kosong."""
    payload = {
        "instruksi": instruction,
        "kas_tersedia": state["cash"],
        "holdings": state["holdings"],
        "kandidat": cands,
        "max_orders": MAX_ORDERS,
    }
    user = "DATA:\n" + _dumps(payload)
    raw = groq_client.chat_json(SYSTEM, user, model=config.REASONING_MODEL,
                                effort=config.REASONING_EFFORT["synthesis"])
    try:
        return TradingPlan.model_validate(raw)
    except ValidationError:
        repair = user + "\n\nOutput sebelumnya TIDAK sesuai skema. Balas ULANG HANYA JSON valid."
        try:
            raw2 = groq_client.chat_json(SYSTEM, repair, model=config.REASONING_MODEL,
                                         effort=config.REASONING_EFFORT["synthesis"])
            return TradingPlan.model_validate(raw2)
        except (ValidationError, groq_client.GroqError):
            log.warning("TradingPlan gagal divalidasi — plan kosong.")
            return TradingPlan()


def run_manage(db: Session, instruction: str) -> Dict[str, Any]:
    """Jalankan satu siklus kelola porto AI dari sebuah instruksi."""
    state = data.portfolio_state(db)
    cands = data.candidates(db)

    plan = _make_plan(instruction, state, cands)

    executed = []
    skipped = []
    for order in plan.orders[:MAX_ORDERS]:
        try:
            tr = trade_exec.execute_trade(
                db,
                ticker=order.ticker,
                action=order.action,
                lots=order.lots,
                trade_type=TRADE_TYPE,
                user_id=None,
                strategy_id="ai",
                notes=order.reason or "",
            )
            executed.append({
                "ticker": order.ticker,
                "action": order.action,
                "lots": order.lots,
                "price": tr.price,
                "reason": order.reason,
            })
        except trade_exec.TradeError as e:
            skipped.append({
                "ticker": order.ticker,
                "action": order.action,
                "lots": order.lots,
                "reason": str(e),
            })

    snapshot = data.portfolio_state(db)

    if executed:
        head = f"Dieksekusi {len(executed)} order."
    elif skipped:
        head = "Tidak ada order yang bisa dieksekusi."
    else:
        head = "AI tidak mengusulkan aksi kali ini."
    reply = head
    if plan.strategy_note:
        reply += " " + plan.strategy_note

    return {
        "reply": reply,
        "strategy_note": plan.strategy_note,
        "executed": executed,
        "skipped": skipped,
        "snapshot": snapshot,
    }
