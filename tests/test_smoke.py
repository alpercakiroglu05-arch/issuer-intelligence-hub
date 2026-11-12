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
    assert "−30.0%" in narrate(card, "en")
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
    from engine.data import daily, intraday, intraday_isins
    d = daily()[["isin", "date", "turnover_eur"]]
    for isin in intraday_isins():   # one stock at a time (the full file has millions of rows)
        b = intraday(isin)
        s = b.groupby(b["ts_local"].dt.tz_localize(None).dt.normalize())["volume_eur"].sum()
        m = d[d["isin"] == isin].set_index("date")["turnover_eur"]
        r = (s / m).dropna()
        # len > 0, not 213: a stock that changed ISIN (FRE, QIA) has its days split over two ISINs
        assert len(r) > 0 and r.median() == pytest.approx(1.0, abs=0.001), (isin, r.median())


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
    from engine.data import intraday_isins, stock
    for isin in intraday_isins():
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
    assert c["rank_of"] == c["n"] + 1   # the rank counts this day too
    typed = compare.same_type_events("H1")
    assert set(typed["ticker"]) >= {"ADS", "SAP", "EVD"} and len(typed) >= 30


def test_events_csv_is_clean():
    """Every researched event has a known type, a source link and a parsable date/time; no duplicates."""
    import pandas as pd
    from config import EVENTS_CSV
    e = pd.read_csv(EVENTS_CSV, dtype=str).fillna("")
    types = {"FY", "Q1", "H1", "Q3", "DIVIDEND_EX", "AGM", "ADHOC", "GUIDANCE", "MA", "CMD", "INDEX"}
    assert set(e["type"]) <= types
    assert (e["source_url"].str.startswith("http")).all()
    assert pd.to_datetime(e["date"], format="%Y-%m-%d").notna().all()
    assert e["time_local"].str.fullmatch(r"(\d\d:\d\d)?").all()
    assert not e.duplicated(["ticker", "type", "date"]).any()
    assert set(e["verified"]) <= {"0", "1"}


@needs_data
def test_events_match_trading_days_and_cards():
    """All events map to a trading day of a known stock; EVD's FY release (26 Mar 17:45) reacts on 27 Mar."""
    from engine.data import events, isin_of
    from engine.impact import impact_card
    ev = events()
    assert ev["isin"].notna().all() and ev["reaction_day"].notna().all()
    fy = ev[(ev["ticker"] == "EVD") & (ev["type"] == "FY")].iloc[0]
    assert fy["timing"] == "post_close" and str(fy["reaction_day"].date()) == "2026-03-27"
    h1 = ev[(ev["ticker"] == "EVD") & (ev["type"] == "H1")].iloc[0]   # 20 Aug 17:45 -> reacts 21 Aug
    card = impact_card(isin_of("EVD"), h1["reaction_day"], h1.to_dict())
    assert card["event"]["reaction_day"] == "2026-08-21" and card["event"]["timing_source"] == "announcement"
    assert card["comparison"]["group_type"] == "H1" and card["comparison"]["n"] >= 30


@needs_data
def test_xlm_cost_curve():
    """Order-size cost curve: cost rises with size, SAP's book absorbs EUR 10m, HDD's stops at EUR 500k."""
    from engine.data import isin_of
    from engine.xlm import cost_curve, curve_summary
    c = cost_curve(isin_of("SAP"))
    s = c["stock_bps"].dropna()
    assert s.is_monotonic_increasing and curve_summary(c)["largest_absorbed_eur"] == 10e6
    assert curve_summary(cost_curve(isin_of("HDD"), by="size"))["largest_absorbed_eur"] == 500e3
    assert curve_summary(cost_curve(isin_of("GXI")))["largest_absorbed_eur"] is None   # left the SDAX: no XLM
