"""
IR assistant (agent).  OWNER: C4 (AI).  STATUS: v2 = tool calling over the engine (first version by C3;
prompt glossary from the v1 dry run with the live JAIF model).

    run(question, isin, history=(), context=None, lang="en") -> dict
        text      the answer
        source    "llm" (model + tools) | "template" (deterministic, no key or model error)
        model     model name or None
        steps     [{"tool", "args"}]  engine functions that produced the numbers, in order
        actions   [{"view", "isin", "day", "event_id", "event_type", "index"}]  buttons the UI shows
        check     {"total", "unsupported": [...]}  numbers check of the answer against the tool outputs
        rejected  figures of a model answer that failed the check (then text/source are the deterministic answer)
    ask(question, isin) -> str   v1 signature, kept for the Streamlit page

How it works: the model gets the TOOLS below (OpenAI function calling, works with the JAIF / hessian.AI
gateway). It decides which engine functions to call, reads their JSON and writes the answer. It never sees
raw data and never computes figures itself: every number must come from a tool output, which ai/checks.py
verifies after the fact; an answer with an unverified figure is replaced by the deterministic answer (same rule
as the card summary). Causes come only from the event calendar (events.csv, with sources).
Without a key, or if the model fails, a deterministic router answers from the same tools, so the demo
never breaks. Answers are cached in data/agent_cache.json (LLM_CACHE, same switch as ai/llm.py).
"""
import hashlib
import json
import math
import os
import re
import time

import numpy as np
import pandas as pd

from ai import llm
from ai.checks import unsupported_numbers
from config import COMPARE_MIN_GROUP, DATA_DIR
from engine import baseline, compare, data, evidence, impact

MAX_ROUNDS = 6
CACHE_VERSION = 3  # bump when the agent logic changes, so old cached answers are not replayed
# GLM-5.3-Flash reasons before it answers; a small budget can end with no visible answer (model handbook)
MAX_TOKENS = 4096
BUDGET_S = 75  # whole tool loop; past this the deterministic answer is shown instead of a spinner

SYSTEM = """You are the IR analyst inside the Issuer Intelligence Hub, a Deutsche Boerse Issuer Services tool.
You help the investor-relations team of a listed company understand how its share trades on Xetra.

Rules:
- Every figure you write must come from a tool result in this conversation. Never estimate, compute new
  figures or round differently than 1 decimal for percentages and ratios. If no tool gives a number, say so.
- Call tools first, then answer. Use the company in CONTEXT unless the user names another one
  (then use find_company).
- Causes: the trading data shows THAT something happened, not WHY. Name a cause only if the event calendar
  (event_calendar / unusual_days) lists an announcement for that day, and say it is the listed announcement.
  Market context flags (index event, option expiry, market-wide volume) are mechanics, not company news.
- A question about a specific day or event: call impact_card for that day, then show(view="card", day=...).
- Whether an explanation of a move holds ("was it the market?", "did funds sell?", "was it an overreaction?",
  "was there a leak?"): call check_explanation and report its verdict and evidence; say "consistent with",
  never "caused by". If the verdict is not_testable, say what the data cannot show.
  Never write "leak", "insider" or "rumour" yourself: say "unusual trading before the announcement" and that
  the data does not show why.
- When the user wants to see, open, create or export something (impact card, comparison, report, dashboard),
  call show() so the UI offers a one-click button. ALWAYS also answer the question in text with the key figures;
  never reply only that a view is ready. Do not write links or placeholders like [VIEW CARD]: the UI shows
  the button itself.
- Rankings: comparison.n and compare_events count the OTHER events; the group is n + 1 events. Write
  "#3 of 215" (rank_of_day of n_group), never "#3 of 214".
- Glossary (do not mix them up): price.ret = the share's own return that day ("the share fell 23.2%");
  price.abn_ret = the stock-specific move = return minus the median return of the other index members
  ("stock-specific -21.7%"). Never call ret "stock-specific" or abn_ret "the share fell".
- "Has liquidity improved?": use the liquidity_trend verdict and summary (last 60 vs previous 60 trading days,
  stock vs index). Never compare a 60-day median with a 4-month average.
- If the calendar lists an announcement for a day, name it; never say there is no context when there is one.
- Do not mention internal field names, z-scores or severity scores.
  XLM = Xetra Liquidity Measure: round-trip cost of a EUR 25k order (spread + price impact) in basis points.
  "Size cohort" is a turnover proxy; market capitalisation is not in the data.
- No investment advice, no price predictions, no judgement of the company's strategy.
- Style: factual, short (max ~120 words), plain text for an IR manager: no markdown, no ** and no bullet lists. Answer in {language}.
- Data covers Xetra trading from 2 Jan to {last_date}. Today in the product is the day after the last close.

CONTEXT: {context}"""


# ---------- helpers ----------
def _num(x, nd=6):  # 6 dp like the engine, so re-rounding never shifts a digit
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return x
    return None if math.isnan(f) or math.isinf(f) else round(f, nd)


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, pd.Timestamp):
        return str(o.date())
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return _num(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def _day(s) -> str:
    return str(pd.Timestamp(s).date())


def last_date() -> str:
    return _day(data.daily()["date"].max())


# ---------- tools (implementations = engine functions, compact output) ----------
def find_company(query: str) -> dict:
    q = str(query).strip().lower()
    u = data.universe()
    names = u["isin"].map(data.display_name).str.lower()
    hit = u[(u["isin"].str.lower() == q) | (u["ticker"].str.lower() == q)]
    if hit.empty:
        hit = u[names.str.contains(re.escape(q), na=False) | u["name"].str.lower().str.contains(re.escape(q), na=False)]
    hit = hit.sort_values("avg_turnover_eur", ascending=False).head(5)
    return {"matches": [{"isin": r.isin, "ticker": r.ticker, "name": data.display_name(r.isin), "index": r.idx_latest}
                        for r in hit.itertuples()]}


def company_overview(isin: str) -> dict:
    k = baseline.kpis(isin)
    lt = baseline.liquidity_trend(isin)
    s = data.stock(isin)
    p = s["price"].dropna()
    return _clean({
        "name": data.display_name(isin), "ticker": k["ticker"], "index": k["index"], "data_until": last_date(),
        "close_last_day": p.iloc[-1], "return_since_2_jan": p.iloc[-1] / p.iloc[0] - 1,
        "period": k["period"],
        "median_turnover_eur": k["median_turnover_eur"], "median_xlm_25k_bps": k["median_xlm_25k_bps"],
        "median_auction_share": k["median_auction_share"], "median_agent_share": k["median_agent_share"],
        "xetra_liquidity_category_estimate": k["liquidity_check"]["category_estimate"],
        "avg_turnover_eur_4m": k["liquidity_check"]["avg_turnover_eur_4m"],
        "median_xlm_25k_bps_4m": k["liquidity_check"]["median_xlm_25k_bps_4m"],
        "liquidity_trend": {x: lt.get(x) for x in ("verdict", "summary", "xlm_25k_change_pct", "turnover_change_pct",
                                                     "index_xlm_25k_change_pct", "index_turnover_change_pct")},
        "unusual_days_last_60": k["anomaly_days_last_period"],
        "peer_groups": k["peer_groups"],
    })


def peer_benchmark(isin: str, by: str = "index") -> dict:
    g = compare.peer_group(isin, by)
    k = baseline.kpis(isin)
    col = {"index": "index_median", "sector": "sector_median", "size": "size_median"}[g["by"]]
    vals = {m: {"stock": k[m]["stock"], "peer_median": k[m][col]}
            for m in ("median_turnover_eur", "median_xlm_25k_bps", "median_auction_share", "median_agent_share")}
    return _clean({"group": g["label"], "n_peers": g["n"], "period": k["period"], "values": vals,
                   "peers": [data.display_name(i) for i in g["isins"][:12]]})


def trading_cost_curve(isin: str) -> dict:
    from engine import xlm
    c = xlm.cost_curve(isin)
    return _clean({"rows": c[["label", "stock_bps", "stock_fill", "peer_bps"]].to_dict("records"),
                   "summary": xlm.curve_summary(c),
                   "note": "bps = round-trip cost; fill = share of days the order book could absorb that size"})


def unusual_days(isin: str, limit: int = 8) -> dict:
    ep = baseline.anomaly_episodes(isin)
    ev = data.events()
    ev = ev[ev["isin"] == isin]
    by_day = {_day(d): r for d, r in zip(ev["reaction_day"], ev.to_dict("records"))}
    canon = compare.day_ratios(isin)  # the impact card's "x normal", so the assistant and the card agree
    rows = []
    for r in ep.sort_values("severity", ascending=False).head(int(limit)).to_dict("records"):
        d = _day(r["peak_date"])
        m = by_day.get(d)
        rows.append({"day": d, "days": r["days"], "abn_ret": r["peak_abn_ret"],
                     "turnover_x_normal": canon["vol_ratio"].get(pd.Timestamp(d)),
                     "why_flagged": r["reason"], "market_context": r["context"] or None,
                     "calendar_entry": {"event_id": m["event_id"], "type": m["type"], "title": m["title"]} if m else None})
    return _clean({"n_total": len(ep), "rule": "turnover z>=3, stock-specific move z>=3 or XLM >=2x normal",
                   "note": "day = the peak day of the episode; turnover_x_normal = that day vs the median of t-65..t-6",
                   "days": sorted(rows, key=lambda x: x["day"])})


def event_calendar(isin: str) -> dict:
    e = data.events()
    e = e[e["isin"] == isin].sort_values("reaction_day")
    return _clean({"events": [{"event_id": r.event_id, "type": r.type, "date": _day(r.date), "time": r.time_local or None,
                               "timing": r.timing, "reaction_day": _day(r.reaction_day), "title": r.title,
                               "verified": str(r.verified) == "1"} for r in e.itertuples()]})


def _find_event(isin, event_id):
    if not event_id:
        return None
    e = data.events()
    hit = e[(e["isin"] == isin) & (e["event_id"] == event_id)]
    return hit.iloc[0].to_dict() if len(hit) else None


def impact_card(isin: str, day: str, event_id: str | None = None) -> dict:
    c = impact.impact_card(isin, day, _find_event(isin, event_id))
    intr = dict(c.get("intraday") or {})
    on = dict(intr.pop("onset", None) or {})
    for k in ("bars", "curve", "series"):
        intr.pop(k, None)
        on.pop(k, None)
    c["intraday"] = {**intr, "onset": on} if (intr or on) else None
    cm = c.get("comparison")
    if isinstance(cm, dict) and isinstance(cm.get("n"), int):
        cm.setdefault("rank_of", cm["n"] + 1)  # group = the others + this event ("#3 of 215")
    return _clean(c)


def compare_events(event_type: str = "NOTABLE_DAY", index: str | None = None, isin: str | None = None,
                   day: str | None = None) -> dict:
    note = None
    t = compare.same_type_events(event_type, index or None)
    t = t[t["abn_ret"].notna()].copy()
    if isin and day and len(t) < COMPARE_MIN_GROUP:  # too few to rank: widen like the impact card does
        for et, ix in ((event_type, None), (compare.AUTO_TYPE, index), (compare.AUTO_TYPE, None)):
            w = compare.same_type_events(et, ix)
            w = w[w["abn_ret"].notna()]
            if len(w) >= COMPARE_MIN_GROUP:
                note = (f"only {len(t)} {event_type} events in {index or 'all indices'}; "
                        f"ranked among {et} in {ix or 'DAX+MDAX+SDAX'} instead")
                t, event_type, index = w.copy(), et, ix
                break
    if t.empty:
        return {"event_type": event_type, "n_group": 0}
    t["abs"] = t["abn_ret"].abs()
    t = t.sort_values("abs", ascending=False).reset_index(drop=True)
    names = t["isin"].map(data.display_name)
    out = {"event_type": event_type, "index": index or "DAX+MDAX+SDAX", "n_group": len(t), "note": note,
           "median_abs_abn_ret": t["abs"].median(), "median_turnover_x_normal": t["vol_ratio"].median(),
           "top5": [{"name": n, "day": _day(r.reaction_day), "abn_ret": r.abn_ret, "turnover_x_normal": r.vol_ratio}
                    for n, r in zip(names.head(5), t.head(5).itertuples())]}
    if isin:
        mine = t[t["isin"] == isin]
        out["this_company"] = [{"day": _day(r.reaction_day), "rank": int(i) + 1, "abn_ret": r.abn_ret,
                                "turnover_x_normal": r.vol_ratio} for i, r in mine.iterrows()]
        if day:
            m = mine[mine["reaction_day"].map(_day) == _day(day)]
            if len(m):
                out["rank_of_day"] = int(m.index[0]) + 1
    return _clean(out)


def check_explanation(isin: str, day: str, explanation: str, event_id: str | None = None) -> dict:
    """Test an explanation of a move against the card figures (engine/evidence.py): verdict per claim."""
    ev = _find_event(isin, event_id)
    if ev is None:  # the calendar entry for that reaction day, if any
        e = data.events()
        e = e[(e["isin"] == isin) & (pd.to_datetime(e["reaction_day"]) == pd.Timestamp(day))]
        ev = e.iloc[0].to_dict() if len(e) else None
    b = evidence.brief(isin, _day(day), ev)["en"]
    ids = evidence.classify(explanation) or list(evidence.CLAIMS)
    return _clean({"day": _day(day), "headline": b["headline"], "explanation": explanation,
                   "checks": {k: {"claim": b["claims"][k]["label"], "verdict": b["claims"][k]["verdict"],
                                  "evidence": b["claims"][k]["text"], "better_wording": b["claims"][k]["better"]} for k in ids},
                   "data_cannot_tell": next(x["points"] for x in b["sections"] if x["key"] == "unknown"),
                   "verdicts": "supported = consistent with the data (association, not proof); contradicted; partly; "
                               "not_testable = the data cannot answer it"})


def show(view: str, isin: str, day: str | None = None, event_id: str | None = None,
         event_type: str | None = None, index: str | None = None) -> dict:
    if view not in ("dashboard", "card", "compare", "report"):
        raise ValueError("view must be dashboard, card, compare or report")
    if view in ("card", "report") and day:
        day = _day(day)
        if not (data.stock(isin)["date"] == pd.Timestamp(day)).any():
            raise ValueError(f"{day} is not a trading day for this share")
    return {"view": view, "isin": isin, "day": day, "event_id": event_id, "event_type": event_type, "index": index}


def _fn(name, desc, props, req):
    return {"type": "function", "function": {"name": name, "description": desc,
                                             "parameters": {"type": "object", "properties": props, "required": req}}}


_ISIN = {"type": "string", "description": "ISIN of the share, e.g. DE0005470306"}
_DAY = {"type": "string", "description": "trading day YYYY-MM-DD"}
TYPES = ["NOTABLE_DAY", "FY", "Q1", "H1", "Q3", "ADHOC", "GUIDANCE", "DIVIDEND_EX", "AGM", "INDEX", "MA", "CMD"]
TOOLS = [
    _fn("find_company", "Find a DAX/MDAX/SDAX share by name, ticker or ISIN.", {"query": {"type": "string"}}, ["query"]),
    _fn("company_overview", "Normal state of the share over the last 60 trading days vs index/sector/size medians, "
        "liquidity trend (last 60 vs previous 60 days) and the Xetra liquidity category estimate.", {"isin": _ISIN}, ["isin"]),
    _fn("peer_benchmark", "Compare the share with a peer group: index, sector or size (the 10 stocks closest in turnover).",
        {"isin": _ISIN, "by": {"type": "string", "enum": ["index", "sector", "size"]}}, ["isin"]),
    _fn("trading_cost_curve", "Trading cost (XLM) by order size from EUR 10k to 10m vs peers, and the largest order "
        "the order book absorbs on most days.", {"isin": _ISIN}, ["isin"]),
    _fn("unusual_days", "Unusual trading days of 2026 (volume spikes, stock-specific moves, spread widening) with "
        "market context and the matching calendar entry if any.", {"isin": _ISIN, "limit": {"type": "integer"}}, ["isin"]),
    _fn("event_calendar", "Corporate events of the share (results, AGM, dividends, ad hoc) with time, timing and "
        "reaction day.", {"isin": _ISIN}, ["isin"]),
    _fn("impact_card", "All figures for one event or unusual day: abnormal return vs peers, turnover vs normal, "
        "XLM vs normal, opening/closing auction, client flows, intraday onset, rank among comparable events.",
        {"isin": _ISIN, "day": _DAY, "event_id": {"type": "string", "description": "from event_calendar, optional"}},
        ["isin", "day"]),
    _fn("compare_events", "Compare all events of one type across DAX/MDAX/SDAX in 2026 (ranking by stock-specific "
        "move). Pass isin (and day) to get this company's rank.",
        {"event_type": {"type": "string", "enum": TYPES}, "index": {"type": "string", "enum": ["DAX", "MDAX", "SDAX"]},
         "isin": _ISIN, "day": _DAY}, ["event_type"]),
    _fn("check_explanation", "Test an explanation of a share move (e.g. 'it was the market', 'thin trading', "
        "'funds sold', 'overreaction', 'a leak before the news', 'our results') against the figures of that day. "
        "Returns a verdict per claim: supported / contradicted / partly / not_testable, the evidence and a more "
        "defensible wording.", {"isin": _ISIN, "day": _DAY, "explanation": {"type": "string"},
                                "event_id": {"type": "string"}}, ["isin", "day", "explanation"]),
    _fn("show", "Offer the user a one-click button that opens a view: the impact card of a day, the comparison "
        "page, the IR snapshot report or the dashboard.",
        {"view": {"type": "string", "enum": ["dashboard", "card", "compare", "report"]}, "isin": _ISIN, "day": _DAY,
         "event_id": {"type": "string"}, "event_type": {"type": "string", "enum": TYPES},
         "index": {"type": "string", "enum": ["DAX", "MDAX", "SDAX"]}}, ["view"]),
]
IMPL = {"find_company": find_company, "company_overview": company_overview, "peer_benchmark": peer_benchmark,
        "trading_cost_curve": trading_cost_curve, "unusual_days": unusual_days, "event_calendar": event_calendar,
        "impact_card": impact_card, "compare_events": compare_events, "check_explanation": check_explanation,
        "show": show}
_NEEDS_ISIN = {"company_overview", "peer_benchmark", "trading_cost_curve", "unusual_days", "event_calendar",
               "impact_card", "check_explanation", "show"}


def call_tool(name: str, args: dict, isin: str, context: dict | None = None) -> dict:
    if name not in IMPL:
        return {"error": f"unknown tool {name}"}
    args = {k: v for k, v in (args or {}).items() if v not in (None, "")}
    if name in _NEEDS_ISIN:
        args.setdefault("isin", isin)
    if name == "check_explanation" and (context or {}).get("day"):
        args.setdefault("day", context["day"])
        args.setdefault("event_id", context.get("event_id"))
    if name == "compare_events":  # rank the company (and the open card's day) unless the model asked otherwise
        args.setdefault("isin", isin)
        if (context or {}).get("day") and args["isin"] == isin:
            args.setdefault("day", context["day"])
    try:
        return IMPL[name](**args)
    except (ValueError, KeyError, TypeError, IndexError) as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ---------- cache ----------
def _cache_on() -> bool:
    return os.getenv("LLM_CACHE", "true").lower() not in ("0", "false", "no")


def _cache_file():
    return DATA_DIR / "agent_cache.json"


def _cache(key, value=None):
    try:
        f = _cache_file()
        d = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        if value is None:
            return d.get(key)
        d[key] = value
        f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except (OSError, ValueError):
        return None
    return value


# ---------- the agent ----------
def _ctx_text(isin, context, lang):
    c = context or {}
    u = data.universe().set_index("isin").loc[isin]
    parts = [f"company {data.display_name(isin)} ({u['ticker']}, ISIN {isin}, {u['idx_latest']})",
             f"page the user is on: {c.get('page', 'dashboard')}"]
    if c.get("day"):
        parts.append(f"impact card open for {c['day']}" + (f" (event_id {c['event_id']})" if c.get("event_id") else ""))
    if c.get("event_type"):
        parts.append(f"comparison open for event type {c['event_type']}")
    return "; ".join(parts)


def _assistant_msg(msg) -> dict:
    return {"role": "assistant", "content": msg.content or "",
            "tool_calls": [{"id": t.id, "type": "function",
                            "function": {"name": t.function.name, "arguments": t.function.arguments or "{}"}}
                           for t in msg.tool_calls]}


def _check(text, outputs, question, context):
    payload = {"tools": outputs, "question": question, "context": context or {}}
    bad = [b for b in unsupported_numbers(text, payload)
           if not re.fullmatch(r"20[0-3]\d", b.lstrip("+-−"))]  # years (FY 2025) are labels, not figures
    total = len(re.findall(r"\d+(?:[.,]\d+)?", text))
    return {"total": total, "unsupported": bad}


def _run_llm(question, isin, history, context, lang):
    msgs = [{"role": "system", "content": SYSTEM.format(language="German" if lang == "de" else "English",
                                                         last_date=last_date(), context=_ctx_text(isin, context, lang))}]
    for h in list(history or [])[-6:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            msgs.append({"role": h["role"], "content": str(h["content"])[:2000]})
    msgs.append({"role": "user", "content": question})
    steps, actions, outputs, text = [], [], [], ""
    repaired, draft = False, ""
    t0 = time.monotonic()
    for _ in range(MAX_ROUNDS):
        if time.monotonic() - t0 > BUDGET_S:
            raise TimeoutError(f"agent took longer than {BUDGET_S} s")
        try:
            msg = llm.chat(msgs, tools=TOOLS, tool_choice="auto", temperature=0.1, max_tokens=MAX_TOKENS)
        except Exception:  # noqa: BLE001  the repair round failed: judge the first draft (it is rejected below)
            if not repaired:
                raise
            text = draft
            break
        calls = getattr(msg, "tool_calls", None) or []
        if not calls:
            text = re.sub(r"<think>.*?</think>", "", msg.content or "", flags=re.S).strip()
            bad = _check(text, outputs, question, context)["unsupported"]
            if bad and not repaired:  # one repair round: the model must fetch the figures or drop them
                repaired, draft = True, text
                msgs += [{"role": "assistant", "content": text},
                         {"role": "user", "content": f"These figures are not in any tool result: {', '.join(bad[:8])}. "
                                                     "Call the tools you need, then answer again using only figures "
                                                     "from tool results."}]
                text = ""
                continue
            break
        msgs.append(_assistant_msg(msg))
        for t in calls:
            try:
                args = json.loads(t.function.arguments or "{}")
            except ValueError:
                args = {}
            out = call_tool(t.function.name, args, isin, context)
            steps.append({"tool": t.function.name, "args": {k: v for k, v in args.items() if k != "isin"}})
            if t.function.name == "show" and "error" not in out:
                if out not in actions:
                    actions.append(out)
            else:
                outputs.append(out)
            msgs.append({"role": "tool", "tool_call_id": t.id, "content": json.dumps(out, default=str)[:14000]})
    if not text:  # ran out of rounds: ask once more without tools
        msg = llm.chat(msgs + [{"role": "user", "content": "Answer now with the data above."}], temperature=0.1,
                       max_tokens=MAX_TOKENS)
        text = (msg.content or "").strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    check = _check(text, outputs, question, context)
    if check["unsupported"]:  # still invented figures: never show them; the template answers with the same tools
        fb = fallback(question, isin, context, lang)
        fb["actions"] = fb["actions"] or actions
        fb["rejected"] = check["unsupported"]
        fb["note"] = f"model answer rejected by the numbers check: {', '.join(check['unsupported'][:5])}"
        return fb
    return {"text": text, "source": "llm", "model": llm.model_name(), "steps": steps, "actions": actions,
            "check": check}


def _checked(out: dict, question: str, isin: str, context, lang: str) -> dict:
    """Same rule as the card summary: a model answer with a figure that is not in the tool outputs is not shown;
    the deterministic answer from the same tools is shown instead, and `rejected` says which figures failed."""
    bad = (out.get("check") or {}).get("unsupported") or []
    if not bad:
        return out
    fb = fallback(question, isin, context, lang)
    fb["rejected"] = bad
    fb["note"] = f"model answer not shown: {len(bad)} figure(s) not in the engine output ({', '.join(bad[:3])})"
    return fb


def run(question: str, isin: str, history=(), context=None, lang: str = "en") -> dict:
    question = str(question or "").strip()[:1000]
    if not question:
        raise ValueError("empty question")
    if llm.available():
        key = hashlib.sha256(json.dumps([CACHE_VERSION, llm.model_name(), SYSTEM, TOOLS, question, isin, context, lang, list(history or [])[-6:]],
                                        sort_keys=True, default=str).encode()).hexdigest()
        if _cache_on() and (hit := _cache(key)):
            return _checked({**hit, "cached": True}, question, isin, context, lang)  # labelled "saved answer"
        try:
            out = _run_llm(question, isin, history, context, lang)
            if out["text"]:
                if _cache_on() and out["source"] == "llm" and not out["check"]["unsupported"]:
                    _cache(key, out)  # only clean model answers are replayed in the demo
                return _checked(out, question, isin, context, lang)
        except Exception as e:  # noqa: BLE001  network, quota, model without tool support -> template
            fb = fallback(question, isin, context, lang)
            fb["note"] = f"model error: {type(e).__name__}"
            return fb
    return fallback(question, isin, context, lang)


def ask(question: str, isin: str) -> str:
    """v1 signature (Streamlit assistant page)."""
    return run(question, isin)["text"]


# ---------- deterministic fallback (no key): same tools, fixed wording ----------
_MON = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_MON.update({"mär": 3, "mai": 5, "okt": 10, "dez": 12, "march": 3, "märz": 3, "june": 6, "juni": 6, "july": 7, "juli": 7})


def parse_day(q: str) -> str | None:
    m = re.search(r"\b(20\d\d)-(\d{1,2})-(\d{1,2})\b", q)
    if m:
        return f"{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}"
    m = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(?:(20\d\d)\b)?", q)
    if m:
        return f"{m[3] or 2026}-{int(m[2]):02d}-{int(m[1]):02d}"
    m = re.search(r"\b(\d{1,2})\.?\s*([a-zäA-Z]{3,9})\b", q) or re.search(r"\b([a-zA-Z]{3,9})\s+(\d{1,2})\b", q)
    if m:
        a, b = m.groups()
        d, mon = (a, b) if a.isdigit() else (b, a)
        mon = mon.lower()
        k = _MON.get(mon) or _MON.get(mon[:3])
        if k:
            return f"2026-{k:02d}-{int(d):02d}"
    return None


def _nearest_trading_day(isin, day):
    s = data.stock(isin)
    d = s["date"][s["date"] >= pd.Timestamp(day)]
    return _day(d.iloc[0]) if len(d) else None


def _pc(x, de, sign=True):
    if x is None:
        return "–"
    v = f"{x * 100:+.1f}" if sign else f"{x * 100:.1f}"
    return (v.replace(".", ",") + " %") if de else (v + "%")


_MS = (["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
       ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sep.", "Okt.", "Nov.", "Dez."])


def _d(day, de):
    t = pd.Timestamp(day)
    return f"{t.day}. {_MS[1][t.month - 1]}" if de else f"{t.day} {_MS[0][t.month - 1]}"


def _x(x, de):
    return "–" if x is None else (f"{x:.1f}".replace(".", ",") + "×" if de else f"{x:.1f}×")


def _eur(x, de):
    if x is None:
        return "–"
    if x >= 1e6:
        return (f"{x / 1e6:.1f}".replace(".", ",") + " Mio. €") if de else f"€{x / 1e6:.1f}m"
    return (f"{x / 1e3:.0f} Tsd. €") if de else f"€{x / 1e3:.0f}k"


def fallback(question: str, isin: str, context=None, lang: str = "en") -> dict:
    from ai import narrate as nar
    q, de, ctx = question.lower(), lang == "de", context or {}
    name = data.display_name(isin)
    steps, actions, outputs = [], [], []

    def use(tool, **args):
        out = call_tool(tool, args, isin)
        steps.append({"tool": tool, "args": args})
        outputs.append(out)
        return out

    def act(view, **kw):
        a = call_tool("show", {"view": view, **kw}, isin)
        if "error" not in a:
            actions.append(a)

    has = lambda *ws: any(w in q for w in ws)  # noqa: E731
    day = parse_day(question)
    if not day and has("this card", "this day", "diese karte", "diesen tag", "explain", "erklär", "summar", "zusammenfass") and ctx.get("day"):
        day = ctx["day"]

    peerq = has("spread", "xlm", "trading cost", "handelskosten", "peer", "sector", "sektor", "size", "größe") and \
        not has("event", "ereignis", "results", "ergebnis", "unusual", "auffällig", "this day", "diesen tag")
    claim_ids = evidence.classify(question) if (ctx.get("day") or day) and has(
        "market", "markt", "fund", "fonds", "short", "leak", "insider", "overreact", "übertr", "thin", "dünn",
        "investor", "anleger", "index", "expir", "verfall", "revers", "erhol", "why", "warum", "because", "weil",
        "explanation", "erklärung") else []
    if claim_ids and not peerq:
        td = _nearest_trading_day(isin, day or ctx["day"])
        r = use("check_explanation", day=td, explanation=question,
                event_id=ctx.get("event_id") if td == ctx.get("day") else None)
        bl = evidence.brief(isin, td, _find_event(isin, ctx.get("event_id")) if td == ctx.get("day") else None)[lang]
        vw = {"supported": ("supported by the data", "von den Daten gestützt"), "contradicted": ("contradicted by the data", "von den Daten widerlegt"),
              "partly": ("partly supported", "teilweise gestützt"), "not_testable": ("not testable with this data", "mit diesen Daten nicht prüfbar")}
        text = " ".join(f"{bl['claims'][k]['label']} {vw[bl['claims'][k]['verdict']][1 if de else 0]}: {bl['claims'][k]['text']}"
                        for k in r["checks"])
        act("card", day=td, event_id=ctx.get("event_id") if td == ctx.get("day") else None)
        return {"text": text, "source": "template", "model": None, "steps": steps, "actions": actions,
                "check": _check(text, outputs + [bl], question, context)}
    if peerq and not day:
        by = "sector" if has("sector", "sektor") else "size" if has("size", "größe") else "index"
        p = use("peer_benchmark", by=by)
        s, m = p["values"]["median_xlm_25k_bps"]["stock"], p["values"]["median_xlm_25k_bps"]["peer_median"]
        t, tm = p["values"]["median_turnover_eur"]["stock"], p["values"]["median_turnover_eur"]["peer_median"]
        text = (f"{name} vs. {p['group']} ({p['n_peers']} Werte), letzte 60 Handelstage: Handelskosten (XLM 25k) {s:.1f} Bp. "
                f"vs. {m:.1f} Bp. Median, also {'günstiger' if s < m else 'teurer'}; Umsatz {_eur(t, True)} vs. {_eur(tm, True)} pro Tag.") if de else \
               (f"{name} vs {p['group']} ({p['n_peers']} shares), last 60 trading days: trading cost (XLM 25k) {s:.1f} bps "
                f"vs {m:.1f} bps median, so {'cheaper' if s < m else 'more expensive'}; turnover {_eur(t, False)} vs {_eur(tm, False)} a day.")
        return {"text": text, "source": "template", "model": None, "steps": steps, "actions": actions,
                "check": _check(text, outputs, question, context)}
    if has("report", "pdf", "export", "snapshot", "bericht"):
        d = ctx.get("day")
        act("report", day=d, event_id=ctx.get("event_id"))
        text = (f"Der IR-Snapshot für {name} ist bereit: Normalzustand, Peer-Vergleich, Liquidität, auffällige Tage"
                f"{' und die Impact Card' if d else ''}. Abschnitte wählen, dann als PDF sichern.") if de else \
               (f"The IR snapshot for {name} is ready: normal state, peer benchmark, liquidity, unusual days"
                f"{' and the impact card' if d else ''}. Choose the sections, then save as PDF.")
    elif day:
        td = _nearest_trading_day(isin, day)
        cal = use("event_calendar")
        ev = next((e for e in cal["events"] if e["reaction_day"] == td), None)
        card = use("impact_card", day=td, event_id=ev["event_id"] if ev else None) if td else {"error": "no day"}
        if "error" in card:
            text = "Für diesen Tag gibt es keine Handelsdaten." if de else "There is no trading data for that day."
        else:
            text = nar.template_narrative(card, lang)
            act("card", day=td, event_id=ev["event_id"] if ev else None)
    elif has("compare", "rank", "vergleich", "rang", "other compan", "andere", "similar event", "ähnlich", "which compan", "welches unternehmen") or (ctx.get("page") == "compare" and has("which", "welche", "who", "wer")):
        etype, idx = ctx.get("event_type") or "NOTABLE_DAY", ctx.get("index") if ctx.get("index") in ("DAX", "MDAX", "SDAX") else None
        if ctx.get("day"):
            card = use("impact_card", day=ctx["day"], event_id=ctx.get("event_id"))
            if card.get("comparison"):  # same group as the card shows ("#3 of 215 MDAX days")
                etype = card["comparison"]["group_type"]
                gi = card["comparison"].get("group_index")
                idx = gi if gi in ("DAX", "MDAX", "SDAX") else None
        c = use("compare_events", event_type=etype, index=idx, isin=isin, day=ctx.get("day"))
        act("compare", event_type=etype, index=idx)
        if not c.get("n_group"):
            text = "Für diesen Ereignistyp gibt es noch keine Vergleichsfälle." if de else "No comparable events of this type yet."
        else:
            top = c["top5"][0]
            r = c.get("rank_of_day")
            if de:
                text = (f"{c['n_group']} vergleichbare Fälle in {c['index']}; Median der titelspezifischen Bewegung "
                        f"{_pc(c['median_abs_abn_ret'], True, False)}, Umsatz {_x(c['median_turnover_x_normal'], True)} normal. "
                        f"Größter Fall: {top['name']} am {_d(top['day'], True)} ({_pc(top['abn_ret'], True)})."
                        + (f" {name} liegt an diesem Tag auf Rang {r} von {c['n_group']}." if r else ""))
            else:
                text = (f"{c['n_group']} comparable cases in {c['index']}; median stock-specific move "
                        f"{_pc(c['median_abs_abn_ret'], False, False)}, turnover {_x(c['median_turnover_x_normal'], False)} normal. "
                        f"Largest: {top['name']} on {_d(top['day'], False)} ({_pc(top['abn_ret'], False)})."
                        + (f" {name} ranks #{r} of {c['n_group']} on that day." if r else ""))
    elif has("result", "ergebnis", "quarter", "quartal", "earnings", "zahlen"):
        cal = use("event_calendar")
        res = [e for e in cal["events"] if e["type"] in ("FY", "Q1", "H1", "Q3")]
        lines = []
        for e in res:
            c = use("impact_card", day=e["reaction_day"], event_id=e["event_id"])
            if "error" not in c:
                lines.append(f"{e['type']} ({_d(e['reaction_day'], de)}): {_pc(c['price']['abn_ret'], de)} "
                             f"{'abnormal' if not de else 'abnormal'}, {_x(c['volume']['ratio'], de)} "
                             f"{'turnover vs normal' if not de else 'Umsatz vs. normal'}")
        if res:
            act("compare", event_type=res[-1]["type"])
        head = "Reaktion auf Ergebnisveröffentlichungen:" if de else "Reaction to results releases:"
        text = head + "\n" + "\n".join(lines) if lines else ("Keine Ergebnistermine im Kalender." if de else "No results dates in the calendar yet.")
    elif has("unusual", "biggest", "largest", "strongest", "auffällig", "größte", "stärkste", "anomal", "spike"):
        u = use("unusual_days", limit=5)
        days = sorted(u["days"], key=lambda x: -abs(x["abn_ret"] or 0))[:3]
        if not days:
            text = "Keine auffälligen Tage 2026." if de else "No unusual days in 2026."
        else:
            def why(x):
                if x["calendar_entry"]:
                    return x["calendar_entry"]["type"]
                if x["market_context"]:
                    return ("Marktkontext: " if de else "market context: ") + x["market_context"].replace("_", " ")
                return "kein Kalendereintrag" if de else "no calendar entry"
            text = ((f"{u['n_total']} auffällige Phasen 2026. Die stärksten: " if de else f"{u['n_total']} unusual episodes in 2026. The strongest: ")
                    + "; ".join(f"{_d(x['day'], de)}: {_pc(x['abn_ret'], de)}, {_x(x['turnover_x_normal'], de)} ({why(x)})" for x in days) + ".")
            act("card", day=days[0]["day"], event_id=(days[0]["calendar_entry"] or {}).get("event_id"))
    elif has("order size", "large order", "block", "ordergröße", "große order", "institution", "curve", "kurve", "absorb"):
        c = use("trading_cost_curve")
        s = c["summary"]
        text = (f"{name}: Eine 100-T€-Order kostet im Median {s['cost_100k_bps']:.0f} Bp. (Peers {s['peer_cost_100k_bps']:.0f}). "
                f"Das Orderbuch nimmt an den meisten Tagen Orders bis {s['largest_absorbed_label']} auf.") if de else \
               (f"{name}: a €100k order costs a median {s['cost_100k_bps']:.0f} bps round trip (peers {s['peer_cost_100k_bps']:.0f}). "
                f"The order book absorbs orders up to {s['largest_absorbed_label']} on most days.")
    elif has("spread", "xlm", "cost", "kosten", "peer", "sector", "sektor", "size", "größe"):
        by = "sector" if has("sector", "sektor") else "size" if has("size", "größe") else "index"
        p = use("peer_benchmark", by=by)
        s, m = p["values"]["median_xlm_25k_bps"]["stock"], p["values"]["median_xlm_25k_bps"]["peer_median"]
        t, tm = p["values"]["median_turnover_eur"]["stock"], p["values"]["median_turnover_eur"]["peer_median"]
        text = (f"{name} vs. {p['group']} ({p['n_peers']} Werte), letzte 60 Handelstage: Handelskosten (XLM 25k) {s:.1f} Bp. "
                f"vs. {m:.1f} Bp. Median, also {'günstiger' if s < m else 'teurer'}; Umsatz {_eur(t, True)} vs. {_eur(tm, True)} pro Tag.") if de else \
               (f"{name} vs {p['group']} ({p['n_peers']} shares), last 60 trading days: trading cost (XLM 25k) {s:.1f} bps "
                f"vs {m:.1f} bps median, so {'cheaper' if s < m else 'more expensive'}; turnover {_eur(t, False)} vs {_eur(tm, False)} a day.")
    else:
        o = use("company_overview")
        lt = o["liquidity_trend"]
        if de:
            v = {"improved": "verbessert", "worsened": "verschlechtert", "mixed": "gemischt", "stable": "stabil"}.get(lt["verdict"], "offen")
            text = (f"Liquidität {v}: Handelskosten {_pc(lt['xlm_25k_change_pct'], True)}, Umsatz {_pc(lt['turnover_change_pct'], True)} "
                    f"(letzte 60 vs. vorherige 60 Handelstage). Xetra-Kategorie (Schätzung): {o['xetra_liquidity_category_estimate']}.")
        else:
            text = lt["summary"] + f" Xetra liquidity category (estimate): {o['xetra_liquidity_category_estimate']}."
    return {"text": text, "source": "template", "model": None, "steps": steps, "actions": actions,
            "check": _check(text, outputs, question, context)}
