"""Router intent: klasifikasi pesan user + ekstraksi parameter (gpt-oss-20b, JSON).

Output JSON dari LLM di-coerce ke RouterOutput yang tervalidasi. Parameter dari form
bantu UI di-merge (form menang karena itu input eksplisit user).
"""
import json
import logging
from typing import List, Optional

from services.advisor import config, prompts, groq_client
from services.advisor.schemas import (
    RouterOutput, RouterParams, ChatTurn, ScreenForm, AdvisorContext, VALID_INTENTS,
)

log = logging.getLogger("advisor.router")


def _history_text(history: List[ChatTurn], n: int) -> str:
    turns = history[-n:]
    return "\n".join(f"{t.role}: {t.content}" for t in turns)


def _build_user_message(message: str, history: List[ChatTurn], form: Optional[ScreenForm],
                        context: Optional[AdvisorContext]) -> str:
    parts: List[str] = []
    if history:
        parts.append("RINGKASAN PERCAKAPAN:\n" + _history_text(history, config.HISTORY_TURNS))
    if context and context.candidates:
        tickers = [str(c.get("ticker")) for c in context.candidates if c.get("ticker")]
        if tickers:
            parts.append(
                "KONTEKS KANDIDAT (daftar saham dari giliran sebelumnya, siap dipilih): "
                + ", ".join(tickers)
            )
    if form:
        provided = {k: v for k, v in form.model_dump().items() if v is not None}
        if provided:
            parts.append("PARAM FORM: " + json.dumps(provided))
    parts.append("PESAN USER:\n" + message)
    return "\n\n".join(parts)


def _coerce(raw: dict) -> RouterOutput:
    intent = str(raw.get("intent") or "clarify").lower()
    if intent not in VALID_INTENTS:
        intent = "clarify"

    params_raw = raw.get("params") or {}
    if not isinstance(params_raw, dict):
        params_raw = {}
    params = RouterParams(**{k: params_raw.get(k) for k in RouterParams.model_fields})
    if params.ticker:
        params.ticker = str(params.ticker).upper()

    missing = raw.get("missing")
    if not isinstance(missing, list):
        missing = []

    return RouterOutput(intent=intent, params=params, missing=missing)


def _merge_form(out: RouterOutput, form: ScreenForm) -> RouterOutput:
    """Form bantu UI mengisi/menimpa parameter (input eksplisit user)."""
    for k, v in form.model_dump().items():
        if v is None:
            continue
        setattr(out.params, k, str(v).upper() if k == "ticker" else v)
    return out


def route(message: str, history: Optional[List[ChatTurn]] = None, form: Optional[ScreenForm] = None,
          context: Optional[AdvisorContext] = None) -> RouterOutput:
    history = history or []
    user_msg = _build_user_message(message, history, form, context)
    raw = groq_client.chat_json(
        prompts.ROUTER_SYSTEM, user_msg,
        model=config.ROUTER_MODEL,
        effort=config.REASONING_EFFORT["router"],
    )
    out = _coerce(raw)
    if form:
        out = _merge_form(out, form)
    return out
