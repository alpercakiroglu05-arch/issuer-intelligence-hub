"""
Market-intelligence layer: WHY a share moved, from cited external sources + the engine's figures.  Deterministic
core, the language model only phrases.

    explain_event(isin, day, event_id, lang, fresh=False) -> dict | None   "Why the market reacted" (impact card)
    explain_period(isin, period, lang, fresh=False) -> dict | None        "Market intelligence" (overview, 1M/3M/YTD/1Y)
    available(isin) -> {"events": [event_id], "periods": True}            what exists for a share

Where the "why" comes from: events/intel/<TICKER>.json, a research pack per company. Each item paraphrases one or
more public sources (publisher, title, URL, publication day) and is tagged with a kind (expectations, guidance,
analyst, competition, ...) and a direction. The pack is curated for the demo companies; in production the same
format is filled by a news / consensus feed. Nothing outside the pack is ever cited.

Rules (the mentor brief "Kausale KI-Erklärung"):
- evidence-based: an external statement is shown only with its source;
- expectation-aware: items about expectations and guidance rank first when they point the same way as the move;
- time-consistent: for an event, an item published after the reaction day is labelled "later reporting";
- no false causality: the text says "consistent with", never "caused by"; what stays open is said;
- numbers come from the engine or the pack (ai/checks.py), the model phrases only. If its JSON is invalid, cites an
  unknown item, uses a figure that is in neither, or claims a cause, the deterministic text is shown instead.
"""
import json
import math
import re
from functools import lru_cache

import pandas as pd

from ai import llm
from ai.checks import unsupported_numbers
from config import REPO_ROOT
from engine import compare, data, impact, market

INTEL_DIR = REPO_ROOT / "events" / "intel"
MAX_DRIVERS = 4
KIND = {  # how a driver is named in the deterministic headline
    "expectations": ("expectations", "Erwartungen"), "guidance": ("the outlook", "den Ausblick"),
    "analyst": ("analyst views", "Analystenstimmen"), "competition": ("the competitive picture", "die Wettbewerbslage"),
    "company": ("the reported figures", "die gemeldeten Zahlen"), "management": ("management and insider news", "Management- und Insidermeldungen"),
    "index": ("index flows", "Indexflüsse"), "regulatory": ("regulatory news", "regulatorische Nachrichten"),
    "investor": ("investor news", "Investorennachrichten"), "market": ("chart signals", "Chartsignale"),
}
CAUSAL = re.compile(r"\b(caused by|was caused|were caused|because of the|due to the news|verursacht|ausgelöst durch|lag (allein )?an)\b",
                    re.I)


# ---------------------------------------------------------------- packs
def _ticker(isin: str) -> str | None:
    u = data.daily()
    hit = u.loc[u["isin"] == isin, "ticker"]
    return str(hit.iloc[0]) if len(hit) else None


@lru_cache(maxsize=16)
def _load(ticker: str) -> dict | None:
    p = INTEL_DIR / f"{ticker}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    for it in d["items"]:
        it["sources"] = [dict(d["sources"][s], id=s) for s in it["src"]]
    return d


def pack(isin: str) -> dict | None:
    t = _ticker(isin)
    return _load(t) if t else None


def available(isin: str) -> dict:
    p = pack(isin)
    return {"events": sorted(p.get("events", {})) if p else [], "periods": bool(p)}


# ---------------------------------------------------------------- formatting (EN / DE house style)
def _num(x: float, nd: int, de: bool) -> str:
    s = f"{abs(x):,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") if de else s


def _pct(x, de, nd=1, sign=True) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    sg = ("−" if x < 0 else "+" if x > 0 else "") if sign else ""
    return f"{sg}{_num(x * 100, nd, de)}{' %' if de else '%'}"


def _pp(x, de) -> str:
    sg = "−" if x < 0 else "+" if x > 0 else ""
    return f"{sg}{_num(x * 100, 1, de)}{' Pp.' if de else ' pp'}"


def _eur(x, de) -> str:
    if x is None:
        return "n/a"
    if abs(x) >= 1e6:
        return f"{_num(x / 1e6, 1, de)} Mio. €" if de else f"€{_num(x / 1e6, 1, de)}m"
    if abs(x) >= 1e3:
        return f"{_num(x / 1e3, 0, de)} Tsd. €" if de else f"€{_num(x / 1e3, 0, de)}k"
    return f"{_num(x, 0, de)} €" if de else f"€{_num(x, 0, de)}"


def _r0(x) -> str:
    return str(int(math.floor(x + 0.5)))


def _x(x, de) -> str:
    return f"{_num(x, 1, de)}×"


# ---------------------------------------------------------------- engine facts
def _sector_move(isin: str, day: pd.Timestamp) -> dict | None:
    g = compare.peer_group(isin, "sector")
    if g.get("fallback") or not g.get("isins"):
        return None
    d = data.daily()
    r = d[(d["date"] == day) & (d["isin"].isin(g["isins"]))]["ret"].dropna()
    return {"name": g["name"], "ret": round(float(r.mean()), 6), "n": int(len(r))} if len(r) >= 3 else None


def event_facts(isin: str, day: str, event_id: str) -> dict:
    e = data.events()
    hit = e[(e["isin"] == isin) & (e["event_id"] == event_id)]
    ev = hit.iloc[0].to_dict() if len(hit) else None
    c = impact.impact_card(isin, day, ev)
    p, v, li, a, pa = c["price"], c["volume"], c["liquidity"], c.get("auctions") or {}, c["participants"]
    onset = ((c.get("intraday") or {}).get("onset") or {})
    sec = _sector_move(isin, pd.Timestamp(day))
    f = {"company": c["name"], "index": c["index"], "day": day, "event_title": c["event"].get("title"),
         "published": c["event"].get("datetime_local"), "timing": c["event"].get("timing"),
         "ret": p["ret"], "peer_ret": p["peer_ret"], "abn_ret": p["abn_ret"], "gap_open": p.get("gap_open"),
         "ret_intraday": p.get("ret_intraday"), "car_0_5": p.get("car_0_5"),
         "turnover_ratio": v["ratio"], "turnover_eur": v["turnover_eur"], "turnover_normal_eur": v["baseline_eur"],
         "trading_cost_ratio": li.get("ratio"), "trading_cost_bps": li.get("xlm_25k_bps"),
         "open_auction_ratio": a.get("open_auction_ratio"), "client_imbalance": pa.get("agent_aggr_imbalance"),
         "client_net_eur": pa.get("agent_aggr_net_eur"), "onset_time": onset.get("time")}
    if sec:
        f.update({"sector": sec["name"], "sector_ret": sec["ret"], "abn_vs_sector": round(p["ret"] - sec["ret"], 6)})
    if isinstance(f["turnover_ratio"], (int, float)):
        f["normal_days_traded"] = round(f["turnover_ratio"])  # "as much as N normal days" (plain-language example)
    return f


def period_facts(isin: str, period: str) -> dict:
    d = market.dashboard(isin, period)
    vm, lt = d["versus_market"], d.get("liquidity_trend") or {}
    pr, to, xl = vm["price"], vm["turnover_eur"], vm["xlm_25k"]
    f = {"company": d["name"], "index": d["index"], "period": d["period"], "label": vm["label"], "from": pr["start_close"],
         "to": d["to"], "ret": pr["stock"], "peer_ret": pr["index"], "rel": round(pr["stock"] - pr["index"], 6),
         "rank": pr["rank"], "of": pr["of"], "turnover_eur": to["stock"], "turnover_index_eur": to["index"],
         "turnover_rank": to["rank"], "xlm_bps": xl["stock"], "xlm_index_bps": xl["index"], "xlm_rank": xl["rank"],
         "liquidity_trend": lt.get("verdict"), "xlm_change_pct": lt.get("xlm_25k_change_pct"),
         "turnover_change_pct": lt.get("turnover_change_pct")}
    if f["xlm_bps"] and f["xlm_index_bps"]:  # plain-language examples, so the model may use them as figures
        f["cost_25k_eur"] = round(25000 * f["xlm_bps"] / 1e4, 1)
        f["cost_25k_index_eur"] = round(25000 * f["xlm_index_bps"] / 1e4, 1)
    if f["turnover_eur"] and f["turnover_index_eur"]:
        f["turnover_vs_index"] = round(f["turnover_eur"] / f["turnover_index_eur"], 2)
    return f


# ---------------------------------------------------------------- choosing the drivers
def _rank(items: list, move: float) -> list:
    """Items that point the same way as the move first, then by weight; expectations/guidance break ties."""
    want = "neg" if move < 0 else "pos"
    pri = {"expectations": 0, "guidance": 1}
    return sorted(items, key=lambda it: (it["dir"] != want and it["dir"] != "neutral", -it["w"], pri.get(it["kind"], 2)))


def _event_items(p: dict, event_id: str, day: str) -> list:
    out = []
    for it in p["items"]:
        if it.get("event") == event_id:
            out.append(dict(it, timing="later" if it["date"] > day else "at_time"))
    return out


def _period_items(p: dict, start: str, end: str) -> list:
    return [dict(it, timing="in_period") for it in p["items"] if start < it["date"] <= end]


# ---------------------------------------------------------------- deterministic texts
def _kinds(items: list, de: bool) -> str:
    ks = []
    for it in items:
        k = KIND.get(it["kind"])
        if k and k[de] not in ks:
            ks.append(k[de])
    ks = ks[:2]
    return (" und " if de else " and ").join(ks) if ks else ("die zitierten Meldungen" if de else "the cited reporting")


def _reaction(f: dict, de: bool) -> str:
    s = (f"{f['company']} {_pct(f['ret'], de)} gegenüber {_pct(f['peer_ret'], de)} für die {f['index']}-Werte: "
         f"{_pp(f['abn_ret'], de)} relativ" if de else
         f"{f['company']} {_pct(f['ret'], de)} against {_pct(f['peer_ret'], de)} for the {f['index']} peers: "
         f"{_pp(f['abn_ret'], de)} relative")
    if f.get("sector_ret") is not None:
        s += (f"; Sektor {f['sector']} {_pct(f['sector_ret'], de)}" if de else f"; {f['sector']} sector {_pct(f['sector_ret'], de)}")
    return s + "."


def _trading(f: dict, de: bool) -> str:
    bits = []
    g, i = f.get("gap_open"), f.get("ret_intraday")
    if g is not None and i is not None and abs(g) >= 0.01 and g * i < 0:
        bits.append(f"Die Aktie eröffnete {_pct(g, de)} und verlor im fortlaufenden Handel {_pct(i, de)}: Die erste Lesart wurde im Tagesverlauf revidiert"
                    if de and g > 0 else
                    f"Die Aktie eröffnete {_pct(g, de)} und erholte sich im Handel um {_pct(i, de)}" if de else
                    f"The share opened {_pct(g, de)} and moved {_pct(i, de)} in continuous trading: the first reading was revised during the day"
                    if g > 0 else f"The share opened {_pct(g, de)} and recovered {_pct(i, de)} in continuous trading")
    elif g is not None and abs(g) >= 0.02 and abs(g) >= 0.5 * abs(f["ret"]):
        bits.append(f"Ein großer Teil der Bewegung fiel schon in der Eröffnungsauktion ({_pct(g, de)})" if de else
                    f"Much of the move came at the opening auction ({_pct(g, de)})")
    elif i is not None and abs(i) >= 0.5 * abs(f["ret"]) and abs(f["ret"]) >= 0.02:
        bits.append(f"Der Großteil der Bewegung kam im fortlaufenden Handel ({_pct(i, de)} nach der Eröffnung bei {_pct(g, de)})" if de else
                    f"Most of the move came in continuous trading ({_pct(i, de)} after an opening at {_pct(g, de)})")
    if f.get("onset_time"):
        bits.append(f"die Reaktion begann laut Minutendaten um {f['onset_time']}" if de else f"minute data show the reaction from {f['onset_time']}")
    vr = f.get("turnover_ratio")
    if isinstance(vr, (int, float)):
        bits.append(f"Umsatz {_x(vr, de)} normal ({_eur(f['turnover_eur'], de)}), also breiter Handel, kein dünner Markt" if de and vr >= 2 else
                    f"Umsatz nur {_x(vr, de)} normal" if de else
                    f"turnover {_x(vr, de)} normal ({_eur(f['turnover_eur'], de)}): broad trading, not a thin market" if vr >= 2 else
                    f"turnover only {_x(vr, de)} normal")
    ci = f.get("client_imbalance")
    if isinstance(ci, (int, float)) and abs(ci) >= 0.2:
        bits.append((f"Kundenorders waren per Saldo {'Verkäufer' if ci < 0 else 'Käufer'} ({_eur(abs(f['client_net_eur'] or 0), de)})") if de else
                    (f"client orders were net {'sellers' if ci < 0 else 'buyers'} ({_eur(abs(f['client_net_eur'] or 0), de)})"))
    if not bits:
        return ""
    s = "; ".join(bits)
    return s[0].upper() + s[1:] + "."


def _template_event(f, items, ev_meta, de):
    move = f["abn_ret"]
    top = [it for it in items if it["timing"] == "at_time"][:3] or items[:3]
    head = (f"Die Reaktion ({_pp(move, de)} gegenüber den {f['index']}-Werten) passt zu {_kinds(top, de)}, laut zitierten Quellen."
            if de else
            f"The reaction ({_pp(move, de)} against the {f['index']} peers) is consistent with {_kinds(top, de)}, according to the cited sources.")
    head = ev_meta.get("headline_de" if de else "headline_en") or head   # the curated key takeaway, if the pack has one
    return {"headline": head,
            "drivers": [{"id": it["id"], "text": it["de" if de else "en"]} for it in items[:MAX_DRIVERS]],
            "trading": _trading(f, de),
            "shown": ("Die relative Bewegung, der Umsatz und wer handelte (Xetra-Daten)." if de else
                      "The relative move, the turnover and who traded (Xetra data)."),
            "plausible": (f"Zitierte Berichte stützen {_kinds(top, de)} als Treiber." if de else
                          f"Cited reporting supports {_kinds(top, de)} as drivers."),
            "open": ev_meta.get("open_de" if de else "open_en", "")}


def _template_period(f, items, de):
    rel = f["rel"]
    drv = [it for it in items if it["kind"] != "watch"]
    watch = next((it for it in items if it["kind"] == "watch"), None)
    beat = rel >= 0
    head = ((f"{f['company']} lag im Zeitraum {f['label']} {_pp(rel, de)} {'vor' if beat else 'hinter'} den {f['index']}-Werten (Rang {f['rank']} von {f['of']}); "
             + (f"die zitierten Meldungen betreffen vor allem {_kinds(drv, de)}." if drv else "für den Zeitraum liegen keine zitierten Meldungen vor."))
            if de else
            (f"{f['company']} {'outperformed' if beat else 'underperformed'} its {f['index']} peers by {_pp(rel, de)} over {f['label']} "
             f"(rank {f['rank']} of {f['of']}); " + (f"the cited reporting is mostly about {_kinds(drv, de)}." if drv else
                                                    "no cited reporting covers the period.")))
    if drv and not any(it["kind"] in ("company", "guidance", "expectations") for it in drv):
        head += (" Im Zeitraum gab es keine Unternehmenszahlen oder Prognosen; die Meldungen erklären die Bewegung nur zum Teil." if de else
                 " There were no company results or guidance in the period, so the reporting explains the move only in part.")
    return {"headline": head,
            "drivers": [{"id": it["id"], "text": it["de" if de else "en"]} for it in drv[:3]],
            "trading": _quality(f, de),
            "watch": watch["de" if de else "en"] if watch else ""}


def _quality(f: dict, de: bool) -> str:
    tv, ce, ci = f.get("turnover_vs_index"), f.get("cost_25k_eur"), f.get("cost_25k_index_eur")
    if tv is None or ce is None:
        return ""
    if de:
        s = (f"Handelt mit {_eur(f['turnover_eur'], de)} pro Tag {'weniger als halb so viel wie' if tv < 0.5 else 'weniger als' if tv < 1 else 'mehr als'} der {f['index']}-Median "
             f"({_eur(f['turnover_index_eur'], de)}); ein Kauf und Verkauf von 25 T€ kostet rund {_r0(ce)} € statt {_r0(ci)} €.")
    else:
        s = (f"Trades {_eur(f['turnover_eur'], de)} a day, {'less than half' if tv < 0.5 else 'less than' if tv < 1 else 'more than'} the {f['index']} median "
             f"({_eur(f['turnover_index_eur'], de)}); buying and selling €25k costs about €{_r0(ce)} against €{_r0(ci)}.")
    return s


# ---------------------------------------------------------------- the model
SYSTEM_EVENT = """You are a senior investor-relations analyst. Explain WHY a share reacted to an announcement, for the IR team.
You get FACTS (Xetra trading figures from the engine, exact) and ITEMS (external reporting, each with an id, date, kind,
direction and timing: "at_time" = known on the reaction day, "later" = published afterwards).
Return ONLY a JSON object, no prose around it:
{"headline": "<one sentence, the key insight, max 30 words>",
 "drivers": [{"id": "<item id>", "text": "<one sentence: what the item says and how it fits the reaction>"}],
 "trading": "<1-2 sentences: what the trading data adds; does it support or contradict the drivers?>",
 "shown": "<what the data shows>", "plausible": "<what is a plausible interpretation>", "open": "<what stays unclear>"}
Rules:
- 2 to 4 drivers, most important first, only ids from ITEMS. A positive headline with a negative reaction usually means
  expectations: say so when items support it. Mark an item with timing "later" as later reporting.
- Use ONLY numbers that appear in FACTS or ITEMS (you may round; ratios as 3.2×). The relative move (abn_ret) is in
  percentage points ("pp", German "Pp."), not percent. Never compute new numbers.
- Never claim certainty about causes: write "consistent with", "points to", never "caused by". No advice, no forecasts.
- Plain words an IR manager can repeat to the board. Write in {language}."""

SYSTEM_PERIOD = """You are a senior investor-relations analyst writing a short management summary of how a share performed in a
period, what may be driving it, and what deserves attention. You get FACTS (engine figures, exact) and ITEMS (external
reporting in the period, each with an id, date, kind and direction).
Return ONLY a JSON object:
{"headline": "<one sentence key message, max 30 words>",
 "drivers": [{"id": "<item id>", "text": "<one sentence>"}],
 "trading": "<one sentence on trading quality: turnover and the cost of a €25k round trip vs the index, as plain examples>",
 "watch": "<one short sentence: what to watch next, or empty>"}
Rules: 0 to 3 drivers, only ids from ITEMS, most relevant first; if the items explain only part of the move, say so in
the headline. Use ONLY numbers from FACTS or ITEMS (round freely; cost_25k_eur are euro examples). Relative performance
(rel) is in percentage points. Never claim certainty about causes ("consistent with", "points to"). 80-120 words in
total. Write in {language}."""

LANG = {"en": "English", "de": "German"}


def _ask(system: str, facts: dict, items: list, lang: str, fresh: bool):
    payload = {"FACTS": facts, "ITEMS": [{k: it[k] for k in ("id", "date", "kind", "dir", "timing")} |
                                         {"text": it["de" if lang == "de" else "en"]} for it in items]}
    msg = llm.chat([{"role": "system", "content": system.replace("{language}", LANG.get(lang, "English"))},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)}],
                   cache=not fresh, temperature=0.2)
    raw = (msg.content or "").strip()
    m = re.search(r"\{.*\}", raw, flags=re.S)
    return (json.loads(m.group(0)) if m else None), bool(getattr(msg, "cached", False)), payload


def _check(out: dict, keys: tuple, items: list, payload: dict, min_drivers: int) -> list:
    bad = []
    if not isinstance(out, dict) or any(k not in out for k in keys):
        return ["the answer is not the requested JSON"]
    ids = {it["id"] for it in items}
    drv = out.get("drivers") or []
    if not isinstance(drv, list) or len(drv) < min_drivers or any(not isinstance(d, dict) or d.get("id") not in ids for d in drv):
        bad.append("a driver cites an item that is not in the pack")
    text = " ".join([str(out.get(k) or "") for k in keys if k != "drivers"] + [str(d.get("text", "")) for d in drv if isinstance(d, dict)])
    bad += unsupported_numbers(text, payload)
    if CAUSAL.search(text):
        bad.append("a causal claim")
    return bad


def _attach(out: dict, items: list) -> list:
    by = {it["id"]: it for it in items}
    res = []
    for d in out.get("drivers") or []:
        it = by.get(d["id"])
        if it:
            res.append({"id": it["id"], "kind": it["kind"], "dir": it["dir"], "date": it["date"], "timing": it["timing"],
                        "text": str(d.get("text") or "").strip(), "sources": it["sources"]})
    return res[:MAX_DRIVERS]


# ---------------------------------------------------------------- public
def explain_event(isin: str, day: str, event_id: str | None, lang: str = "en", fresh: bool = False) -> dict | None:
    p = pack(isin)
    if not p or not event_id or event_id not in p.get("events", {}):
        return None
    de = lang == "de"
    f = event_facts(isin, day, event_id)
    f["company"] = p.get("company", f["company"])
    items = _rank(_event_items(p, event_id, day), f["abn_ret"])
    meta = p["events"][event_id]
    tpl = _template_event(f, items, meta, de)
    res = {"kind": "event", "question": meta.get("question_de" if de else "question_en"), "reaction": _reaction(f, de),
           "source": "template", "model": None, "cached": False, "rejected": []}
    out = tpl
    try:
        o, cached, payload = _ask(SYSTEM_EVENT, f, items, lang, fresh)
        bad = _check(o, ("headline", "drivers", "trading", "shown", "plausible", "open"), items, payload, 2)
        if not bad:
            out = o
            res.update({"source": "llm", "model": llm.model_name(), "cached": cached})
        else:
            res["rejected"] = bad
    except Exception:  # noqa: BLE001  no key, network, bad JSON -> deterministic text
        pass
    res.update({"headline": out["headline"], "drivers": _attach(out, items), "trading": out.get("trading") or tpl["trading"],
                "assessment": {k: out.get(k) or tpl[k] for k in ("shown", "plausible", "open")},
                "later": [it["id"] for it in items if it["timing"] == "later"], "facts": f})
    return res


def explain_period(isin: str, period: str, lang: str = "en", fresh: bool = False) -> dict | None:
    p = pack(isin)
    if not p:
        return None
    de = lang == "de"
    f = period_facts(isin, period)
    f["company"] = p.get("company", f["company"])
    items = _rank(_period_items(p, f["from"], f["to"]), f["rel"])
    tpl = _template_period(f, items, de)
    res = {"kind": "period", "label": f["label"], "from": f["from"], "to": f["to"], "source": "template", "model": None,
           "cached": False, "rejected": []}
    out = tpl
    usable = [it for it in items if it["kind"] != "watch"]
    try:
        o, cached, payload = _ask(SYSTEM_PERIOD, f, items, lang, fresh)
        bad = _check(o, ("headline", "drivers", "trading", "watch"), items, payload, 0)
        if not bad:
            out = o
            res.update({"source": "llm", "model": llm.model_name(), "cached": cached})
        else:
            res["rejected"] = bad
    except Exception:  # noqa: BLE001
        pass
    res.update({"headline": out["headline"], "drivers": _attach(out, usable or items),
                "trading": out.get("trading") or tpl["trading"], "watch": out.get("watch") or "",
                "covered": len(usable), "facts": f})
    return res
