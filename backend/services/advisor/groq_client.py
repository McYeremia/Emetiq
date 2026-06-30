"""Wrapper tipis untuk Groq: chat teks & chat JSON, dengan retry/backoff.

SDK `groq` di-import lazy (di dalam fungsi) supaya modul ini bisa diimport tanpa
paket terpasang — tes me-mock `chat_json`/`chat_text` di level ini, jadi tak butuh
SDK maupun API key. API key dibaca dari env `GROQ_API_KEY` saat panggilan nyata.
"""
import os
import json
import time
import logging
from typing import Any, Dict, List

from services.advisor import config

log = logging.getLogger("advisor.groq")


class GroqError(Exception):
    """Kesalahan umum advisor↔Groq."""


class GroqConfigError(GroqError):
    """API key / paket belum siap (tidak di-retry)."""


class GroqCallError(GroqError):
    """Panggilan gagal setelah retry, atau output tak valid."""


_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise GroqConfigError("GROQ_API_KEY tidak diset di environment.")
        try:
            from groq import Groq  # lazy import
        except ImportError as e:  # pragma: no cover
            raise GroqConfigError("Paket 'groq' belum terpasang (pip install groq).") from e
        _client = Groq(api_key=api_key)
    return _client


def _create(messages: List[dict], model: str, *, json_mode: bool, effort, temperature: float):
    kwargs: Dict[str, Any] = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        timeout=config.REQUEST_TIMEOUT,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if effort:
        kwargs["reasoning_effort"] = effort
    return _get_client().chat.completions.create(**kwargs)


def _with_retry(fn):
    """Jalankan fn dengan retry eksponensial. Config error tidak di-retry."""
    last = None
    for attempt in range(config.MAX_RETRIES + 1):
        try:
            return fn()
        except GroqConfigError:
            raise
        except Exception as e:  # timeout / 5xx / rate-limit / lainnya
            last = e
            log.warning("Groq call gagal (attempt %d): %s", attempt + 1, e)
            if attempt < config.MAX_RETRIES:
                time.sleep(config.RETRY_BACKOFF * (2 ** attempt))
    raise GroqCallError(str(last))


def chat_text(system: str, user: str, *, model: str, effort=None, temperature: float = 0.3) -> str:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    resp = _with_retry(lambda: _create(messages, model, json_mode=False, effort=effort, temperature=temperature))
    return (resp.choices[0].message.content or "").strip()


def chat_json(system: str, user: str, *, model: str, effort=None, temperature: float = 0.2) -> Dict[str, Any]:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    resp = _with_retry(lambda: _create(messages, model, json_mode=True, effort=effort, temperature=temperature))
    content = (resp.choices[0].message.content or "{}").strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise GroqCallError(f"Output Groq bukan JSON valid: {e}") from e
