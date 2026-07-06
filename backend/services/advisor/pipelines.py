"""3 pipeline AI Advisor: data builder (kode) -> spesialis -> sintesis -> kritik.

Setiap stage LLM divalidasi Pydantic dengan 1x percobaan repair, lalu fallback aman.
Pipeline mengembalikan dict {reply, data, confidence} yang dibungkus jadi ChatResponse
oleh endpoint.
"""
import json
import logging
import time
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from pydantic import ValidationError

from services.advisor import config, prompts, groq_client, data_provider as dp
from services.advisor.schemas import (
    RouterOutput, RouterParams, AdvisorContext,
    ScreenRanking, AnalyzeSpecialist, AnalyzeSynthesis, Critique,
    PortfolioSynthesis,
)

log = logging.getLogger("advisor.pipelines")

EFFORT = config.REASONING_EFFORT
REASONING = config.REASONING_MODEL
LIGHT = config.ROUTER_MODEL


def new_deadline() -> float:
    """Anggaran waktu (monotonic) utk 1 pipeline — dipakai `_stage_json` agar stage
    berikutnya dilewati begitu waktu habis, bukan menambah panggilan Groq baru."""
    return time.monotonic() + config.PIPELINE_BUDGET_SECONDS


def _dumps(obj: Any) -> str:
    return json.dumps(obj, default=str, ensure_ascii=False)


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def _clamp_count(requested, default: int) -> int:
    """Jumlah saham yang dikembalikan: pakai permintaan user bila ada, jatuh ke default,
    lalu dibatasi 1..SCREEN_MAX_COUNT agar hasil tetap ringkas."""
    try:
        n = int(requested) if requested else default
    except (TypeError, ValueError):
        n = default
    return max(1, min(n, config.SCREEN_MAX_COUNT))


def _rank_reply(items: list) -> str:
    """Narasi tegas: sebut pemenang lebih dulu, lalu peringkat sisanya (bila ada)."""
    best = items[0]
    lines = [f"Pilihan teratas: {best.ticker} (skor {round(best.score)}) — {best.reason}"]
    if len(items) > 1:
        lines.append("Peringkat berikutnya:")
        lines += [f"{n}. {i.ticker} (skor {round(i.score)}) — {i.reason}"
                  for n, i in enumerate(items[1:], start=2)]
    return "\n".join(lines)


def _stage_json(model_cls, system: str, payload: Any, *, model: str, effort, deadline: Optional[float] = None):
    """Panggil Groq JSON, validasi ke skema; 1x repair; fallback ke default skema.

    Kalau `deadline` (anggaran waktu pipeline) sudah lewat, lewati panggilan sama
    sekali dan langsung fallback — mencegah stage lanjutan menambah tunggu lama.
    """
    if deadline is not None and time.monotonic() >= deadline:
        log.warning("Stage %s dilewati — anggaran waktu pipeline habis.", model_cls.__name__)
        return model_cls()

    user = "DATA:\n" + (_dumps(payload) if not isinstance(payload, str) else payload)
    raw = groq_client.chat_json(system, user, model=model, effort=effort)
    try:
        return model_cls.model_validate(raw)
    except ValidationError:
        if deadline is not None and time.monotonic() >= deadline:
            log.warning("Repair %s dilewati — anggaran waktu pipeline habis.", model_cls.__name__)
            return model_cls()
        repair = user + "\n\nOutput sebelumnya TIDAK sesuai skema. Balas ULANG, HANYA JSON valid sesuai skema."
        try:
            raw2 = groq_client.chat_json(system, repair, model=model, effort=effort)
            return model_cls.model_validate(raw2)
        except (ValidationError, groq_client.GroqError):
            log.warning("Stage %s gagal divalidasi, pakai fallback.", model_cls.__name__)
            return model_cls()


# ── Pipeline 1: Screening ────────────────────────────────────────────────────

def run_screen(db: Session, params: RouterParams, deadline: Optional[float] = None) -> Dict[str, Any]:
    filters = dict(pe_max=params.pe_max, pbv_max=params.pbv_max, div_min=params.div_min,
                   rsi=params.rsi, trend=params.trend, sector=params.sector,
                   price_max=params.price_max, price_min=params.price_min)
    candidates = dp.screen(db, **filters)

    if not candidates:
        return {
            "reply": "Tidak ada saham yang cocok dengan kriteria itu. Coba longgarkan — "
                     "misalnya naikkan PE maks, naikkan batas harga, turunkan dividen min, "
                     "atau lepas filter sektor.",
            "data": {"intent": "screen", "candidates": []},
            "confidence": None,
        }

    count = _clamp_count(params.count, config.SCREEN_DEFAULT_COUNT)
    # Hanya kirim pool kecil ke LLM & minta ia mengembalikan yang terbaik saja — bukan
    # menilai 40 saham (yang membuat keluaran meledak & JSON terpotong / kena rate limit).
    pool = candidates[: config.SCREEN_RANK_POOL]
    ranking = _stage_json(
        ScreenRanking, prompts.SCREEN_RANK_SYSTEM,
        {"kriteria": _clean(filters), "jumlah_diminta": count, "kandidat": pool},
        model=REASONING, effort=EFFORT["rank"], deadline=deadline,
    )
    critiqued = _stage_json(
        ScreenRanking, prompts.SCREEN_CRITIQUE_SYSTEM,
        {"kriteria": _clean(filters), "pick": [i.model_dump() for i in ranking.items]},
        model=LIGHT, effort=EFFORT["specialist"], deadline=deadline,
    )
    items = critiqued.items or ranking.items
    items = [i for i in items if i.score > 0]
    items.sort(key=lambda x: x.score, reverse=True)

    if not items:
        # LLM gagal me-rank — tetap tampilkan sebagian kandidat mentah agar tidak buntu
        shown = candidates[:count]
        return {
            "reply": f"Ditemukan {len(candidates)} saham yang lolos kriteria. Menampilkan {len(shown)} teratas (per kapitalisasi).",
            "data": {"intent": "screen", "candidates": shown, "top_pick": None},
            "confidence": None,
        }

    top = items[:count]
    return {
        "reply": _rank_reply(top),
        "data": {"intent": "screen", "candidates": [i.model_dump() for i in top],
                 "top_pick": top[0].ticker},
        "confidence": None,
    }


# ── Pipeline rank: pilih terbaik dari daftar giliran sebelumnya ──────────────

def run_rank(db: Session, params: RouterParams, context: Optional[AdvisorContext] = None,
             deadline: Optional[float] = None) -> Dict[str, Any]:
    """Pilih saham terbaik dari kandidat yang sudah ada di layar (giliran sebelumnya).
    Tak butuh ticker — menjawab tegas 'mana yang paling oke' tanpa menyuruh user memilih."""
    candidates = list(context.candidates) if context and context.candidates else []
    if not candidates:
        return {
            "reply": "Belum ada daftar saham untuk dibandingkan. Cari dulu (mis. \"cari saham "
                     "PE<15 dividen>3%\"), atau sebutkan beberapa kode yang ingin diadu.",
            "data": {"intent": "clarify"},
            "confidence": None,
        }

    count = _clamp_count(params.count, 1)
    ranking = _stage_json(
        ScreenRanking, prompts.RANK_SELECT_SYSTEM,
        {"jumlah_diminta": count, "kandidat": candidates[: config.SCREEN_RANK_POOL]},
        model=REASONING, effort=EFFORT["rank"], deadline=deadline,
    )
    items = [i for i in ranking.items if i.score > 0]
    items.sort(key=lambda x: x.score, reverse=True)

    if not items:
        # LLM gagal me-rank — jangan buntu, kembalikan kandidat pertama apa adanya
        first = candidates[:count]
        return {
            "reply": "Belum bisa memutuskan pemenang dari daftar itu — coba sebutkan kriteria "
                     "yang paling kamu utamakan (mis. paling murah, dividen tertinggi, tren terkuat).",
            "data": {"intent": "screen", "candidates": first, "top_pick": None},
            "confidence": None,
        }

    top = items[:count]
    return {
        "reply": _rank_reply(top),
        "data": {"intent": "screen", "candidates": [i.model_dump() for i in top],
                 "top_pick": top[0].ticker},
        "confidence": None,
    }


# ── Pipeline 2: Analisa 1 saham ──────────────────────────────────────────────

def run_analyze(db: Session, params: RouterParams, deadline: Optional[float] = None) -> Dict[str, Any]:
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
                       model=REASONING, effort=EFFORT["specialist"], deadline=deadline)
    synth = _stage_json(AnalyzeSynthesis, prompts.ANALYZE_SYNTHESIS_SYSTEM,
                        {"data": data, "spesialis": spec.model_dump()},
                        model=REASONING, effort=EFFORT["synthesis"], deadline=deadline)
    crit = _stage_json(Critique, prompts.ANALYZE_CRITIQUE_SYSTEM,
                       {"data": data, "keputusan": synth.model_dump()},
                       model=REASONING, effort=EFFORT["critique"], deadline=deadline)

    def _price(x):  # harga saham -> rupiah utuh (buang ekor desimal LLM)
        return round(x) if x is not None else None

    card = {
        "intent": "analyze",
        "ticker": data["ticker"],
        "decision": synth.decision,
        "last_price": data["last_price"],
        "entry": _price(synth.entry),
        "take_profit": _price(synth.take_profit),
        "cut_loss": _price(synth.cut_loss),
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

def run_portfolio(db: Session, user_id: str, deadline: Optional[float] = None) -> Dict[str, Any]:
    port = dp.portfolio(db, user_id)
    if port["position_count"] == 0:
        return {
            "reply": "Belum ada posisi aktif di portofolio kamu. Tambah posisi dulu untuk dapat saran.",
            "data": {"intent": "portfolio", "holdings": []},
            "confidence": None,
        }

    synth = _stage_json(PortfolioSynthesis, prompts.PORTFOLIO_SYNTHESIS_SYSTEM, port,
                        model=REASONING, effort=EFFORT["synthesis"], deadline=deadline)
    crit = _stage_json(
        Critique, prompts.PORTFOLIO_CRITIQUE_SYSTEM,
        {"portofolio": {"cash": port["cash"], "total_value": port["total_value"],
                        "position_count": port["position_count"]},
         "saran": synth.model_dump()},
        model=REASONING, effort=EFFORT["critique"], deadline=deadline,
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

def run(db: Session, route_out: RouterOutput, user_id: str,
        context: Optional[AdvisorContext] = None) -> Dict[str, Any]:
    """Jalankan pipeline sesuai intent. (clarify/chitchat ditangani di endpoint.)"""
    deadline = new_deadline()
    if route_out.intent == "screen":
        return run_screen(db, route_out.params, deadline=deadline)
    if route_out.intent == "rank":
        return run_rank(db, route_out.params, context, deadline=deadline)
    if route_out.intent == "analyze":
        return run_analyze(db, route_out.params, deadline=deadline)
    if route_out.intent == "portfolio":
        return run_portfolio(db, user_id, deadline=deadline)
    raise ValueError(f"Intent bukan pipeline: {route_out.intent}")
