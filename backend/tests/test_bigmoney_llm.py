"""Tes services/bigmoney/llm — klien Gemini yang terisolasi dari Groq.

Tak ada tes yang memanggil Gemini sungguhan maupun butuh GEMINI_API_KEY.
Seluruh SDK di-mock; yang diuji adalah kontraknya, bukan jaringannya.
"""
import pytest

from services.bigmoney import llm
from services.bigmoney.llm import LlmError, LlmNotConfigured, generate_text, is_configured


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(llm, "_MODEL_CACHE", None)


def test_is_configured_false_without_key():
    assert is_configured() is False


def test_is_configured_true_with_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "kunci-palsu")

    assert is_configured() is True


def test_generate_text_without_key_raises_actionable_error():
    """Key belum diambil: galatnya harus menyebut nama env var, bukan AttributeError."""
    with pytest.raises(LlmNotConfigured, match="GEMINI_API_KEY"):
        generate_text("halo")


def test_generate_text_returns_model_output(monkeypatch, mocker):
    monkeypatch.setenv("GEMINI_API_KEY", "kunci-palsu")
    model = mocker.Mock()
    model.generate_content.return_value = mocker.Mock(text="  laporan pasar  ")
    mocker.patch("services.bigmoney.llm._get_model", return_value=model)

    assert generate_text("prompt apa saja") == "laporan pasar"


def test_generate_text_wraps_sdk_failure(monkeypatch, mocker):
    """Gemini tumbang tak boleh membocorkan galat SDK mentah ke pemanggil."""
    monkeypatch.setenv("GEMINI_API_KEY", "kunci-palsu")
    model = mocker.Mock()
    model.generate_content.side_effect = RuntimeError("503 backend kelebihan beban")
    mocker.patch("services.bigmoney.llm._get_model", return_value=model)

    with pytest.raises(LlmError, match="Gemini"):
        generate_text("prompt")


def test_generate_text_rejects_empty_response(monkeypatch, mocker):
    """Respons kosong (mis. kena filter keamanan) adalah kegagalan, bukan laporan kosong."""
    monkeypatch.setenv("GEMINI_API_KEY", "kunci-palsu")
    model = mocker.Mock()
    model.generate_content.return_value = mocker.Mock(text="")
    mocker.patch("services.bigmoney.llm._get_model", return_value=model)

    with pytest.raises(LlmError, match="kosong"):
        generate_text("prompt")


def test_llm_module_does_not_import_groq():
    """Batas tegas: fitur ini pakai Gemini, Groq tetap milik AI Advisor."""
    import inspect

    source = inspect.getsource(llm)
    assert "groq" not in source.lower()
