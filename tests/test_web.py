"""Web front end (web/server.py): every API the demo uses, through a real HTTP server.

Going through HTTP (not calling the functions) matters: the server serialises with allow_nan=False, so a NaN
anywhere in the engine output (e.g. a blank sector) turns into a 400. Data tests skip if data/ is empty.
"""
import importlib.util
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from config import DATA_DIR

HAS_DATA = (DATA_DIR / "daily_features.parquet").exists()
needs_data = pytest.mark.skipif(not HAS_DATA, reason="data/daily_features.parquet missing")
ROOT = Path(__file__).resolve().parents[1]
EVD = "DE0005470306"


@pytest.fixture(scope="module")
def base():
    spec = importlib.util.spec_from_file_location("web_server", ROOT / "web" / "server.py")
    srv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(srv)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=120) as r:
        assert r.status == 200, path
        body = r.read()
    return json.loads(body) if path.startswith("/api/") else body


def post(base, path, payload):
    req = urllib.request.Request(base + path, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        assert r.status == 200, path
        return json.loads(r.read())


@needs_data
def test_web_static_and_status(base):
    assert b"<html" in get(base, "/").lower()
    st = get(base, "/api/status")
    assert st["stocks"] == 174 and st["intraday_stocks"] >= 44


@needs_data
def test_web_universe_has_every_share(base):
    u = get(base, "/api/universe")
    assert len(u) == 174 and {"EVD", "EVT", "HDD", "KCO"} <= {x["ticker"] for x in u}


@needs_data
@pytest.mark.parametrize("ticker", ["EVD", "HDD", "GXI", "KCO", "HAG", "SAP"])
def test_web_issuer_page_for_edge_cases(base, ticker):
    """GXI: no XLM after leaving the SDAX; KCO: no sector; HAG: no unusual days."""
    from engine.data import isin_of
    iss = get(base, f"/api/issuer?isin={isin_of(ticker)}")
    assert iss["meta"]["ticker"] == ticker


@needs_data
def test_web_impact_card_evd_27_mar(base):
    d = get(base, f"/api/card?isin={EVD}&day=2026-03-27&event_id=EVD_FY_20260326")
    c = d["card"]
    assert c["event"]["type"] == "FY" and c["event"]["timing"] == "post_close"
    assert c["intraday"]["onset"]["time"] == "09:03"
    assert c["auctions"]["close_auction_eur"] == pytest.approx(25.59e6, rel=0.005)
    assert c["comparison"]["rank_abs_abn_ret"] <= 3
    assert d["bars"] and max(d["bars"]["t"]) <= "17:40"


@needs_data
def test_web_compare_and_ai(base):
    h1 = get(base, "/api/compare?type=H1")
    assert len(json.dumps(h1)) > 1000
    n = post(base, "/api/narrate", {"isin": EVD, "day": "2026-03-27", "event_id": "EVD_FY_20260326", "lang": "de"})
    assert n["source"] == "template" and "CTS Eventim" in n["text"]
    a = post(base, "/api/ask", {"isin": EVD, "question": "Has our liquidity improved?", "lang": "en"})
    assert a["text"] and a["source"] == "template"
