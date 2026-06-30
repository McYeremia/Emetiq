"""AI Advisor (IDXAdvisor) — Groq-backed staged-prompting advisor.

Layout (lihat docs/superpowers/specs/2026-06-29-ai-advisor-design.md):
    config.py        — model IDs, TIER_LIMITS, timeouts
    schemas.py       — Pydantic request/response & per-stage outputs
    prompts.py       — system/stage prompts + JSON schema hints
    data_provider.py — data deterministik (screen/analyze/portfolio), tanpa LLM
    groq_client.py   — wrapper Groq (chat, JSON, retry)
    router.py        — klasifikasi intent + ekstraksi parameter
    pipelines.py     — 3 pipeline: builder(kode) -> spesialis -> sintesis -> kritik
    quota.py         — kuota harian per tier
"""
