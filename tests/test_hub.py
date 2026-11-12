"""The web UI's data contracts (web/hub): periods 1M / 3M / YTD / 1Y, the comparison counts, the evidence statuses,
the agent's period tool and the summary wording. No real LLM is called."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from config import DATA_DIR

pytestmark = pytest.mark.skipif(not (DATA_DIR / "daily_features.parquet").exists(), reason="data missing")
EVD = "DE0005470306"


def _server():
    spec = importlib.util.spec_from_file_location("web_server_hub", Path(__file__).resolve().parents[1] / "web" / "server.py")
    srv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(srv)
    return srv


def test_periods_follow_the_data_coverage():
    from engine import data, market
    p = {x["key"]: x for x in market.periods()}
    dates = sorted(data.daily()["date"].unique())
    assert p["1m"]["available"] and p["1m"]["days"] == 21 and p["3m"]["days"] == 63
    assert p["ytd"]["from"] == str(pd.Timestamp(dates[0]).date()) and p["ytd"]["note"]       # 31 Dec close missing: said
    assert not p["1y"]["available"] and "252" in p["1y"]["reason"]                           # never silently shortened
    with pytest.raises(ValueError):
        market.versus_market(EVD, "1y")


@pytest.mark.parametrize("period", ["1m", "3m", "ytd"])
def test_period_return_is_last_close_over_start_close(period):
    from engine import data, market
    pr = market.versus_market(EVD, period)["price"]
    px = data.stock(EVD).set_index("date")["price"]
    assert pr["close_start"] == pytest.approx(px[pd.Timestamp(pr["start_close"])])
    assert pr["stock"] == pytest.approx(pr["close_end"] / pr["close_start"] - 1, abs=1e-6)
    assert "not adjusted" in pr["basis"]


def test_ytd_lists_the_ex_dividend_day():
    from engine import market
    assert market.versus_market(EVD, "ytd")["price"]["ex_dividend_days"] == ["2026-05-28"]


def test_compare_counts_every_index_choice():
    srv = _server()
    t = srv.compare_table("FY", "MDAX")
    assert t["counts"]["ALL"] == t["counts"]["DAX"] + t["counts"]["MDAX"] + t["counts"]["SDAX"]
    assert t["n"] == t["counts"]["MDAX"] and t["type_counts"]["FY"] == t["counts"]["ALL"]
    assert {r["index"] for r in t["rows"]} <= {"MDAX"}


def test_issuer_series_carries_the_peer_move():
    from engine import data
    s = _server().issuer(EVD)["series"]
    raw = data.stock(EVD).set_index("date")["peer_ret"]
    i = 10
    assert s["peer_ret"][i] == pytest.approx(raw[pd.Timestamp(s["date"][i])], abs=1e-6)


def test_status_lists_the_periods_and_root_is_the_hub():
    srv = _server()
    assert (srv.WEB / "hub" / "index.html").exists()
    src = (Path(srv.__file__)).read_text(encoding="utf-8")
    assert '"/hub/index.html"' in src and '"periods": market.periods()' in src


def test_evidence_missing_evidence_is_not_a_contradiction():
    from engine import data, evidence
    ev = data.events()
    # EVD 27 Mar (FY results): no index event or expiry -> no sign, not "contradicted"
    fy = ev[ev["event_id"] == "EVD_FY_20260326"].iloc[0].to_dict()
    c = evidence.brief(EVD, "2026-03-27", fy)["en"]["claims"]
    assert c["technical"]["verdict"] == "no_evidence" and "MSCI" in c["technical"]["text"]
    # EVD 31 Aug: the calendar lists the MSCI deletion, so index trading is consistent with the data
    ix = ev[ev["event_id"].str.startswith("EVD_INDEX")].iloc[0].to_dict()
    assert evidence.brief(EVD, "2026-08-31", ix)["en"]["claims"]["technical"]["verdict"] == "supported"
    assert set(evidence.VERDICTS) == {"supported", "partly", "contradicted", "no_evidence", "not_testable"}


def test_evidence_statuses_follow_the_figures():
    from engine import data, evidence, impact
    for e in data.events().to_dict("records"):
        day = str(pd.Timestamp(e["reaction_day"]).date())
        card = impact.impact_card(e["isin"], day, e)
        cl = evidence.brief(e["isin"], day, e, card)["en"]["claims"]
        p, v, li = card["price"], card["volume"], card["liquidity"]
        big = p["abn_ret_z"] is not None and abs(p["abn_ret_z"]) >= evidence.NORMAL_MOVE_Z
        if not big and (v["ratio"] or 0) < evidence.REACTION_VOL:     # no reaction -> the announcement is not "supported"
            assert cl["announcement"]["verdict"] != "supported", e["event_id"]
        if cl["overreaction"]["verdict"] == "supported":               # a reversal needs an outsized move first
            assert big, e["event_id"]
        if cl["thin"]["verdict"] == "contradicted":                     # measured: turnover not low and cost not high
            assert v["ratio"] >= 1.0 and not (li["ratio"] is not None and li["ratio"] >= 1.5), e["event_id"]


def test_agent_period_tool_and_unavailable_period():
    from ai import agent
    r = agent.share_performance(EVD, "3m")
    assert r["period"] == "3M" and r["difference_pp"] == pytest.approx((r["share_return"] - r["index_peers_return"]) * 100, abs=0.06)
    bad = agent.share_performance(EVD, "1y")
    assert "error" in bad and {p["key"] for p in bad["available_periods"]} == {"1m", "3m", "ytd"}


@pytest.mark.parametrize("q, period", [("How did our share perform over the last 3 months?", "3m"),
                                       ("Wie lief die Aktie seit Jahresbeginn?", "ytd"),
                                       ("What was our return over the past year?", "1y"),
                                       ("Performance in the last month?", "1m")])
def test_agent_fallback_answers_performance_questions(q, period):
    from ai import agent
    assert agent.perf_period(q.lower()) == period
    r = agent.fallback(q, EVD, {"period": "ytd"}, "de" if "Wie" in q else "en")
    assert [s["tool"] for s in r["steps"]] == ["share_performance"] and r["check"]["unsupported"] == []
    if period == "1y":
        assert "not covered" in r["text"]


def test_summary_never_calls_xlm_a_spread(monkeypatch):
    from ai import llm, narrate
    from engine import impact

    class Msg:
        content = "The share moved -23.2 %, its index peers -1.5 %, so the stock-specific move was -21.7 %. The spread was 1.3x normal."
        cached = False
    monkeypatch.setattr(llm, "chat", lambda *a, **k: Msg())
    card = impact.impact_card(EVD, "2026-03-27")
    out = narrate.narrate_with_meta(card, "en")
    assert out["source"] == "template" and any("spread" in b for b in out["rejected"])
    assert "3) trading cost (XLM)" in narrate.system_prompt("en")
