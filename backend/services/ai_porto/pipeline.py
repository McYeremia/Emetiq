"""Pipeline AI Porto v2: risiko adaptif + otak hybrid.

Alur run_manage:
  1. snapshot + rezim risiko (kode)
  2. auto exit TP/CL (kode)
  3. skor kandidat (kode)
  4. LLM usulkan rencana di dalam guardrail rezim
  5. enforcement guardrail (kode) -> eksekusi
Keputusan besar ditentukan kode teruji; LLM memilih di dalam pagar & menjelaskan.
"""
import json
import logging
import time
from typing import Any, Dict, List

from pydantic import ValidationError
from sqlalchemy.orm import Session

from services import trade_exec
from services.advisor import config as advisor_config, groq_client
from services.advisor.pipelines import new_deadline
from services.ai_porto import config, data, risk
from services.ai_porto.schemas import TradingPlan

log = logging.getLogger("ai_porto.pipeline")

MAX_ORDERS = config.MAX_ORDERS
TRADE_TYPE = "AUTO_AI"

SYSTEM = (
    "Kamu manajer portofolio otonom untuk saham IDX. Tujuanmu MEMAKSIMALKAN keuntungan. "
    "Sistem sudah menentukan REZIM risiko (AGGRESSIVE/NORMAL/DEFENSIVE) beserta GUARDRAIL "
    "(maks % per saham, maks total deploy, maks jumlah posisi). Sistem akan MEMAKSA guardrail "
    "ini, jadi ikuti agar rencanamu tidak dipangkas. Saat cuan/rezim agresif, boleh konsentrasi & "
    "pakai kas lebih banyak; saat defensif, kecilkan posisi & sisakan kas. "
    "Utamakan kandidat ber-SKOR tinggi. Kamu boleh JUAL untuk rebalance. "
    "Gunakan HANYA ticker dari KANDIDAT atau HOLDINGS. Satuan LOT (1 lot = 100 lembar). "
    "Balas HANYA satu objek JSON: "
    '{"orders":[{"action":"BUY|SELL","ticker":"KODE","lots":<int>0>,"reason":"..."}],'
    '"strategy_note":"ringkas strategimu"}. Jangan mengarang harga/ticker.'
)


def _dumps(obj: Any) -> str:
    return json.dumps(obj, default=str, ensure_ascii=False)


def _slim_candidates(cands: List[Dict]) -> List[Dict]:
    return [{
        "ticker": c["ticker"], "score": c.get("score"), "price": c.get("last_price"),
        "rsi": c.get("rsi"), "trend": c.get("trend"),
        "signal": c.get("signal_strength"), "pe": c.get("pe"), "div": c.get("dividend_yield"),
    } for c in cands]


def _make_plan(instruction: str, state: Dict, regime: str, guard: Dict,
               cands: List[Dict], deployable: float, deadline: float) -> TradingPlan:
    payload = {
        "instruksi": instruction,
        "rezim": regime,
        "guardrail": guard,
        "kas_tersedia": state["cash"],
        "kas_boleh_dipakai": round(max(0.0, deployable), 2),
        "total_equity": state["total_value"],
        "holdings": state["holdings"],
        "kandidat": _slim_candidates(cands),
        "max_orders": MAX_ORDERS,
    }
    user = "DATA:\n" + _dumps(payload)
    raw = groq_client.chat_json(SYSTEM, user, model=advisor_config.REASONING_MODEL,
                                effort=advisor_config.REASONING_EFFORT["synthesis"])
    try:
        return TradingPlan.model_validate(raw)
    except ValidationError:
        if time.monotonic() >= deadline:
            log.warning("Repair TradingPlan dilewati — anggaran waktu pipeline habis.")
            return TradingPlan()
        repair = user + "\n\nOutput sebelumnya TIDAK sesuai skema. Balas ULANG HANYA JSON valid."
        try:
            raw2 = groq_client.chat_json(SYSTEM, repair, model=advisor_config.REASONING_MODEL,
                                         effort=advisor_config.REASONING_EFFORT["synthesis"])
            return TradingPlan.model_validate(raw2)
        except (ValidationError, groq_client.GroqError):
            log.warning("TradingPlan gagal divalidasi — plan kosong.")
            return TradingPlan()


def _sell(db: Session, ticker: str, lots: int, reason: str):
    return trade_exec.execute_trade(db, ticker=ticker, action="SELL", lots=lots,
                                    trade_type=TRADE_TYPE, user_id=None,
                                    strategy_id="ai", notes=reason)


def _run_auto_exits(db: Session, state: Dict, guard: Dict) -> List[Dict]:
    executed = []
    for o in risk.auto_exit_orders(state, guard):
        try:
            tr = _sell(db, o["ticker"], o["lots"], o["reason"])
            executed.append({"ticker": o["ticker"], "action": "SELL", "lots": o["lots"],
                             "price": tr.price, "reason": o["reason"]})
        except trade_exec.TradeError as e:
            log.warning("Auto-exit %s gagal: %s", o["ticker"], e)
    return executed


def _enforce_execute(db: Session, orders, guard: Dict):
    """Eksekusi order LLM dengan memaksa guardrail rezim. Recompute state tiap order."""
    executed, skipped = [], []
    for o in orders[:MAX_ORDERS]:
        state = data.portfolio_state(db)
        equity = state["total_value"]
        holdings = {h["ticker"]: h for h in state["holdings"]}

        if o.action == "SELL":
            try:
                tr = _sell(db, o.ticker, o.lots, o.reason or "rebalance")
                executed.append({"ticker": o.ticker, "action": "SELL", "lots": o.lots,
                                 "price": tr.price, "reason": o.reason})
            except trade_exec.TradeError as e:
                skipped.append({"ticker": o.ticker, "action": "SELL", "lots": o.lots, "reason": str(e)})
            continue

        # BUY — pangkas ke guardrail rezim
        stock, price = data.price_of(db, o.ticker)
        if price is None:
            skipped.append({"ticker": o.ticker, "action": "BUY", "lots": o.lots,
                            "reason": "harga/ticker tidak tersedia"})
            continue

        is_new = o.ticker not in holdings
        if is_new and len(holdings) >= guard["max_positions"]:
            skipped.append({"ticker": o.ticker, "action": "BUY", "lots": o.lots,
                            "reason": f"melebihi batas {guard['max_positions']} posisi (rezim)"})
            continue

        held = holdings.get(o.ticker, {})
        cur_val = held.get("current_price", 0) * held.get("shares", 0)
        room_pos = guard["max_position_pct"] * equity - cur_val
        room_deploy = guard["max_deploy_pct"] * equity - state["invested"]
        room = min(room_pos, room_deploy)
        lot_cost = price * 100
        max_lots = int(room // lot_cost) if room > 0 else 0
        lots = min(o.lots, max_lots)
        if lots <= 0:
            skipped.append({"ticker": o.ticker, "action": "BUY", "lots": o.lots,
                            "reason": "tak muat di pagar risiko rezim"})
            continue

        try:
            tr = trade_exec.execute_trade(db, ticker=o.ticker, action="BUY", lots=lots,
                                          trade_type=TRADE_TYPE, user_id=None,
                                          strategy_id="ai", notes=o.reason or "")
            note = o.reason or ""
            if lots != o.lots:
                note = (note + f" (dipangkas dari {o.lots} ke {lots} lot oleh guardrail)").strip()
            executed.append({"ticker": o.ticker, "action": "BUY", "lots": lots,
                             "price": tr.price, "reason": note})
        except trade_exec.TradeError as e:
            skipped.append({"ticker": o.ticker, "action": "BUY", "lots": o.lots, "reason": str(e)})

    return executed, skipped


def run_manage(db: Session, instruction: str) -> Dict[str, Any]:
    """Satu siklus kelola porto AI dengan risiko adaptif."""
    state = data.portfolio_state(db)
    peak = risk.peak_equity(db, state["total_value"])
    regime = risk.compute_regime(state["total_value"], peak)
    guard = risk.guardrails(regime)

    # 1) Auto exit TP/CL (kode) — sebelum rencana LLM
    auto_exits = _run_auto_exits(db, state, guard)

    # 2) State segar setelah exit
    state = data.portfolio_state(db)
    cands = data.scored_candidates(db)
    deployable = guard["max_deploy_pct"] * state["total_value"] - state["invested"]

    # 3) Rencana LLM di dalam guardrail
    plan = _make_plan(instruction, state, regime, guard, cands, deployable, deadline=new_deadline())

    # 4) Enforcement + eksekusi
    executed, skipped = _enforce_execute(db, plan.orders, guard)

    snapshot = data.portfolio_state(db)

    parts = [f"Rezim: {regime}."]
    if auto_exits:
        parts.append(f"Auto-exit {len(auto_exits)} posisi (TP/CL).")
    if executed:
        parts.append(f"Dieksekusi {len(executed)} order.")
    elif not auto_exits:
        parts.append("Tidak ada aksi baru." if not skipped else "Tidak ada order yang lolos guardrail.")
    if plan.strategy_note:
        parts.append(plan.strategy_note)

    return {
        "reply": " ".join(parts),
        "regime": regime,
        "guardrails": guard,
        "strategy_note": plan.strategy_note,
        "auto_exits": auto_exits,
        "executed": executed,
        "skipped": skipped,
        "snapshot": snapshot,
    }
