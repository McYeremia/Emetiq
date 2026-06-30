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


def _content(resp) -> str:
    return (resp.choices[0].message.content or "").strip()


def _extract_json(text: str) -> Dict[str, Any]:
    """Parse JSON; bila ada teks pembungkus, ambil objek JSON seimbang pertama."""
    text = (text or "").strip()
    if not text:
        raise GroqCallError("Output Groq kosong.")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        raise GroqCallError("Tidak menemukan JSON pada output Groq.")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError as e:
                        raise GroqCallError(f"JSON tak valid: {e}") from e
    raise GroqCallError("JSON tidak lengkap pada output Groq.")


def chat_json(system: str, user: str, *, model: str, effort=None, temperature: float = 0.2) -> Dict[str, Any]:
    """Minta JSON. Coba JSON-mode ketat dulu; bila gagal (mis. model reasoning kena
    `json_validate_failed`), langsung fallback ke mode teks + ekstraksi JSON manual.
    Tidak meretry JSON-mode berkali-kali agar tak boros panggilan."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    # 1) JSON mode ketat (cepat & rapi, biasanya sukses untuk model kecil/router)
    try:
        resp = _create(messages, model, json_mode=True, effort=effort, temperature=temperature)
        return _extract_json(_content(resp) or "{}")
    except GroqConfigError:
        raise
    except Exception as e:
        log.warning("JSON mode gagal (%s) — fallback ke mode teks.", e)

    # 2) Fallback: mode teks biasa + ekstraksi JSON, dengan retry transient
    text_messages = messages + [{
        "role": "system",
        "content": "Keluarkan HANYA satu objek JSON valid sesuai skema, tanpa teks/penjelasan lain.",
    }]
    last = None
    for attempt in range(config.MAX_RETRIES + 1):
        try:
            resp = _create(text_messages, model, json_mode=False, effort=effort, temperature=temperature)
            return _extract_json(_content(resp))
        except GroqConfigError:
            raise
        except Exception as e:
            last = e
            log.warning("Fallback teks gagal (attempt %d): %s", attempt + 1, e)
            if attempt < config.MAX_RETRIES:
                time.sleep(config.RETRY_BACKOFF * (2 ** attempt))
    raise GroqCallError(str(last))
