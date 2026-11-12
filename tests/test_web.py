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


@needs_data
@pytest.mark.parametrize("query, name", [
    (f"isin={EVD}&day=2026-03-27&event_id=EVD_FY_20260326&lang=de", "IR_snapshot_EVD_2026-03-27_DE"),
    (f"isin={EVD}&lang=en", "IR_report_EVD_EN"),
])
def test_web_one_click_export(base, query, name):
    """Brief: the card is generated 'with one click ... including an exportable short report'."""
    with urllib.request.urlopen(f"{base}/api/export?{query}", timeout=180) as r:
        assert r.status == 200
        ctype, disp, raw = r.headers["Content-Type"], r.headers["Content-Disposition"], r.read()
    if ctype == "application/pdf":
        assert raw.startswith(b"%PDF") and f'filename="{name}.pdf"' in disp
    else:  # xhtml2pdf missing: the same report as HTML
        assert ctype.startswith("text/html") and f'filename="{name}.html"' in disp



@needs_data
@pytest.mark.parametrize("period", ["3m", "6m", "all"])
def test_web_dashboard_in_one_call(base, period):
    """The simple UI draws the whole dashboard from /api/dashboard; the browser computes nothing."""
    d = get(base, f"/api/dashboard?isin={EVD}&period={period}")
    assert d["index"] == "MDAX" and d["sector"] == "Media & Telecom" and d["liquidity_category"] in ("A", "B")
    vm = d["versus_market"]
    for k in ("price", "turnover_eur", "xlm_25k"):
        assert vm[k]["of"] == 50 and 1 <= vm[k]["rank"] <= 50 and vm[k]["stock"] is not None and vm[k]["index"] is not None
    assert d["tiles"]["price"] == vm["price"] and len(d["timeline"]["date"]) == d["days"]
    assert 1 <= len(d["market_days"]) <= 10 and all(r["index_ret"] is not None for r in d["market_days"])
    if period == "all":
        fy = next(e for e in d["events"] if e["event_id"] == "EVD_FY_20260326")
        assert fy["published"] == "2026-03-26" and fy["day"] == "2026-03-27" and fy["time"] == "17:45"   # publication date, not the reaction day
        assert fy["unusual"] and fy["vol_ratio"] == 8.55 and d["tiles"]["unusual_days"] == 6


@needs_data
def test_web_card_compare_and_examples_agree(base):
    """One rounded value and one rank everywhere: card 8.55x = compare table 8.55x; rank 3 of 215 in both."""
    c = get(base, f"/api/card?isin={EVD}&day=2026-03-27&event_id=EVD_FY_20260326")
    assert c["card"]["volume"]["ratio"] == 8.55 and c["rank"]["en"]["rank"] == "rank 3 of 215 (incl. this day)"
    assert len(c["bars"]["ret"]) == len(c["bars"]["t"])
    t = get(base, "/api/compare?type=NOTABLE_DAY&index=MDAX")
    row = next(r for r in t["rows"] if r["isin"] == EVD and r["reaction_day"][:10] == "2026-03-27")
    assert row["vol_ratio"] == 8.55 and row["rank"] == 3 and t["n"] == 215 and row["display"].startswith("CTS Eventim")
    ex = sorted((u["example"], u["index"]) for u in get(base, "/api/universe") if u.get("example") is not None)
    assert [i for _, i in ex] == ["DAX", "MDAX", "SDAX"]   # one example company per index on the first screen
