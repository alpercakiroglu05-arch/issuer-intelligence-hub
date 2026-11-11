"""Smoke tests: run `pytest` before every merge to main.

Tests that need data/daily_features.parquet are skipped when the file is missing
(data is not in git - copy it from the shared OneDrive folder).
"""
import os

import pytest

os.environ["LLM_PROVIDER"] = "none"  # tests never call a real LLM

from config import DATA_DIR  # noqa: E402

HAS_DATA = (DATA_DIR / "daily_features.parquet").exists()
needs_data = pytest.mark.skipif(not HAS_DATA, reason="data/daily_features.parquet missing")


def test_classify_event_timing():
    from ingest.build_events import classify
    assert classify("07:00") == "pre_open"
    assert classify("14:12") == "intraday"
    assert classify("18:30") == "post_close"
    assert classify("") == "unknown"


def test_template_narrative_works_without_llm():
    from ai.narrate import narrate
    card = {
        "name": "TEST AG", "index": "SDAX", "event": {"reaction_day": "2026-02-11"},
        "price": {"ret": -0.31, "peer_ret": -0.01, "abn_ret": -0.30},
        "volume": {"ratio": 20.1}, "liquidity": {"xlm_25k_bps": 48.0, "ratio": 1.0},
        "participants": {"agent_aggr_imbalance": -0.44},
    }
    assert "-30.0%" in narrate(card, "en")
    assert "unternehmensspezifisch" in narrate(card, "de")


@needs_data
def test_impact_card_known_values():
    """Gerresheimer, 11 Feb 2026: values checked against the raw trade data."""
    from engine.data import isin_of
    from engine.impact import impact_card
    card = impact_card(isin_of("GXI"), "2026-02-11")
    assert card["price"]["ret"] == pytest.approx(-0.314, abs=0.002)
    assert card["price"]["abn_ret"] == pytest.approx(-0.305, abs=0.002)
    assert card["volume"]["ratio"] == pytest.approx(20.1, abs=0.5)


@needs_data
def test_flows_match_turnover():
    """One-sided flow total must equal Xetra on-book turnover (validates the flow mapping)."""
    from engine.data import daily
    d = daily().dropna(subset=["flow_total_eur", "turnover_eur"])
    ratio = (d["flow_total_eur"] / d["turnover_eur"]).median()
    assert ratio == pytest.approx(1.0, abs=0.01)


@needs_data
def test_dashboard_functions_run_for_heroes():
    from config import HERO_TICKERS
    from engine import baseline
    from engine.data import isin_of
    for t in HERO_TICKERS:
        k = baseline.kpis(isin_of(t))
        assert k["ticker"] == t
        assert len(baseline.profile(isin_of(t))) > 100
