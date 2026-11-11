#!/usr/bin/env python3
"""
Issuer Intelligence Hub, web front end server.  OWNER: C3 (frontend).

Serves the single-page app in web/ and a small JSON API on top of the engine.
Standard library only (no new dependencies). The LLM key stays here, in .env; the browser never sees it.

    python web/server.py            # http://127.0.0.1:8600
    python web/server.py --port 9000 --host 0.0.0.0

API (all GET unless noted, JSON):
    /api/universe                         all 174 shares for the ISIN entry
    /api/issuer?isin=                     trading profile: series, index medians, kpis, liquidity trend, peers,
                                          trading cost by order size, unusual days, event calendar
    /api/card?isin=&day=&event_id=        impact_card() + 1-minute bars + aftershocks
         [&date=&time=&type=&title=]      ... for an event the user added or imported (not in events.csv)
    /api/compare?type=&index=             same-type events (engine.compare)
    POST /api/calendar {isin,events:[{date,time,type,title}]}  match the company's own calendar to trading days
    POST /api/narrate {isin,day,event_id,lang}   AI summary (LLM or template fallback)
    POST /api/agent {isin,question,history,context,lang}  IR analyst agent (ai/agent.py: tool calling over the engine)
    POST /api/ask {isin,question,lang}           same agent, short answer (v1 contract)
    /api/status                           data + LLM status
"""
import argparse
import json
import math
import sys
import traceback
from datetime import date, datetime
from functools import lru_cache
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from config import DATA_DIR, HERO_TICKERS, SECTORS_CSV, XETRA_CLOSE_AUCTION, XETRA_OPEN  # noqa: E402
from engine import baseline, compare, data, impact  # noqa: E402

WEB = Path(__file__).resolve().parent


# ---------- JSON helpers ----------
def clean(o):
    """Make engine output JSON safe: NaN/inf -> None, numpy/pandas scalars -> Python."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set, frozenset)):
        return [clean(v) for v in o]
    if isinstance(o, (pd.Timestamp, datetime, date)):
        return str(o.date()) if isinstance(o, pd.Timestamp) and o == o.normalize() else str(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return None if math.isnan(f) or math.isinf(f) else f
    if o is pd.NaT:
        return None
    return o


def records(df: pd.DataFrame) -> list[dict]:
    return clean(df.to_dict("records"))


def r(x, nd=6):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


# ---------- data helpers ----------
@lru_cache(maxsize=1)
def sectors() -> dict:
    if not SECTORS_CSV.exists():
        return {}
    s = pd.read_csv(SECTORS_CSV, dtype=str).dropna(subset=["sector"])  # KCO has no sector -> no NaN in JSON
    return dict(zip(s["ticker"], s["sector"], strict=False))


@lru_cache(maxsize=1)
def universe() -> list[dict]:
    u = data.universe()
    has = data.intraday_isins()
    sec = sectors()
    out = []
    for row in u.sort_values("avg_turnover_eur", ascending=False).itertuples():
        out.append({"isin": row.isin, "ticker": row.ticker, "name": row.name, "index": row.idx_latest,
                    "member_now": bool(row.member_now), "avg_turnover_eur": r(row.avg_turnover_eur, 0),
                    "intraday": row.isin in has, "hero": row.ticker in HERO_TICKERS,
                    "sector": sec.get(row.ticker)})
    return out


PEER_COLS = list(compare.PEER_COLS)


def peers(isin: str) -> dict:
    """Index, sector and size peers with the engine's one benchmark (engine.compare.peer_medians): the same
    numbers as Streamlit, the Part A report and the assistant."""
    p = compare.peer_medians(isin)

    def vals(v):
        return {c: r(v[c]) for c in PEER_COLS} if v else None

    groups = []
    for by in ("index", "sector", "size"):
        g = p["groups"][by]
        if by == "sector" and g["by"] != "sector":  # unknown sector: the engine falls back to the index
            continue
        groups.append({"key": by, "label": g["label"], "name": g["name"], "n": g["n"], "values": vals(g["values"]),
                       "members": [{"ticker": data.ticker_of(i), "name": data.display_name(i)} for i in g["isins"]][:12]})
    return {"stock": vals(p["stock"]), "groups": groups,
            "period": p["period"] + "; volatility = annualised std of daily returns; "
                      "size = the 10 stocks closest in turnover (market cap is not in the data)"}


def cost_curve(isin: str) -> dict | None:
    from engine import xlm
    try:
        c = xlm.cost_curve(isin)
    except Exception:  # noqa: BLE001  no XLM (e.g. left the index): the dashboard simply hides the curve
        return None
    return clean({"rows": records(c), "summary": xlm.curve_summary(c)})


def events_for(isin: str) -> list[dict]:
    e = data.events()
    e = e[e["isin"] == isin].sort_values("reaction_day")
    return records(e)


def find_event(isin: str, event_id: str | None) -> dict | None:
    if not event_id:
        return None
    e = data.events()
    hit = e[(e["isin"] == isin) & (e["event_id"] == event_id)]
    return hit.iloc[0].to_dict() if len(hit) else None


def issuer(isin: str) -> dict:
    s = data.stock(isin)
    if s.empty:
        raise KeyError(isin)
    idx = s["idx_latest"].iloc[-1]
    prof = baseline.profile(isin)
    bench = {c: baseline.index_benchmark(idx, c) for c in ("turnover_eur", "xlm_25k", "auction_share", "ret")}
    dates = prof["date"]
    series = {
        "date": [str(d.date()) for d in dates],
        **{c: [r(v) for v in prof[c]] for c in ("price", "ret", "abn_ret", "turnover_eur", "vol_ratio", "xlm_25k",
                                                  "auction_share", "agent_share", "prop_share", "mm_share")},
        "index_turnover_eur": [r(bench["turnover_eur"].get(d)) for d in dates],
        "index_xlm_25k": [r(bench["xlm_25k"].get(d)) for d in dates],
        "index_auction_share": [r(bench["auction_share"].get(d)) for d in dates],
        "index_ret": [r(bench["ret"].get(d)) for d in dates],
    }
    ep = baseline.anomaly_episodes(isin)
    ev = data.events()
    ev = ev[ev["isin"] == isin]
    by_day = {str(pd.Timestamp(d).date()): row for d, row in zip(ev["reaction_day"], ev.to_dict("records"))}
    eps = []
    for row in ep.to_dict("records"):
        day = str(pd.Timestamp(row["peak_date"]).date())
        m = by_day.get(day)
        eps.append({**clean(row), "peak_date": day, "context": row.get("context") or "",
                    "event": clean({k: m[k] for k in ("event_id", "type", "title", "verified")}) if m else None})
    u = next(x for x in universe() if x["isin"] == isin)
    return clean({
        "meta": {**u, "first_date": series["date"][0], "last_date": series["date"][-1], "days": len(dates)},
        "series": series,
        "kpis": baseline.kpis(isin),
        "liquidity": baseline.liquidity_trend(isin),
        "peers": peers(isin),
        "cost_curve": cost_curve(isin),
        "anomalies": eps,
        "events": events_for(isin),
    })


def _timing(t: str | None) -> str:
    if not t:
        return "unknown"
    t = t.strip()[:5]
    return "pre_open" if t < XETRA_OPEN else "intraday" if t < XETRA_CLOSE_AUCTION else "post_close"


def calendar(body: dict) -> dict:
    """The company's own event calendar (typed in or imported as CSV/ICS in the browser) -> reaction days.
    Same rule as ingest/build_events.py: after the close or on a non-trading day -> next trading day."""
    isin = body["isin"]
    days = pd.DatetimeIndex(sorted(data.stock(isin)["date"].unique()))
    out = []
    for e in body.get("events", [])[:200]:
        try:
            d = pd.Timestamp(str(e["date"])[:10])
        except (KeyError, ValueError):
            continue
        t = (e.get("time") or "").strip()[:5] or None
        timing = _timing(t)
        pos = int(days.searchsorted(d))
        if pos < len(days) and days[pos] == d and timing == "post_close":
            pos += 1
        if pos >= len(days):
            out.append({**e, "reaction_day": None, "note": "after the end of the data"})
            continue
        etype = str(e.get("type") or "OTHER").upper()[:12]
        out.append({"event_id": f"USR_{etype}_{d.strftime('%Y%m%d')}{'_' + t.replace(':', '') if t else ''}",
                    "type": etype, "date": str(d.date()), "time_local": t or "", "timing": timing,
                    "title": str(e.get("title") or etype)[:160], "reaction_day": str(days[pos].date()),
                    "verified": "0", "source_url": "", "user": True})
    return {"events": out}


def card(isin: str, day: str, event_id: str | None, user: dict | None = None) -> dict:
    ev = find_event(isin, event_id)
    if ev is None and user and user.get("date"):
        t = (user.get("time") or "").strip()[:5]
        ev = {"event_id": event_id, "type": (user.get("type") or "OTHER").upper(), "date": user["date"],
              "time_local": t, "timing": _timing(t), "title": user.get("title") or "Own calendar entry",
              "source_url": ""}
    c = impact.impact_card(isin, day, ev)
    s = data.stock(isin)
    i = int(s.index[s["date"] == pd.Timestamp(day)][0])
    prev_close = r(s.loc[i - 1, "price"]) if i > 0 else None
    after = s.iloc[max(0, i - 5): i + 16]
    aftershocks = [{"t": int(k - i), "date": str(d.date()), "vol_ratio": r(v), "xlm_ratio": r(x), "abn_ret": r(a)}
                   for k, d, v, x, a in zip(after.index, after["date"], after["vol_ratio"], after["xlm_25k_ratio"], after["abn_ret"])]
    bars = None
    b = data.intraday(isin)
    if b is not None and len(b):
        b = b[b["ts_local"].dt.date == pd.Timestamp(day).date()]
        hh = b["ts_local"].dt.strftime("%H:%M")
        b = b[(hh >= "08:55") & (hh <= "17:40")]
        if len(b):
            bars = {"t": list(b["ts_local"].dt.strftime("%H:%M")), "close": [r(x) for x in b["close"]],
                    "low": [r(x) for x in b["low"]], "high": [r(x) for x in b["high"]],
                    "eur": [r(x, 0) for x in b["volume_eur"]], "auction": [bool(x) for x in b["is_auction"]],
                    "buy": [r(x, 0) for x in b["aggr_buy_eur"]], "sell": [r(x, 0) for x in b["aggr_sell_eur"]]}
    return clean({"card": c, "prev_close": prev_close, "close": r(s.loc[i, "price"]), "bars": bars,
                  "aftershocks": aftershocks, "event_row": ev})


def compare_table(etype: str, index: str | None) -> dict:
    t = compare.same_type_events(etype, index or None)
    return clean({"types": compare.event_types(), "type": etype, "index": index or "ALL", "rows": records(t)})


def llm_available() -> bool:
    try:
        from ai import llm
        return llm.available()
    except Exception:  # noqa: BLE001
        return False


def llm_model() -> str | None:
    try:
        from ai import llm
        return llm.model_name() if llm.available() else None
    except Exception:  # noqa: BLE001
        return None


def narrate(body: dict) -> dict:
    from ai import narrate as nar
    c = impact.impact_card(body["isin"], body["day"], find_event(body["isin"], body.get("event_id")))
    lang = body.get("lang", "en")
    # narrate_with_meta: the model's text is used only if every number in it is in the card (ai/checks.py);
    # "source" says which one the user sees, so the label is honest even when the check rejects a draft
    m = nar.narrate_with_meta(c, lang)
    return {"text": m["text"], "source": m["source"], "model": m["model"], "rejected": m["rejected"], "lang": lang}


def agent(body: dict) -> dict:
    from ai import agent as ag
    out = ag.run(body["question"], body["isin"], history=body.get("history") or [],
                 context=body.get("context") or {}, lang=body.get("lang", "en"))
    return clean(out)


def ask(body: dict) -> dict:
    """v1 contract: {text, source}. Same agent."""
    out = agent(body)
    return {"text": out["text"], "source": out["source"], "actions": out.get("actions", [])}


# ---------- HTTP ----------
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(WEB), **kw)

    def log_message(self, fmt, *args):  # quieter console
        if "/api/" in str(args[0] if args else ""):  # args[0] is an HTTPStatus for errors (e.g. favicon 404)
            sys.stderr.write("%s\n" % (fmt % args))

    def _json(self, obj, code=200):
        raw = json.dumps(obj, default=str, allow_nan=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _guard(self, fn, *a):
        try:
            self._json(fn(*a))
        except KeyError as e:
            self._json({"error": f"unknown: {e}"}, 404)
        except ValueError as e:
            self._json({"error": str(e)}, 400)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        routes = {
            "/api/status": lambda: {"data_dir": str(DATA_DIR), "stocks": len(universe()),
                                    "intraday_stocks": len(data.intraday_isins()), "llm": llm_available(),
                                    "model": llm_model(), "last_date": str(data.daily()["date"].max().date())},
            "/api/universe": universe,
            "/api/issuer": lambda: issuer(q["isin"]),
            "/api/card": lambda: card(q["isin"], q["day"], q.get("event_id"),
                                      {k: q[k] for k in ("date", "time", "type", "title") if k in q} or None),
            "/api/compare": lambda: compare_table(q.get("type", "NOTABLE_DAY"), q.get("index")),
        }
        if u.path in routes:
            return self._guard(routes[u.path])
        if u.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
        routes = {"/api/narrate": narrate, "/api/ask": ask, "/api/agent": agent, "/api/calendar": calendar}
        if u.path in routes:
            return self._guard(routes[u.path], body)
        self._json({"error": "not found"}, 404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8600)
    a = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):  # Windows consoles (cp1252/cp1254) cannot print "→"
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if not (DATA_DIR / "daily_features.parquet").exists():
        sys.exit(f"No processed data in {DATA_DIR}. Copy it from OneDrive or run the ingest scripts (README).")
    print("warming up the engine …", flush=True)
    universe()
    compare.stock_medians()
    compare.metrics_all()
    print(f"Issuer Intelligence Hub → http://{a.host}:{a.port}", flush=True)
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
