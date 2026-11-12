"""IR analyst agent (ai/agent.py) and the own-calendar import (web/server.py). No real LLM is called."""
import importlib.util
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from config import DATA_DIR

HAS_DATA = (DATA_DIR / "daily_features.parquet").exists()
needs_data = pytest.mark.skipif(not HAS_DATA, reason="data/daily_features.parquet missing")
EVD = "DE0005470306"


def test_parse_day_understands_en_de_and_iso():
    from ai.agent import parse_day
    assert parse_day("What happened on 27 Mar?") == "2026-03-27"
    assert parse_day("Was war am 27.03.?") == "2026-03-27"
    assert parse_day("Was war am 27. März?") == "2026-03-27"
    assert parse_day("and on 2026-10-29") == "2026-10-29"
    assert parse_day("Has our liquidity improved?") is None


@needs_data
def test_fallback_answers_from_engine_and_offers_the_card():
    from ai import agent
    r = agent.run("What happened on 27 Mar?", EVD)
    assert r["source"] == "template" and "23.2%" in r["text"]
    assert r["actions"][0]["view"] == "card" and r["actions"][0]["event_id"] == "EVD_FY_20260326"
    assert r["check"]["unsupported"] == [] and r["check"]["total"] > 5


@needs_data
@pytest.mark.parametrize("q", ["Has our liquidity improved?", "How do our spreads compare with our sector?",
                               "What were our biggest moves this year?", "How large an order can the book absorb?",
                               "How did the market react to results?", "Put this card in a report"])
def test_fallback_numbers_all_come_from_tools(q):
    from ai import agent
    r = agent.run(q, EVD, context={"page": "card", "day": "2026-03-27", "event_id": "EVD_FY_20260326"})
    assert r["text"] and r["check"]["unsupported"] == [], (q, r["text"], r["check"])


def _script(*answers):
    call = lambda i, name, args: SimpleNamespace(id=f"c{i}", function=SimpleNamespace(name=name, arguments=json.dumps(args)))  # noqa: E731
    return [SimpleNamespace(content="", tool_calls=[call(1, "impact_card", {"day": "2026-03-27", "event_id": "EVD_FY_20260326"}),
                                                    call(2, "show", {"view": "card", "day": "2026-03-27"})])] + \
           [SimpleNamespace(content=a, tool_calls=None) for a in answers]


def _fake_llm(monkeypatch, script):
    from ai import llm
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "model_name", lambda: "test-model")
    monkeypatch.setattr(llm, "chat", lambda *a, **k: script.pop(0))


@needs_data
def test_tool_calling_loop_repairs_an_invented_figure(monkeypatch):
    """Model calls impact_card + show, writes one invented figure, gets one repair round, then answers cleanly."""
    from ai import agent
    script = _script("The share fell 23.2% (stock-specific -21.7%) on 8.6x normal turnover; 99.9% made up.",
                     "The share fell 23.2% (stock-specific -21.7%) on 8.6x normal turnover, #3 of 215 unusual days.")
    _fake_llm(monkeypatch, script)
    r = agent.run("What happened on 27 March?", EVD, context={"page": "dashboard"})
    assert r["source"] == "llm" and r["model"] == "test-model" and not script
    assert [s["tool"] for s in r["steps"]] == ["impact_card", "show"]
    assert r["actions"] == [{"view": "card", "isin": EVD, "day": "2026-03-27", "event_id": None, "event_type": None, "index": None}]
    assert r["check"]["unsupported"] == [] and "99.9" not in r["text"]


@needs_data
def test_invented_figures_are_never_shown(monkeypatch):
    from ai import agent
    _fake_llm(monkeypatch, _script("The share fell 12.4% on 5.6x turnover.", "Still 12.4% and 5.6x."))
    r = agent.run("What happened on 27 March?", EVD, context={"page": "dashboard"})
    assert r["source"] == "template" and "12.4" not in r["text"] and "rejected" in r["note"]
    assert r["actions"] and r["actions"][0]["view"] == "card"


@needs_data
def test_answer_with_unverified_figure_falls_back(monkeypatch):
    """Same rule as the card summary: an invented figure means the deterministic answer is shown."""
    from ai import agent, llm
    call = lambda i, name, args: SimpleNamespace(id=f"c{i}", function=SimpleNamespace(name=name, arguments=json.dumps(args)))
    script = [
        SimpleNamespace(content="", tool_calls=[call(1, "impact_card", {"day": "2026-03-27", "event_id": "EVD_FY_20260326"})]),
        SimpleNamespace(content="The share fell 23.2% on 8.6x normal turnover; 99.9% made up.", tool_calls=None),
    ]
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "model_name", lambda: "test-model")
    monkeypatch.setattr(llm, "chat", lambda *a, **k: script.pop(0))
    r = agent.run("What happened on 27 March?", EVD, context={"page": "dashboard"})
    assert r["source"] == "template" and r["rejected"] == ["99.9"] and "99.9" not in r["text"]
    assert not r["check"]["unsupported"]          # the deterministic answer passes its own check


@needs_data
def test_answer_that_passes_the_check_is_shown(monkeypatch):
    from ai import agent, llm
    call = lambda i, name, args: SimpleNamespace(id=f"c{i}", function=SimpleNamespace(name=name, arguments=json.dumps(args)))
    script = [
        SimpleNamespace(content="", tool_calls=[call(1, "impact_card", {"day": "2026-03-27", "event_id": "EVD_FY_20260326"})]),
        SimpleNamespace(content="The share moved -23.2% on 8.6x normal turnover.", tool_calls=None),
    ]
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "model_name", lambda: "test-model")
    monkeypatch.setattr(llm, "chat", lambda *a, **k: script.pop(0))
    r = agent.run("What happened on 27 March?", EVD, context={"page": "dashboard"})
    assert r["source"] == "llm" and "rejected" not in r


@needs_data
def test_model_error_falls_back_to_template(monkeypatch):
    from ai import agent, llm
    monkeypatch.setattr(llm, "available", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("gateway down")
    monkeypatch.setattr(llm, "chat", boom)
    r = agent.run("Has our liquidity improved?", EVD)
    assert r["source"] == "template" and r["text"] and "model error" in r["note"]


@pytest.fixture(scope="module")
def base():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("web_server_agent", root / "web" / "server.py")
    srv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(srv)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _post(base, path, payload):
    req = urllib.request.Request(base + path, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


@needs_data
def test_web_own_calendar_and_agent(base):
    cal = _post(base, "/api/calendar", {"isin": EVD, "events": [
        {"date": "2026-03-26", "time": "17:45", "type": "FY", "title": "FY results"},   # after the close -> next day
        {"date": "2026-03-28", "type": "OTHER", "title": "Saturday"},                  # weekend -> Monday
        {"date": "2026-12-01", "type": "FY", "title": "after the data"}]})
    ev = cal["events"]
    assert ev[0]["reaction_day"] == "2026-03-27" and ev[0]["timing"] == "post_close"
    assert ev[1]["reaction_day"] == "2026-03-30" and ev[2]["reaction_day"] is None
    with urllib.request.urlopen(f"{base}/api/card?isin={EVD}&day=2026-03-27&event_id={ev[0]['event_id']}"
                                f"&date=2026-03-26&time=17:45&type=FY&title=FY%20results", timeout=120) as r:
        card = json.loads(r.read())["card"]
    assert card["event"]["title"] == "FY results" and card["event"]["timing"] == "post_close"
    a = _post(base, "/api/agent", {"isin": EVD, "question": "What happened on 27 Mar?", "lang": "de",
                                   "context": {"page": "dashboard"}, "history": []})
    assert a["source"] == "template" and a["actions"] and a["steps"]
