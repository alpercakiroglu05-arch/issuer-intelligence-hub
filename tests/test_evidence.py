"""Evidence brief + explanation check (engine/evidence.py), canonical "x normal", assistant routing and the
own-calendar statuses. No real LLM is called."""
import pandas as pd
import pytest

from config import DATA_DIR

HAS_DATA = (DATA_DIR / "daily_features.parquet").exists()
pytestmark = pytest.mark.skipif(not HAS_DATA, reason="data/daily_features.parquet missing")
EVD, EVD_FY = "DE0005470306", "EVD_FY_20260326"


def _event(isin, event_id):
    from engine import data
    e = data.events()
    return e[(e["isin"] == isin) & (e["event_id"] == event_id)].iloc[0].to_dict()


def test_evd_results_day_claims():
    from engine import evidence
    b = evidence.brief(EVD, "2026-03-27", _event(EVD, EVD_FY))
    c = b["en"]["claims"]
    assert c["market"]["verdict"] == "contradicted"          # -23.2% vs peers -1.5%
    assert c["thin"]["verdict"] == "contradicted"            # 8.6x normal turnover
    assert c["investors"]["verdict"] == "not_testable"       # Xetra data does not identify investor types
    assert c["announcement"]["verdict"] == "supported" and "not proof" in c["announcement"]["text"]
    assert c["overreaction"]["verdict"] == "contradicted"    # day 0..+5 kept falling
    assert set(c) == set(evidence.CLAIMS) and set(b["de"]["claims"]) == set(evidence.CLAIMS)
    assert [s["key"] for s in b["en"]["sections"]] == ["changed", "market", "trading", "unusual", "unknown", "next"]


def test_post_close_news_has_no_same_day_lag():
    """FY results at 17:45 on 26 Mar react on 27 Mar: no 'minutes before publication' across days."""
    from engine import evidence, impact
    card = impact.impact_card(EVD, "2026-03-27", _event(EVD, EVD_FY))
    assert card["intraday"]["onset"]["lag_minutes"] is None
    assert evidence.brief(EVD, "2026-03-27", _event(EVD, EVD_FY), card)["en"]["claims"]["leak"]["verdict"] != "supported"


def test_intraday_ad_hoc_lag_is_measured():
    from engine import data, evidence
    hdd = data.isin_of("HDD")
    b = evidence.brief(hdd, "2026-10-29", _event(hdd, "HDD_GUIDANCE_20261029"))["en"]
    assert "2 min after publication" in b["claims"]["announcement"]["text"]
    assert b["claims"]["overreaction"]["verdict"] == "not_testable"   # day +5 is after the end of the data


def test_brief_figures_come_from_the_card():
    from ai.checks import unsupported_numbers
    from engine import evidence, impact
    card = impact.impact_card(EVD, "2026-03-27", _event(EVD, EVD_FY))
    b = evidence.brief(EVD, "2026-03-27", _event(EVD, EVD_FY), card)
    text = " ".join(p for s in b["en"]["sections"] for p in s["points"] if s["key"] in ("changed", "trading"))
    assert unsupported_numbers(text, {"card": card, "facts": b["facts"]}) == []


@pytest.mark.parametrize("text,ids", [
    ("The whole market sold off that day", ["market"]),
    ("Funds and short sellers dumped the stock", ["investors"]),
    ("Thin trading exaggerated the move", ["thin"]),
    ("Das war eine Übertreibung, die sich erholt hat", ["overreaction"]),
    ("Our share price is nice", []),
])
def test_classify(text, ids):
    from engine import evidence
    assert evidence.classify(text) == ids


def test_one_turnover_ratio_everywhere():
    """HDD 29 Oct: card, dashboard unusual days and assistant show the same 'x normal' (was 7.31 vs 7.66)."""
    import importlib.util
    from pathlib import Path

    from ai import agent
    from engine import data, impact
    hdd = data.isin_of("HDD")
    card = impact.impact_card(hdd, "2026-10-29")["volume"]["ratio"]
    spec = importlib.util.spec_from_file_location("web_server_ev", Path(__file__).resolve().parents[1] / "web" / "server.py")
    srv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(srv)
    ep = next(a for a in srv.issuer(hdd)["anomalies"] if a["peak_date"] == "2026-10-29")
    ud = next(d for d in agent.unusual_days(hdd, limit=20)["days"] if d["day"] == "2026-10-29")
    assert round(ep["peak_vol_ratio"], 2) == round(ud["turnover_x_normal"], 2) == round(card, 2)


@pytest.mark.parametrize("ctx", [{"page": "dashboard"}, {"page": "card", "day": "2026-03-27", "event_id": EVD_FY}])
def test_sector_spread_question_routes_to_peers(ctx):
    from ai import agent
    r = agent.run("How do our spreads compare with our sector?", EVD, context=ctx)
    assert [s["tool"] for s in r["steps"]] == ["peer_benchmark"] and "Sector" in r["text"]


def test_explanation_question_routes_to_the_check():
    from ai import agent
    r = agent.run("Was this just the market falling?", EVD, context={"page": "card", "day": "2026-03-27", "event_id": EVD_FY})
    assert [s["tool"] for s in r["steps"]] == ["check_explanation"] and "contradicted" in r["text"]
    assert r["check"]["unsupported"] == []


def test_calendar_statuses():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("web_server_cal", Path(__file__).resolve().parents[1] / "web" / "server.py")
    srv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(srv)
    ev = srv.calendar({"isin": EVD, "events": [
        {"date": "2026-03-26", "time": "17:45", "type": "FY"}, {"date": "2025-12-01", "type": "FY"},
        {"date": "2026-12-01", "type": "Q3"}, {"date": "31/02/2026"}, {"date": "2026-03-27", "time": "25:99"}]})["events"]
    assert [e["status"] for e in ev] == ["matched", "before_data", "after_data", "invalid", "matched"]
    assert ev[0]["reaction_day"] == "2026-03-27" and "after the 17:35" in ev[0]["rule"]
    assert ev[4]["time_local"] == "" and ev[4]["reaction_day"] == "2026-03-27"   # bad time ignored, not guessed
    assert pd.Timestamp(ev[0]["reaction_day"]).day_of_week < 5


def test_pre_event_volume_ignores_days_the_market_explains():
    """EVD 20 Mar 2026 was a quarterly expiry with market-wide volume: not a hint of early news for 27 Mar."""
    from engine import baseline, evidence
    assert baseline.market_context(EVD, "2026-03-20")          # the expiry day is flagged
    fx = evidence._facts(EVD, "2026-03-27", None)
    assert fx["pre_max_vol_day"] != "2026-03-20"
    en = evidence.brief(EVD, "2026-03-27", _event(EVD, EVD_FY))["en"]
    assert not any("20 Mar" in p for s in en["sections"] for p in s["points"])

