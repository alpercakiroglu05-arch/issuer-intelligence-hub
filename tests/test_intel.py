"""Market-intelligence layer (ai/intel.py): packs are valid, texts are deterministic without a model, and a model
answer is used only if it cites pack items, uses known figures and claims no cause."""
import json
from types import SimpleNamespace

import pytest

from ai import intel, llm

ZAL, EVD, HDD = "DE000ZAL1111", "DE0005470306", "DE0007314007"


@pytest.mark.parametrize("ticker", ["ZAL", "EVD", "HDD"])
def test_pack_is_valid(ticker):
    d = json.loads((intel.INTEL_DIR / f"{ticker}.json").read_text(encoding="utf-8"))
    ids = set()
    for it in d["items"]:
        assert it["id"] not in ids and it["en"] and it["de"] and it["src"]
        assert all(s in d["sources"] for s in it["src"]), it["id"]
        assert it["dir"] in ("pos", "neg", "neutral") and it["kind"]
        ids.add(it["id"])
    for s in d["sources"].values():
        assert s["url"].startswith("https://") and s["publisher"] and len(s["date"]) == 10


def test_event_template_without_model(monkeypatch):
    monkeypatch.setattr(llm, "chat", lambda *a, **k: (_ for _ in ()).throw(llm.LLMUnavailable("off")))
    r = intel.explain_event(ZAL, "2026-05-06", "ZAL_Q1_20260506", "en")
    assert r["source"] == "template" and r["drivers"] and all(d["sources"] for d in r["drivers"])
    assert "pp relative" in r["reaction"] and r["headline"] == intel.pack(ZAL)["events"]["ZAL_Q1_20260506"]["headline_en"]
    assert intel.explain_event(ZAL, "2026-05-06", "NOPE", "en") is None


def test_later_items_are_labelled(monkeypatch):
    monkeypatch.setattr(llm, "chat", lambda *a, **k: (_ for _ in ()).throw(llm.LLMUnavailable("off")))
    r = intel.explain_event(EVD, "2026-03-27", "EVD_FY_20260326", "de")
    assert any(d["timing"] == "later" for d in r["drivers"])   # the LYNX analysis of 30 March


def test_period_and_no_pack(monkeypatch):
    monkeypatch.setattr(llm, "chat", lambda *a, **k: (_ for _ in ()).throw(llm.LLMUnavailable("off")))
    r = intel.explain_period(HDD, "1m", "en")
    assert r["drivers"] and "€25k" in r["trading"]
    assert intel.explain_period("DE0007164600", "1m", "en") is None  # SAP: no research pack


def _fake(answer):
    return lambda *a, **k: SimpleNamespace(content=json.dumps(answer), cached=False)


GOOD = {"headline": "The results were in line with expectations, which is consistent with the fall.",
        "drivers": [{"id": "zal_q1_consensus", "text": "EBIT was slightly above the €63.8m forecast."},
                    {"id": "zal_q1_agentic", "text": "JPMorgan saw no new positives."}],
        "trading": "The share opened +5.4% and lost −6.8% in continuous trading.",
        "shown": "The relative move.", "plausible": "Expectations.", "open": "The weights."}


def test_model_answer_used_when_valid(monkeypatch):
    monkeypatch.setattr(llm, "chat", _fake(GOOD))
    r = intel.explain_event(ZAL, "2026-05-06", "ZAL_Q1_20260506", "en")
    assert r["source"] == "llm" and [d["id"] for d in r["drivers"]] == ["zal_q1_consensus", "zal_q1_agentic"]


@pytest.mark.parametrize("bad", [
    {**GOOD, "drivers": [{"id": "invented", "text": "x"}, {"id": "zal_q1_agentic", "text": "y"}]},   # unknown item
    {**GOOD, "trading": "Turnover was 7.7× normal."},                                                  # unknown figure
    {**GOOD, "headline": "The fall was caused by the margin."},                                        # causal claim
])
def test_model_answer_rejected(monkeypatch, bad):
    monkeypatch.setattr(llm, "chat", _fake(bad))
    r = intel.explain_event(ZAL, "2026-05-06", "ZAL_Q1_20260506", "en")
    assert r["source"] == "template" and r["rejected"]
