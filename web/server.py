#!/usr/bin/env python3
"""
Issuer Intelligence Hub, web front end server.  OWNER: C3 (frontend).

Serves the single-page app in web/ and a small JSON API on top of the engine.
Standard library only (no new dependencies). The LLM key stays here, in .env; the browser never sees it.

    python web/server.py            # http://127.0.0.1:8600
    python web/server.py --port 9000 --host 0.0.0.0

API (all GET unless noted, JSON):
    /api/universe                         all 174 shares for the ISIN entry
    /api/issuer?isin=                     Part A: profile, index medians, kpis, liquidity trend, peers, anomalies, events
    /api/card?isin=&day=&event_id=        Part B: impact_card() + 1-minute bars + aftershocks
    /api/compare?type=&index=             same-type events (engine.compare)
    POST /api/narrate {isin,day,event_id,lang}   AI summary (LLM or template fallback)
    POST /api/ask {isin,question}                AI assistant
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

from config import DATA_DIR, HERO_TICKERS, SECTORS_CSV  # noqa: E402
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


@lru_cache(maxsize=1)
def stock_medians(days: int = 60) -> pd.DataFrame:
    """Per stock: medians over its last `days` trading days (peer benchmarking)."""
    d = data.daily().sort_values("date")
    last = d.groupby("isin").tail(days)
    m = last.groupby("isin").agg(turnover_eur=("turnover_eur", "median"), xlm_25k=("xlm_25k", "median"),
                                 auction_share=("auction_share", "median"), agent_share=("agent_share", "median"),
                                 volatility=("ret", "std"))
    m["volatility"] = m["volatility"] * math.sqrt(252)
    u = data.universe().set_index("isin")
    m = m.join(u[["ticker", "name", "idx_latest", "avg_turnover_eur"]])
    return m


PEER_COLS = ["turnover_eur", "xlm_25k", "auction_share", "agent_share", "volatility"]


def peers(isin: str) -> dict:
    m = stock_medians()
    me = m.loc[isin]
    idx_peers = m[(m["idx_latest"] == me["idx_latest"]) & (m.index != isin)]
    # size cohort: the 10 shares with the closest average turnover (any index)
    others = m[m.index != isin].copy()
    others["dist"] = (np.log(others["avg_turnover_eur"]) - math.log(me["avg_turnover_eur"])).abs()
    cohort = others.nsmallest(10, "dist")
    sec = sectors().get(me["ticker"])
    sec_peers = m[[sectors().get(t) == sec and i != isin for i, t in zip(m.index, m["ticker"])]] if sec else m.iloc[0:0]

    def med(frame):
        return {c: r(frame[c].median()) for c in PEER_COLS} if len(frame) else None

    return {
        "stock": {c: r(me[c]) for c in PEER_COLS},
        "groups": [
            {"key": "index", "label": f"{me['idx_latest']} median", "n": len(idx_peers), "values": med(idx_peers)},
            {"key": "size", "label": "Size cohort median", "n": len(cohort), "values": med(cohort),
             "members": [{"ticker": t, "name": n} for t, n in zip(cohort["ticker"], cohort["name"])]},
            {"key": "sector", "label": f"{sec} median" if sec else "Sector median", "n": len(sec_peers),
             "values": med(sec_peers), "members": [{"ticker": t, "name": n} for t, n in zip(sec_peers["ticker"], sec_peers["name"])]},
        ],
        "period": "median of the last 60 trading days; volatility = annualised std of daily returns",
    }


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
        eps.append({**clean(row), "peak_date": day, "event": clean({k: m[k] for k in ("event_id", "type", "title", "verified")}) if m else None})
    u = next(x for x in universe() if x["isin"] == isin)
    return clean({
        "meta": {**u, "first_date": series["date"][0], "last_date": series["date"][-1], "days": len(dates)},
        "series": series,
        "kpis": baseline.kpis(isin),
        "liquidity": baseline.liquidity_trend(isin),
        "peers": peers(isin),
        "anomalies": eps,
        "events": events_for(isin),
    })


def card(isin: str, day: str, event_id: str | None) -> dict:
    ev = find_event(isin, event_id)
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


def narrate(body: dict) -> dict:
    from ai import narrate as nar
    c = impact.impact_card(body["isin"], body["day"], find_event(body["isin"], body.get("event_id")))
    lang = body.get("lang", "en")
    # narrate_with_meta: the model's text is used only if every number in it is in the card (ai/checks.py);
    # "source" says which one the user sees, so the label is honest even when the check rejects a draft
    m = nar.narrate_with_meta(c, lang)
    return {"text": m["text"], "source": m["source"], "model": m["model"], "rejected": m["rejected"], "lang": lang}


def _fallback_answer(q: str, isin: str, lang: str) -> str:
    """Deterministic answer from engine numbers when no LLM is configured (the demo never breaks)."""
    from ai import narrate as nar
    ql = q.lower()
    de = lang == "de"
    k = baseline.kpis(isin)
    name = k["name"]
    if any(w in ql for w in ("result", "ergebnis", "quarter", "quartal", "earnings", "zahlen")):
        e = data.events()
        e = e[(e["isin"] == isin) & (e["type"].isin(["FY", "Q1", "H1", "Q3"]))]
        m = compare.metrics_all().set_index(["isin", "date"])
        lines = []
        for row in e.itertuples():
            key = (isin, pd.Timestamp(row.reaction_day))
            if key in m.index:
                x = m.loc[key]
                lines.append(f"{row.type} ({pd.Timestamp(row.reaction_day).date()}): "
                             f"{x['abn_ret'] * 100:+.1f}% {'abnormal' if not de else 'abnormal'}, "
                             f"{x['vol_ratio']:.1f}x {'turnover vs normal' if not de else 'Umsatz vs. normal'}")
        head = "Reaktion auf Ergebnisveröffentlichungen:" if de else "Reaction to results releases:"
        return head + "\n" + "\n".join(lines) if lines else ("Keine Ergebnistermine im Kalender." if de else "No results dates in the calendar yet.")
    dates = [w for w in q.replace("?", " ").split() if len(w) == 10 and w[4] == "-" and w[7] == "-"]
    if dates:
        try:
            return nar.template_narrative(impact.impact_card(isin, dates[0]), lang)
        except ValueError:
            pass
    if any(w in ql for w in ("spread", "xlm", "cost", "kosten", "peer", "vergleich", "compare")):
        s, i = k["median_xlm_25k_bps"]["stock"], k["median_xlm_25k_bps"]["index_median"]
        if de:
            return (f"{name}: Handelskosten (XLM 25k) im Median {s:.1f} bps über die letzten 60 Handelstage, "
                    f"{k['index']}-Median {i:.1f} bps, also {'günstiger' if s < i else 'teurer'} als der Index.")
        return (f"{name}: median trading cost (XLM 25k) {s:.1f} bps over the last 60 trading days vs. "
                f"{i:.1f} bps for the {k['index']} median, so {'cheaper' if s < i else 'more expensive'} than the index.")
    lt = baseline.liquidity_trend(isin)
    if de:
        v = {"improved": "verbessert", "worsened": "verschlechtert", "mixed": "gemischt", "stable": "stabil"}.get(lt["verdict"], "offen")
        return (f"Liquidität {v}: Handelskosten {lt['xlm_25k_change_pct'] * 100:+.0f}%, Umsatz {lt['turnover_change_pct'] * 100:+.0f}% "
                f"(letzte 60 vs. vorherige 60 Handelstage). Xetra-Kategorie (Schätzung): {lt['ds_category']['now']}.")
    return lt["summary"] + f" Xetra liquidity category (estimate): {lt['ds_category']['now']}."


def ask(body: dict) -> dict:
    if llm_available():
        from ai import agent
        return {"text": agent.ask(body["question"], body["isin"]), "source": "llm"}
    return {"text": _fallback_answer(body["question"], body["isin"], body.get("lang", "en")), "source": "template"}


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
                                    "intraday_stocks": len(data.intraday_isins()), "llm": llm_available()},
            "/api/universe": universe,
            "/api/issuer": lambda: issuer(q["isin"]),
            "/api/card": lambda: card(q["isin"], q["day"], q.get("event_id")),
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
        routes = {"/api/narrate": narrate, "/api/ask": ask}
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
    stock_medians()
    compare.metrics_all()
    print(f"Issuer Intelligence Hub → http://{a.host}:{a.port}", flush=True)
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
