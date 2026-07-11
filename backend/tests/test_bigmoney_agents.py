"""Tes tim agen: pekerja berita, pekerja aliran, kritikus, supervisor.

Seluruh LLM dan HTTP di-mock. Yang paling penting diuji di sini bukan kualitas prosa,
melainkan KETAHANAN: tiap pekerja boleh mati sendiri-sendiri tanpa menjatuhkan laporan,
dan tak satu pun jalur boleh menghapus skor yang sudah tersimpan.
"""
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import Base
from services.bigmoney.agents import critic, flow_worker, news_worker, supervisor
from services.bigmoney.llm import LlmError

TARGET = date(2026, 7, 10)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _seed(db, *, foreign_net_value=-285_410_584_421, conviction="WATCH", weight_set="VOLATILE"):
    db.add(models.Stock(ticker="CUAN", name="Petrindo Jaya Kreasi Tbk.", sector="Energy"))
    db.add(models.BigMoneyMarketRegime(
        date=TARGET, volatility_regime="VOLATILE", trend_regime="BULL", weight_set=weight_set,
        market_return_pct=0.08, breadth=0.6, total_foreign_net_value=foreign_net_value,
        sector_rotation={"Energy": 61_200_000_000, "Finance": -178_100_000_000}))
    db.add(models.BigMoneyTopAccumulation(
        date=TARGET, rank=1, ticker="CUAN", composite=85.0, conviction=conviction, phase="AKUMULASI"))
    db.add(models.BigMoneyScore(
        date=TARGET, ticker="CUAN", composite=85.0, conviction=conviction, phase="AKUMULASI",
        weight_set=weight_set, days_confirmed=2, flags={"divergence": False, "pump_dump_risk": False}))
    db.add(models.BigMoneyStockDaily(
        date=TARGET, ticker="CUAN", close=1500.0, volume=1_000_000, value=2_000_000_000,
        change_pct=1.2, foreign_net=500, foreign_net_value=16_230_000_000, avg_ticket=2_000_000.0))
    db.commit()


@pytest.fixture
def agents(mocker):
    """Semua pekerja sukses secara default; tiap tes merusak satu."""
    return {
        "news_fetch": mocker.patch(
            "services.bigmoney.agents.supervisor.fetch_news",
            return_value=[{"ticker": "CUAN", "title": "Prajogo jual 1,7 miliar saham CUAN",
                           "url": "https://x/1", "source": "IDNFinancials", "published": "2026-07-09"}]),
        "news": mocker.patch("services.bigmoney.agents.supervisor.news_worker.summarize",
                             return_value="CUAN: pendiri melepas 1,7 miliar lembar."),
        "flow": mocker.patch("services.bigmoney.agents.supervisor.flow_worker.interpret",
                             return_value="Asing keluar dari pasar, energi bertahan."),
        "write": mocker.patch("services.bigmoney.agents.supervisor.generate_text",
                              return_value="Asing keluar, energi bertahan\n\nIsi laporan."),
        "critic": mocker.patch("services.bigmoney.agents.supervisor.critic.review",
                               return_value=critic.Verdict(passed=True)),
    }


# --- pekerja berita ----------------------------------------------------------

def test_news_prompt_forbids_inventing_causes():
    prompt = news_worker.render_prompt({"CUAN": [{"title": "Prajogo jual saham", "source": "IDN"}]}).lower()

    assert "jangan dikarang" in prompt or "jangan memaksakan" in prompt


def test_news_prompt_forbids_price_prediction():
    """Pekerja berita melaporkan, bukan meramal."""
    prompt = news_worker.render_prompt({"CUAN": [{"title": "x", "source": "y"}]}).lower()

    assert "meramal" in prompt


def test_news_worker_returns_none_without_articles(mocker):
    """Tanpa berita, jangan bakar token untuk bertanya soal daftar kosong."""
    called = mocker.patch("services.bigmoney.agents.news_worker.generate_text")

    assert news_worker.summarize({"CUAN": [], "GOTO": []}) is None
    called.assert_not_called()


def test_news_worker_returns_none_when_llm_fails(mocker):
    mocker.patch("services.bigmoney.agents.news_worker.generate_text",
                 side_effect=LlmError("kuota habis"))

    assert news_worker.summarize({"CUAN": [{"title": "x", "source": "y"}]}) is None


# --- pekerja aliran ----------------------------------------------------------

def test_flow_prompt_forbids_recomputing_numbers():
    """Angkanya sudah teruji; pekerja ini menerjemahkan, bukan menghitung."""
    context = {"date": "2026-07-10", "regime": {"volatility_regime": "VOLATILE",
               "trend_regime": "BULL", "weight_set": "VOLATILE", "market_return_pct": 0.1,
               "breadth": 0.5, "total_foreign_net_value": -1},
               "previous": None, "top_accumulation": [], "sector_inflow": [], "sector_outflow": []}

    prompt = flow_worker.render_prompt(context).lower()

    assert "jangan hitung ulang" in prompt


def test_flow_worker_returns_none_when_llm_fails(mocker, db):
    _seed(db)
    from services.bigmoney.report_generator import build_context
    mocker.patch("services.bigmoney.agents.flow_worker.generate_text",
                 side_effect=LlmError("gagal"))

    assert flow_worker.interpret(build_context(TARGET, db)) is None


# --- kritikus ----------------------------------------------------------------

def _ctx(db):
    from services.bigmoney.report_generator import build_context
    return build_context(TARGET, db)


def test_critic_passes_consistent_draft(mocker, db):
    _seed(db)
    mocker.patch("services.bigmoney.agents.critic.generate_text", return_value="LOLOS")

    verdict = critic.review("Asing keluar dari pasar.", _ctx(db))

    assert verdict.passed is True
    assert verdict.issues is None


def test_critic_flags_contradiction(mocker, db):
    """Draf bilang asing memborong padahal net asing pasar minus Rp285 miliar."""
    _seed(db)
    mocker.patch("services.bigmoney.agents.critic.generate_text",
                 return_value="Draf menyebut asing memborong, padahal net asing pasar negatif.")

    verdict = critic.review("Asing memborong pasar hari ini.", _ctx(db))

    assert verdict.passed is False
    assert "negatif" in verdict.issues


def test_critic_failure_does_not_block_report(mocker, db):
    """Pemeriksa yang mati berhenti menjaga — ia tidak boleh ikut membatalkan laporan."""
    _seed(db)
    mocker.patch("services.bigmoney.agents.critic.generate_text", side_effect=LlmError("mati"))

    verdict = critic.review("apa pun", _ctx(db))

    assert verdict.passed is True
    assert verdict.skipped is True


def test_critic_prompt_treats_news_facts_as_legitimate(db):
    """Kasus nyata 2026-07-10: kritikus memprotes dividen BSSR Rp486 yang sebenarnya benar.

    Angka itu berasal dari berita, bukan engine. Kritikus yang buta terhadap berita akan
    menghukum justru bagian laporan yang paling berharga.
    """
    _seed(db)

    prompt = critic.render_prompt("draf", _ctx(db), news="BSSR membagikan dividen Rp486/lembar.")

    assert "BSSR membagikan dividen Rp486/lembar." in prompt
    assert "sumber sah" in prompt.lower()


def test_critic_receives_news_from_supervisor(db, agents):
    _seed(db)

    supervisor.run_report(TARGET, db)

    assert agents["critic"].call_args.kwargs["news"] == "CUAN: pendiri melepas 1,7 miliar lembar."


def test_critic_prompt_targets_facts_not_style(mocker, db):
    _seed(db)
    prompt = critic.render_prompt("draf", _ctx(db)).lower()

    assert "jangan mengkritik gaya bahasa" in prompt
    assert "nasihat investasi" in prompt


# --- supervisor --------------------------------------------------------------

def test_supervisor_dispatches_all_workers_and_saves_report(db, agents):
    _seed(db)

    report = supervisor.run_report(TARGET, db)

    assert report.headline == "Asing keluar, energi bertahan"
    agents["news"].assert_called_once()
    agents["flow"].assert_called_once()
    agents["critic"].assert_called_once()
    assert db.query(models.BigMoneyDailyReport).count() == 1


def test_supervisor_stores_agent_audit_trail(db, agents):
    """Tanpa jejak kerja tiap pekerja, laporan yang keliru tak bisa diperiksa ulang."""
    _seed(db)

    report = supervisor.run_report(TARGET, db)

    trail = report.context["agents"]
    assert "Prajogo" in trail["news"]["CUAN"][0]["title"]
    assert trail["news_summary"]
    assert trail["flow_reading"]
    assert trail["critic"]["passed"] is True


def test_supervisor_rewrites_when_critic_rejects(db, agents):
    """Draf yang bertentangan dengan angka harus ditulis ulang, bukan disimpan begitu saja."""
    _seed(db)
    agents["critic"].return_value = critic.Verdict(passed=False, issues="Klaim asing memborong salah.")
    agents["write"].side_effect = [
        "Asing memborong\n\nDraf keliru.",
        "Asing keluar\n\nDraf perbaikan.",
    ]

    report = supervisor.run_report(TARGET, db)

    assert report.headline == "Asing keluar"
    assert agents["write"].call_count == 2
    assert "Klaim asing memborong salah." in agents["write"].call_args.args[0]
    assert report.context["agents"]["critic"]["passed"] is False


def test_factcheck_forces_rewrite_even_when_critic_is_blocked(db, agents):
    """Kasus nyata 2026-07-10: kritikus diblokir Gemini, tuduhan pump-dump palsu lolos.

    Pemeriksa deterministik tak bisa diblokir — ia harus tetap memaksa penulisan ulang.
    """
    _seed(db)
    agents["critic"].return_value = critic.Verdict(passed=True, skipped=True)   # kritikus mati
    agents["write"].side_effect = [
        "Waspada\n\nCUAN rentan risiko pump-and-dump.",   # tuduhan palsu: flag = False
        "Asing keluar\n\nCUAN memimpin akumulasi.",
    ]

    report = supervisor.run_report(TARGET, db)

    assert agents["write"].call_count == 2
    assert "pump-and-dump" in agents["write"].call_args.args[0]   # kesalahannya disodorkan balik
    assert report.narrative == "CUAN memimpin akumulasi."
    assert report.context["agents"]["factcheck"]["passed"] is True


def test_factcheck_records_when_rewrite_still_lies(db, agents):
    """Revisi yang tetap melanggar tak boleh diam-diam dianggap beres."""
    _seed(db)
    agents["critic"].return_value = critic.Verdict(passed=True, skipped=True)
    agents["write"].side_effect = [
        "Judul\n\nCUAN rentan pump-and-dump.",
        "Judul\n\nCUAN tetap rentan pump-and-dump.",   # masih bohong
    ]

    report = supervisor.run_report(TARGET, db)

    assert report.context["agents"]["factcheck"]["passed"] is False
    assert any("CUAN" in issue for issue in report.context["agents"]["factcheck"]["issues"])


def test_clean_draft_is_not_rewritten(db, agents):
    _seed(db)

    supervisor.run_report(TARGET, db)

    assert agents["write"].call_count == 1


def test_supervisor_survives_news_worker_failure(db, agents):
    """Berita adalah pelengkap; tanpanya laporan tetap terbit."""
    _seed(db)
    agents["news"].return_value = None

    report = supervisor.run_report(TARGET, db)

    assert report.headline
    assert report.context["agents"]["news_summary"] is None


def test_supervisor_falls_back_when_writer_fails(db, agents, mocker):
    """Penulis tak tergantikan — jatuh ke laporan satu-panggilan, jangan diam saja."""
    _seed(db)
    agents["write"].side_effect = LlmError("kuota habis")
    fallback = mocker.patch("services.bigmoney.agents.supervisor.generate_report",
                            return_value=mocker.Mock(headline="Laporan cadangan"))

    report = supervisor.run_report(TARGET, db)

    assert report.headline == "Laporan cadangan"
    fallback.assert_called_once()


def test_supervisor_returns_none_when_day_not_scored(db, agents):
    assert supervisor.run_report(TARGET, db) is None
    agents["write"].assert_not_called()


def test_supervisor_is_idempotent(db, agents):
    _seed(db)

    supervisor.run_report(TARGET, db)
    supervisor.run_report(TARGET, db)

    assert db.query(models.BigMoneyDailyReport).filter_by(date=TARGET).count() == 1


# --- kelayakan kabar ---------------------------------------------------------

def test_strong_conviction_makes_the_day_newsworthy(db, agents):
    _seed(db, conviction="STRONG")

    report = supervisor.run_report(TARGET, db)

    assert report.context["broadcast"]["worthy"] is True
    assert "STRONG" in report.context["broadcast"]["reason"]


def test_extreme_foreign_flow_makes_the_day_newsworthy(db, agents):
    _seed(db, conviction="WATCH", foreign_net_value=-900_000_000_000)

    report = supervisor.run_report(TARGET, db)

    assert report.context["broadcast"]["worthy"] is True
    assert "ekstrem" in report.context["broadcast"]["reason"]


def test_regime_change_makes_the_day_newsworthy(db, agents):
    _seed(db, conviction="WATCH", foreign_net_value=-1_000_000_000)
    db.add(models.BigMoneyMarketRegime(
        date=TARGET - timedelta(days=1), volatility_regime="CALM", trend_regime="SIDEWAYS",
        weight_set="CALM", total_foreign_net_value=1_000_000_000))
    db.commit()

    report = supervisor.run_report(TARGET, db)

    assert report.context["broadcast"]["worthy"] is True
    assert "rezim berubah" in report.context["broadcast"]["reason"]


def test_quiet_day_is_saved_but_not_worth_broadcasting(db, agents):
    """Notifikasi harian yang membosankan akan diabaikan — dan alarm yang diabaikan sia-sia."""
    _seed(db, conviction="WATCH", foreign_net_value=-1_000_000_000)

    report = supervisor.run_report(TARGET, db)

    assert report.context["broadcast"]["worthy"] is False
    assert report.headline   # laporannya tetap tersimpan dan tetap bisa dibaca di halaman
