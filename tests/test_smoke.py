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


HAS_BARS = (DATA_DIR / "intraday_bars.parquet").exists()


@pytest.mark.skipif(not (HAS_DATA and HAS_BARS), reason="intraday_bars.parquet missing")
def test_intraday_bars_match_daily_turnover():
    """Sum of 1-min bars per day must equal Xetra on-book turnover."""
    import pandas as pd
    from engine.data import daily, intraday
    b = intraday().copy()
    b["date"] = b["ts_local"].dt.tz_localize(None).dt.normalize()
    s = b.groupby(["isin", "date"])["volume_eur"].sum().rename("bars").reset_index()
    m = s.merge(daily()[["isin", "date", "turnover_eur"]], on=["isin", "date"])
    assert (m["bars"] / m["turnover_eur"]).median() == pytest.approx(1.0, abs=0.001)


@pytest.mark.skipif(not (HAS_DATA and HAS_BARS), reason="intraday_bars.parquet missing")
def test_impact_card_intraday_block():
    """CTS Eventim, 27 Mar 2026: EUR ~25.8m in the closing auction (checked against raw trades)."""
    from engine.data import isin_of
    from engine.impact import impact_card
    i = impact_card(isin_of("EVD"), "2026-03-27")["intraday"]
    assert i is not None
    assert i["close_auction_eur"] == pytest.approx(25.8e6, rel=0.02)


@pytest.mark.skipif(not (HAS_DATA and HAS_BARS), reason="intraday_bars.parquet missing")
def test_news_onset_heroes():
    """Onset minute on the hero days (checked by eye against the 1-min bars)."""
    from engine.data import isin_of
    from engine.impact import impact_card
    from engine.onset import onset
    evt = onset(isin_of("EVT"), "2026-07-14")      # -21% already in pre-market trading at 08:02
    assert (evt["time"], evt["session"], evt["inferred_timing"]) == ("08:02", "pre_market", "pre_open")
    hdd = onset(isin_of("HDD"), "2026-10-29")      # intraday news around noon
    assert (hdd["time"], hdd["inferred_timing"]) == ("12:02", "intraday")
    card = impact_card(isin_of("EVT"), "2026-07-14")  # no announcement time -> timing filled from trading
    assert card["event"]["timing"] == "pre_open"
    assert card["event"]["timing_source"] == "inferred_from_trading"


@pytest.mark.skipif(not (HAS_DATA and HAS_BARS), reason="intraday_bars.parquet missing")
def test_auction_block_evd():
    """CTS Eventim, 27 Mar 2026: closing auction uncross at 17:35 = EUR 25.59m, 1.5% below the last trade."""
    from engine.data import isin_of
    from engine.impact import impact_card
    au = impact_card(isin_of("EVD"), "2026-03-27")["auctions"]
    assert au["close_auction_eur"] == pytest.approx(25.59e6, rel=0.005)
    assert au["open_auction_eur"] == pytest.approx(1.16e6, rel=0.01)
    assert au["close_auction_move"] == pytest.approx(-0.0153, abs=0.0005)
    assert au["open_auction_ratio"] > 5 and au["close_auction_ratio"] > 3


@pytest.mark.skipif(not (HAS_DATA and HAS_BARS), reason="intraday_bars.parquet missing")
def test_auction_volumes_match_flows():
    """Opening + closing auction (trade bars) ~ all auction turnover in the flow data (rest: midday/volatility)."""
    from engine.auctions import auction_profile
    from engine.data import intraday, stock
    for isin in intraday()["isin"].unique():
        s, p = stock(isin), auction_profile(isin)
        flow = s[[f"{x}_auct_buy" for x in ("mm", "agent", "prop")]].sum(axis=1)
        r = ((p["open_auction_eur"] + p["close_auction_eur"]) / flow.where(flow > 0)).median()
        assert 0.95 <= r <= 1.001, (isin, r)


@needs_data
def test_compare_matches_card_and_ranks_evd():
    """The comparison table uses the card's own definitions; EVD 27 Mar is a top-3 MDAX move of 2026."""
    from engine import compare
    from engine.data import isin_of
    from engine.impact import impact_card
    card = impact_card(isin_of("EVD"), "2026-03-27")
    m = compare.metrics_all()
    row = m[(m["ticker"] == "EVD") & (m["date"] == "2026-03-27")].iloc[0]
    assert row["vol_ratio"] == pytest.approx(card["volume"]["ratio"], abs=0.01)
    assert row["xlm_ratio"] == pytest.approx(card["liquidity"]["ratio"], abs=0.01)
    assert row["car_0_5"] == pytest.approx(card["price"]["car_0_5"], abs=1e-4)
    c = card["comparison"]
    assert c["group_type"] == "NOTABLE_DAY" and c["group_index"] == "MDAX" and c["n"] >= 100
    assert c["abs_abn_ret_pctile"] >= 0.98 and c["rank_abs_abn_ret"] <= 3
    typed = compare.same_type_events("TBD")
    assert set(typed["ticker"]) >= {"EVD", "GXI"}
