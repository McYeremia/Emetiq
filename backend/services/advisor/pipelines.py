"""3 pipeline AI Advisor: data builder (kode) -> spesialis -> sintesis -> kritik.

Setiap stage LLM divalidasi Pydantic dengan 1x percobaan repair, lalu fallback aman.
Pipeline mengembalikan dict {reply, data, confidence} yang dibungkus jadi ChatResponse
oleh endpoint.
"""
import json
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from pydantic import ValidationError

from services.advisor import config, prompts, groq_client, data_provider as dp
from services.advisor.schemas import (
    RouterOutput, RouterParams,
    ScreenRanking, AnalyzeSpecialist, AnalyzeSynthesis, Critique,
    PortfolioSynthesis,
)

log = logging.getLogger("advisor.pipelines")

EFFORT = config.REASONING_EFFORT
REASONING = config.REASONING_MODEL
LIGHT = config.ROUTER_MODEL


def _dumps(obj: Any) -> str:
    return json.dumps(obj, default=str, ensure_ascii=False)


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def _stage_json(model_cls, system: str, payload: Any, *, model: str, effort):
    """Panggil Groq JSON, validasi ke skema; 1x repair; fallback ke default skema."""
    user = "DATA:\n" + (_dumps(payload) if not isinstance(payload, str) else payload)
    raw = groq_client.chat_json(system, user, model=model, effort=effort)
    try:
        return model_cls.model_validate(raw)
    except ValidationError:
        repair = user + "\n\nOutput sebelumnya TIDAK sesuai skema. Balas ULANG, HANYA JSON valid sesuai skema."
        try:
            raw2 = groq_client.chat_json(system, repair, model=model, effort=effort)
            return model_cls.model_validate(raw2)
        except (ValidationError, groq_client.GroqError):
            log.warning("Stage %s gagal divalidasi, pakai fallback.", model_cls.__name__)
            return model_cls()


# ── Pipeline 1: Screening ────────────────────────────────────────────────────

def run_screen(db: Session, params: RouterParams) -> Dict[str, Any]:
    filters = dict(pe_max=params.pe_max, pbv_max=params.pbv_max, div_min=params.div_min,
                   rsi=params.rsi, trend=params.trend, sector=params.sector)
    candidates = dp.screen(db, **filters)

    if not candidates:
        return {
            "reply": "Tidak ada saham yang cocok dengan kriteria itu. Coba longgarkan — "
                     "misalnya naikkan PE maks, turunkan dividen min, atau lepas filter sektor.",
            "data": {"intent": "screen", "candidates": []},
            "confidence": None,
        }

    ranking = _stage_json(
        ScreenRanking, prompts.SCREEN_RANK_SYSTEM,
        {"kriteria": _clean(filters), "kandidat": candidates},
        model=REASONING, effort=EFFORT["synthesis"],
    )
    critiqued = _stage_json(
        ScreenRanking, prompts.SCREEN_CRITIQUE_SYSTEM,
        {"kriteria": _clean(filters), "pick": [i.model_dump() for i in ranking.items]},
        model=LIGHT, effort=EFFORT["specialist"],
    )
    items = critiqued.items or ranking.items
    items = [i for i in items if i.score > 0]
    items.sort(key=lambda x: x.score, reverse=True)

    if not items:
        # LLM gagal me-rank — tetap tampilkan kandidat mentah agar tidak buntu
        return {
            "reply": f"Ditemukan {len(candidates)} saham yang lolos kriteria.",
            "data": {"intent": "screen", "candidates": candidates},
            "confidence": None,
        }

    top = items[:5]
    lines = [f"Menemukan {len(items)} saham sesuai kriteria. Teratas:"]
    lines += [f"• {i.ticker} (skor {round(i.score)}) — {i.reason}" for i in top]
    return {
        "reply": "\n".join(lines),
        "data": {"intent": "screen", "candidates": [i.model_dump() for i in items]},
        "confidence": None,
    }


# ── Pipeline 2: Analisa 1 saham ──────────────────────────────────────────────

def run_analyze(db: Session, params: RouterParams) -> Dict[str, Any]:
    if not params.ticker:
        return {
            "reply": "Saham mana yang ingin dianalisa? Sebutkan kodenya, misalnya BBRI.",
            "data": {"intent": "clarify"},
            "confidence": None,
        }

    data = dp.analyze(db, params.ticker)
    if not data.get("found"):
        return {
            "reply": f"Saham {params.ticker} tidak ditemukan di basis data.",
            "data": {"intent": "analyze", "found": False, "ticker": params.ticker},
            "confidence": None,
        }

    if data.get("bars_available", 0) < 30:
        return {
            "reply": (f"{data['ticker']} baru punya {data.get('bars_available', 0)} hari data — "
                      "terlalu sedikit untuk analisa teknikal yang andal. Harga terakhir "
                      f"Rp {data.get('last_price')}."),
            "data": {"intent": "analyze", "ticker": data["ticker"], "insufficient_data": True, **data},
            "confidence": None,
        }

    spec = _stage_json(AnalyzeSpecialist, prompts.ANALYZE_SPECIALIST_SYSTEM, data,
                       model=REASONING, effort=EFFORT["specialist"])
    synth = _stage_json(AnalyzeSynthesis, prompts.ANALYZE_SYNTHESIS_SYSTEM,
                        {"data": data, "spesialis": spec.model_dump()},
                        model=REASONING, effort=EFFORT["synthesis"])
    crit = _stage_json(Critique, prompts.ANALYZE_CRITIQUE_SYSTEM,
                       {"data": data, "keputusan": synth.model_dump()},
                       model=REASONING, effort=EFFORT["critique"])

    card = {
        "intent": "analyze",
        "ticker": data["ticker"],
        "decision": synth.decision,
        "last_price": data["last_price"],
        "entry": synth.entry,
        "take_profit": synth.take_profit,
        "cut_loss": synth.cut_loss,
        "confidence": crit.confidence,
        "warnings": crit.warnings,
        "signals": {
            "rsi": data["indicators"].get("RSI_14"),
            "rsi_band": data.get("rsi_band"),
            "trend": data.get("trend"),
        },
    }
    return {"reply": synth.reasoning or "Analisa selesai.", "data": card, "confidence": crit.confidence}


# ── Pipeline 3: Saran portofolio ─────────────────────────────────────────────

def run_portfolio(db: Session, user_id: str) -> Dict[str, Any]:
    port = dp.portfolio(db, user_id)
    if port["position_count"] == 0:
        return {
            "reply": "Belum ada posisi aktif di portofolio kamu. Tambah posisi dulu untuk dapat saran.",
            "data": {"intent": "portfolio", "holdings": []},
            "confidence": None,
        }

    synth = _stage_json(PortfolioSynthesis, prompts.PORTFOLIO_SYNTHESIS_SYSTEM, port,
                        model=REASONING, effort=EFFORT["synthesis"])
    crit = _stage_json(
        Critique, prompts.PORTFOLIO_CRITIQUE_SYSTEM,
        {"portofolio": {"cash": port["cash"], "total_value": port["total_value"],
                        "position_count": port["position_count"]},
         "saran": synth.model_dump()},
        model=REASONING, effort=EFFORT["critique"],
    )

    reply = synth.overview or "Berikut tinjauan portofoliomu."
    if synth.cash_advice:
        reply += "\n\nKas: " + synth.cash_advice
    return {
        "reply": reply,
        "data": {
            "intent": "portfolio",
            "overview": synth.overview,
            "actions": [a.model_dump() for a in synth.actions],
            "cash_advice": synth.cash_advice,
            "snapshot": {"cash": port["cash"], "total_value": port["total_value"],
                         "invested": port["invested"], "unrealized": port["unrealized"]},
        },
        "confidence": crit.confidence,
    }


# ── Dispatcher ───────────────────────────────────────────────────────────────

def run(db: Session, route_out: RouterOutput, user_id: str) -> Dict[str, Any]:
    """Jalankan pipeline sesuai intent. (clarify/chitchat ditangani di endpoint.)"""
    if route_out.intent == "screen":
        return run_screen(db, route_out.params)
    if route_out.intent == "analyze":
        return run_analyze(db, route_out.params)
    if route_out.intent == "portfolio":
        return run_portfolio(db, user_id)
    raise ValueError(f"Intent bukan pipeline: {route_out.intent}")
