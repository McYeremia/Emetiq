"""Regresi: jaga request Groq tetap di bawah plafon TPM free tier (penyebab 413)."""
from services.advisor import config, groq_client

# Groq free tier: gpt-oss-20b & gpt-oss-120b = 8000 tokens/menit (TPM).
FREE_TIER_TPM = 8000


def test_completion_cap_stays_under_free_tier_tpm():
    """`max_completion_tokens` di-reserve ke kuota TPM tiap request. Kalau >= 8000,
    SETIAP panggilan reasoning kena 413 sebelum input dihitung. Sisakan headroom
    untuk prompt input di bawah plafon 8000."""
    assert config.MAX_COMPLETION_TOKENS < FREE_TIER_TPM
    assert config.MAX_COMPLETION_TOKENS <= 6000  # >= ~2000 token untuk input


def test_reasoning_effort_never_forces_oversized_output():
    """Effort 'high' menggelembungkan token nalar (ikut dihitung ke keluaran & TPM);
    hindari di jalur pipeline agar tak menembus limit."""
    assert "high" not in config.REASONING_EFFORT.values()


def test_create_forwards_completion_cap_to_sdk(monkeypatch):
    """`_create` harus meneruskan `max_completion_tokens` (= nilai config) ke SDK,
    agar plafon benar-benar berlaku dan tetap di bawah TPM."""
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return object()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(groq_client, "_get_client", lambda: FakeClient())
    groq_client._create(
        [{"role": "user", "content": "hi"}], "openai/gpt-oss-120b",
        json_mode=False, effort=None, temperature=0.2,
    )
    assert captured["max_completion_tokens"] == config.MAX_COMPLETION_TOKENS
    assert captured["max_completion_tokens"] < FREE_TIER_TPM
