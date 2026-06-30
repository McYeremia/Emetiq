"""Endpoint AI Advisor: POST /advisor/chat.

Alur: router intent -> (clarify/chitchat langsung) | (pipeline: cek kuota -> jalan -> potong kuota).
Kuota hanya dipotong saat pipeline berhasil. Groq gagal -> pesan ramah, kuota utuh.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import CurrentUser, get_current_user
from database import get_db
from services.advisor import router as intent_router, pipelines, quota, groq_client
from services.advisor.schemas import ChatRequest, ChatResponse, RouterOutput

log = logging.getLogger("advisor.endpoint")

router = APIRouter(prefix="/advisor", tags=["advisor"])

CHITCHAT_REPLY = (
    "Halo! Saya asisten saham IDX. Saya bisa bantu: (1) mencari saham sesuai kriteria, "
    "(2) menganalisa satu saham, atau (3) memberi saran portofolio. Mau mulai dari mana?"
)
CONFIG_REPLY = "Fitur advisor belum aktif: GROQ_API_KEY belum diatur di server."
BUSY_REPLY = "Maaf, asisten sedang sibuk. Coba lagi sebentar lagi."


def _clarify_reply(route_out: RouterOutput) -> str:
    if route_out.missing:
        return "Boleh perjelas dulu? Saya butuh info: " + ", ".join(route_out.missing) + "."
    return ("Mau screening saham, analisa satu saham, atau saran portofolio? "
            "Sebutkan lebih spesifik ya — misalnya \"cari saham PE<15 dividen>3%\" atau \"analisa BBRI\".")


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db),
         user: CurrentUser = Depends(get_current_user)):
    # 1) Router intent
    try:
        route_out = intent_router.route(req.message, req.history, req.form)
    except groq_client.GroqConfigError:
        return ChatResponse(reply=CONFIG_REPLY, intent="chitchat", quota=quota.peek(db, user))
    except groq_client.GroqError:
        return ChatResponse(reply=BUSY_REPLY, intent="chitchat", quota=quota.peek(db, user))

    # 2) Non-pipeline intents — tidak memotong kuota
    if route_out.intent == "clarify":
        return ChatResponse(reply=_clarify_reply(route_out), intent="clarify", quota=quota.peek(db, user))
    if route_out.intent == "chitchat":
        return ChatResponse(reply=CHITCHAT_REPLY, intent="chitchat", quota=quota.peek(db, user))

    # 3) Pipeline — cek kuota dulu (belum dipotong)
    try:
        quota.ensure_available(db, user)
    except quota.QuotaExceeded as e:
        raise HTTPException(status_code=429, detail={
            "message": "Kuota harian advisor habis. Reset tengah malam, atau upgrade tier.",
            "quota": e.info.model_dump(),
        })

    # 4) Jalankan pipeline. Gagal -> pesan ramah, kuota TIDAK dipotong.
    try:
        result = pipelines.run(db, route_out, user_id=user.id)
    except groq_client.GroqConfigError:
        return ChatResponse(reply=CONFIG_REPLY, intent=route_out.intent, quota=quota.peek(db, user))
    except groq_client.GroqError:
        return ChatResponse(
            reply="Maaf, analisa gagal diselesaikan. Kuota kamu tidak terpotong — silakan coba lagi.",
            intent=route_out.intent, quota=quota.peek(db, user),
        )

    # 5) Sukses -> potong kuota
    q = quota.consume(db, user)
    return ChatResponse(
        reply=result["reply"],
        intent=route_out.intent,
        data=result.get("data"),
        quota=q,
        confidence=result.get("confidence"),
    )
