"""Tes services/bigmoney/pipeline — urutan tahap, hari non-bursa, dan laporan opsional.

Seluruh tahap di-mock: yang diuji adalah ORKESTRASInya (apa dipanggil, kapan
berhenti), bukan perhitungan yang sudah punya tesnya sendiri.
"""
from datetime import date

import pytest

from services.bigmoney.ingest import IngestResult
from services.bigmoney.engine import EngineResult
from services.bigmoney.llm import LlmError
from services.bigmoney.pipeline import PipelineResult, run_daily_pipeline

TARGET = date(2026, 7, 10)


@pytest.fixture
def stages(mocker):
    """Ketiga tahap, semuanya sukses secara default."""
    return {
        "ingest": mocker.patch(
            "services.bigmoney.pipeline.ingest_stock_summary",
            return_value=IngestResult(date=TARGET, trading_day=True, inserted=960),
        ),
        "score": mocker.patch(
            "services.bigmoney.pipeline.compute_scores",
            return_value=EngineResult(date=TARGET, trading_day=True, scored=273, strong=3, watch=88),
        ),
        "report": mocker.patch(
            "services.bigmoney.pipeline.run_report",
            return_value=mocker.Mock(
                headline="Asing keluar dari Finance",
                context={"broadcast": {"worthy": True, "reason": "3 saham STRONG"}},
            ),
        ),
        "configured": mocker.patch("services.bigmoney.pipeline.is_configured", return_value=True),
        "broadcast": mocker.patch("services.bigmoney.pipeline.broadcast_report", return_value=2),
    }


def test_pipeline_runs_all_three_stages_in_order(stages):
    result = run_daily_pipeline(TARGET, db=object())

    assert isinstance(result, PipelineResult)
    assert result.trading_day is True
    assert result.ingested == 960
    assert result.scored == 273
    assert result.headline == "Asing keluar dari Finance"
    stages["ingest"].assert_called_once()
    stages["score"].assert_called_once()
    stages["report"].assert_called_once()


def test_pipeline_stops_after_ingest_on_non_trading_day(stages):
    """Sabtu/libur: IDX balas nol baris. Jangan menskor apa pun, jangan bakar kuota Gemini."""
    stages["ingest"].return_value = IngestResult(date=TARGET, trading_day=False)

    result = run_daily_pipeline(TARGET, db=object())

    assert result.trading_day is False
    assert result.scored == 0
    stages["score"].assert_not_called()
    stages["report"].assert_not_called()


def test_pipeline_skips_report_when_gemini_not_configured(stages):
    """GEMINI_API_KEY belum ada: skor tetap dihitung, laporan dilewati tanpa galat.

    Data numerik jauh lebih berharga daripada narasinya — pipeline tak boleh gagal
    total hanya karena LLM-nya belum siap.
    """
    stages["configured"].return_value = False

    result = run_daily_pipeline(TARGET, db=object())

    assert result.scored == 273
    assert result.headline is None
    assert result.report_skipped is True
    stages["report"].assert_not_called()


def test_pipeline_survives_report_failure(stages):
    """Gemini tumbang tak boleh membatalkan skor yang sudah tersimpan."""
    stages["report"].side_effect = LlmError("Gemini galat 503")

    result = run_daily_pipeline(TARGET, db=object())

    assert result.scored == 273
    assert result.headline is None
    assert "503" in result.report_error


def test_pipeline_broadcasts_after_writing_report(stages):
    result = run_daily_pipeline(TARGET, db=object())

    assert result.broadcast_sent == 2
    stages["broadcast"].assert_called_once()


def test_pipeline_survives_telegram_failure(stages):
    """Telegram tumbang tak boleh menjatuhkan pipeline — skornya sudah tersimpan."""
    stages["broadcast"].side_effect = RuntimeError("bot diblokir")

    result = run_daily_pipeline(TARGET, db=object())

    assert result.scored == 273
    assert result.broadcast_sent == 0


def test_pipeline_does_not_broadcast_on_a_quiet_day(stages, mocker):
    """Supervisor menilai hari ini membosankan: laporan tetap disimpan, Telegram diam."""
    stages["report"].return_value = mocker.Mock(
        headline="Pasar sepi",
        context={"broadcast": {"worthy": False, "reason": "hari tenang"}},
    )

    result = run_daily_pipeline(TARGET, db=object())

    assert result.headline == "Pasar sepi"
    assert result.broadcast_sent == 0
    stages["broadcast"].assert_not_called()


def test_pipeline_does_not_broadcast_without_report(stages):
    """Tanpa laporan tak ada yang bisa dikirim — jangan repotkan Telegram."""
    stages["configured"].return_value = False

    run_daily_pipeline(TARGET, db=object())

    stages["broadcast"].assert_not_called()


def test_pipeline_can_skip_report_on_request(stages):
    result = run_daily_pipeline(TARGET, db=object(), with_report=False)

    assert result.report_skipped is True
    stages["report"].assert_not_called()
    stages["configured"].assert_not_called()   # jangan repot memeriksa key yang tak akan dipakai
