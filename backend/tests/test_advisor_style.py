"""Jaga agar aturan gaya bahasa (istilah teknis + penjelasan singkat) tetap
tersisip di semua prompt yang menghasilkan teks untuk user — advisor & AI Porto."""
from services.advisor import prompts
from services.ai_porto import pipeline as porto_pipeline

MARKER = "investor awam"


def test_style_rule_in_advisor_user_facing_prompts():
    for p in (prompts.SCREEN_RANK_SYSTEM, prompts.ANALYZE_SYNTHESIS_SYSTEM,
              prompts.PORTFOLIO_SYNTHESIS_SYSTEM, prompts.NARRATOR_SYSTEM):
        assert MARKER in p


def test_style_rule_in_ai_porto_prompt():
    assert MARKER in porto_pipeline.SYSTEM
