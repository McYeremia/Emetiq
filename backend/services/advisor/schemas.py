"""Pydantic schemas untuk AI Advisor: request/response API + output tiap stage LLM.

Output LLM divalidasi lewat skema ini (lihat pipelines.py) supaya angka & struktur
terjamin sebelum dikirim ke frontend.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

Intent = str  # "screen" | "analyze" | "portfolio" | "rank" | "clarify" | "chitchat"
VALID_INTENTS = {"screen", "analyze", "portfolio", "rank", "clarify", "chitchat"}
PIPELINE_INTENTS = {"screen", "analyze", "portfolio", "rank"}  # yang memotong kuota


# ── API request/response ─────────────────────────────────────────────────────

class ChatTurn(BaseModel):
    role: str          # "user" | "assistant"
    content: str


class ScreenForm(BaseModel):
    """Parameter opsional dari form bantu di UI (di-merge dengan hasil router)."""
    ticker: Optional[str] = None
    pe_max: Optional[float] = None
    pbv_max: Optional[float] = None
    div_min: Optional[float] = None
    rsi: Optional[str] = None        # "oversold" | "overbought" | "neutral"
    trend: Optional[str] = None      # "up" | "down"
    sector: Optional[str] = None


class AdvisorContext(BaseModel):
    """Konteks yang dibawa dari giliran sebelumnya (mis. daftar kandidat hasil screening
    terakhir) agar follow-up seperti 'dari tadi mana paling oke?' bisa memilih tanpa
    minta ticker lagi."""
    candidates: List[Dict[str, Any]] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str
    history: List[ChatTurn] = Field(default_factory=list)
    form: Optional[ScreenForm] = None
    context: Optional[AdvisorContext] = None


class QuotaInfo(BaseModel):
    used: int
    limit: Optional[int] = None       # None = unlimited
    remaining: Optional[int] = None


class ChatResponse(BaseModel):
    reply: str                        # narasi bahasa natural
    intent: str
    data: Any = None                  # struktur tambahan (kartu/tabel) tergantung intent
    quota: Optional[QuotaInfo] = None
    confidence: Optional[float] = None


# ── Router output (gpt-oss-20b, JSON) ────────────────────────────────────────

class RouterParams(BaseModel):
    ticker: Optional[str] = None
    pe_max: Optional[float] = None
    pbv_max: Optional[float] = None
    div_min: Optional[float] = None
    rsi: Optional[str] = None
    trend: Optional[str] = None
    sector: Optional[str] = None
    price_max: Optional[float] = None  # harga saham saat ini maksimal ("di bawah 2000")
    price_min: Optional[float] = None  # harga saham saat ini minimal ("di atas 500")
    count: Optional[int] = None       # berapa banyak saham yang diminta user ("3 saham")


class RouterOutput(BaseModel):
    intent: str
    params: RouterParams = Field(default_factory=RouterParams)
    missing: List[str] = Field(default_factory=list)


# ── Pipeline 1: Screening ────────────────────────────────────────────────────

class ScreenRankItem(BaseModel):
    ticker: str
    score: float = 0.0
    reason: str = ""
    key_numbers: Dict[str, Any] = Field(default_factory=dict)


class ScreenRanking(BaseModel):
    items: List[ScreenRankItem] = Field(default_factory=list)


# ── Pipeline 2: Analisa 1 saham ──────────────────────────────────────────────

class AnalyzeSpecialist(BaseModel):
    technical: str = ""
    fundamental: str = ""
    ml_risk: str = ""
    score: float = 50.0               # 0-100 condong bullish


class AnalyzeSynthesis(BaseModel):
    decision: str = "TAHAN"           # BELI | TAHAN | JUAL
    entry: Optional[float] = None
    take_profit: Optional[float] = None
    cut_loss: Optional[float] = None
    reasoning: str = ""


# ── Pipeline 3: Portofolio ───────────────────────────────────────────────────

class PortfolioActionItem(BaseModel):
    ticker: str
    action: str = "HOLD"              # TRIM | ADD | HOLD
    reason: str = ""
    key_numbers: Dict[str, Any] = Field(default_factory=dict)


class PortfolioSynthesis(BaseModel):
    overview: str = ""
    actions: List[PortfolioActionItem] = Field(default_factory=list)
    cash_advice: str = ""


# ── Stage kritik (lintas-pipeline) ───────────────────────────────────────────

class Critique(BaseModel):
    confidence: float = 0.5           # 0-1
    notes: str = ""
    warnings: List[str] = Field(default_factory=list)
