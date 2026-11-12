"""
Market comparison blocks for a dashboard (any front end).  OWNER: C1.  Deterministic, no model.

    window(period)                  -> the trading dates of "3m" (63 days), "6m" (126) or "all"
    versus_market(isin, period)     -> "You vs market": price, turnover and trading cost vs the index, with ranks
    market_days(isin, period, n)    -> "Big market days": how the share moved on the strongest market days
    timeline(isin, period)          -> one chart: turnover / trading cost / auction share with the index median
    event_list(isin, period)        -> calendar entries and unusual days in one list, newest first
    dashboard(isin, period)         -> everything the dashboard shows, in one dict

Definitions (one place, so every screen agrees):
- "Index" = the other current members of the share's index (DAX / MDAX / SDAX), equal-weighted. Its daily move
  is `peer_ret` from the ingest, the same number the impact card subtracts, so share - index = stock-specific
  move on every day. It is NOT the official index level.
- Ranks and index medians use the current index members (universe.csv member_now) with data in the period;
  ranks include the share, medians exclude it.
- "x normal" for turnover and trading cost is engine.compare.day_ratios (the impact-card baseline).
"""
from functools import lru_cache

import numpy as np
import pandas as pd

from engine import baseline, compare, data

PERIODS = {"3m": 63, "6m": 126, "all": None}
MARKET_DAYS_N = 10
MARKET_DAYS_BY_VOLUME = 3   # of the n rows, up to this many are market-wide volume days not already in the list
ROLL = 10                   # days of the rolling median shown for the auction share


def _f(v, nd=6):
    return None if v is None or pd.isna(v) else round(float(v), nd)


def window(period: str = "3m") -> list[pd.Timestamp]:
    if period not in PERIODS:
        raise ValueError(f"period must be one of {tuple(PERIODS)}")
    dates = np.sort(data.daily()["date"].unique())
    n = PERIODS[period]
    return [pd.Timestamp(d) for d in (dates if n is None else dates[-n:])]


def _members(isin: str) -> tuple[str, pd.DataFrame]:
    d = data.daily()
    idx = d.loc[d["isin"] == isin, "idx_latest"].iloc[-1]
    now = compare.current_members() | {isin}   # current members only (SDAX = 70, not 80)
    return idx, d[(d["idx_latest"] == idx) & d["isin"].isin(now)]


def _compound(ret: pd.Series):
    r = ret.dropna()
    return None if r.empty else float((1 + r).prod() - 1)


def _rank(values: pd.Series, isin: str, high_is_first: bool) -> dict:
    v = values.dropna()
    if isin not in v.index:
        return {"rank": None, "of": int(len(v))}
    return {"rank": int(v.rank(ascending=not high_is_first, method="min")[isin]), "of": int(len(v))}


@lru_cache(maxsize=256)
def versus_market(isin: str, period: str = "3m") -> dict:
    """The share against its index for the period: price performance, turnover and trading cost, each with the
    rank among the index members, plus the sector and similar-size medians (engine.compare.peer_medians)."""
    dates = window(period)
    idx, mem = _members(isin)
    w = mem[mem["date"].isin(dates)]
    me = w[w["isin"] == isin].sort_values("date")
    perf = w.sort_values("date").groupby("isin")["ret"].apply(_compound)
    to = w.groupby("isin")["turnover_eur"].median()
    xlm = w.groupby("isin")["xlm_25k"].median()
    pm = compare.peer_medians(isin, len(dates))
    groups = {by: {"label": g["label"], "name": g["name"], "n": g["n"],
                   "turnover_eur": (g["values"] or {}).get("turnover_eur"), "xlm_25k": (g["values"] or {}).get("xlm_25k")}
              for by, g in pm["groups"].items() if by != "index" and not (by == "sector" and g["fallback"])}
    return {
        "isin": isin, "index": idx, "period": period, "days": len(dates),
        "from": str(dates[0].date()), "to": str(dates[-1].date()),
        "index_note": f"equal-weighted move of the other {idx} members; not the official index level",
        "price": {"stock": _f(perf.get(isin)), "index": _f(_compound(me["peer_ret"])), **_rank(perf, isin, True)},
        "turnover_eur": {"stock": _f(to.get(isin), 0), "index": _f(to.drop(isin, errors="ignore").median(), 0),
                         **_rank(to, isin, True)},
        "xlm_25k": {"stock": _f(xlm.get(isin), 2), "index": _f(xlm.drop(isin, errors="ignore").median(), 2),
                    **_rank(xlm, isin, False)},
        "groups": groups,
    }


@lru_cache(maxsize=256)
def _market_days(isin: str, period: str, n: int) -> tuple:
    dates = window(period)
    s = data.stock(isin)
    s = s[s["date"].isin(dates)].set_index("date")
    canon = compare.day_ratios(isin)
    s = s[s["peer_ret"].notna() & s["ret"].notna()]
    ctx = {d: baseline.market_context(isin, str(d.date())) for d in s.index}
    wide = [d for d in s.index if "market_wide_volume" in ctx[d]]
    by_move = list(s["peer_ret"].abs().sort_values(ascending=False).index)
    extra = sorted((d for d in wide if d not in by_move[: n - MARKET_DAYS_BY_VOLUME]),
                   key=lambda d: -(canon["vol_ratio"].get(d) or 0))[:MARKET_DAYS_BY_VOLUME]
    pick = by_move[: n - len(extra)] + extra
    rows = []
    for d in sorted(set(pick), reverse=True):
        r = s.loc[d]
        rows.append({"date": str(d.date()), "index_ret": _f(r["peer_ret"]), "ret": _f(r["ret"]),
                     "abn_ret": _f(r["abn_ret"]), "vol_ratio": _f(canon["vol_ratio"].get(d), 2),
                     "xlm_ratio": _f(canon["xlm_ratio"].get(d), 2),
                     "why": "market_wide_volume" if d in extra else "index_move", "context": ctx[d]})
    return tuple(rows)


def market_days(isin: str, period: str = "3m", n: int = MARKET_DAYS_N) -> list[dict]:
    """The n strongest market days of the period for this share's index: the largest absolute index moves, plus
    up to MARKET_DAYS_BY_VOLUME market-wide volume days. Newest first."""
    return [dict(r) for r in _market_days(isin, period, n)]


@lru_cache(maxsize=256)
def _event_list(isin: str, period: str) -> tuple:
    dates = set(window(period))
    canon = compare.day_ratios(isin)
    s = data.stock(isin).set_index("date")
    ev = data.events()
    ev = ev[ev["isin"] == isin]
    ep = baseline.anomaly_episodes(isin)
    peak = {pd.Timestamp(r["peak_date"]): r for r in ep.to_dict("records")}
    rows, used = [], set()
    for e in ev.to_dict("records"):
        day = pd.Timestamp(e["reaction_day"])
        if day not in dates:
            continue
        used.add(day)
        a = peak.get(day)
        rows.append({"day": str(day.date()), "published": str(pd.Timestamp(e["date"]).date()),
                     "time": e.get("time_local") or None, "timing": e.get("timing") or None,
                     "event_id": e["event_id"], "type": e["type"], "title": e["title"],
                     "source_url": e.get("source_url") or None, "unusual": a is not None,
                     "reason": a["reason"] if a else None,
                     "abn_ret": _f(s["abn_ret"].get(day)), "vol_ratio": _f(canon["vol_ratio"].get(day), 2),
                     "context": baseline.market_context(isin, str(day.date()))})
    for day, a in peak.items():
        if day in dates and day not in used:
            rows.append({"day": str(day.date()), "published": None, "time": None, "timing": None, "event_id": None,
                         "type": "UNUSUAL_DAY", "title": None, "source_url": None, "unusual": True,
                         "reason": a["reason"], "abn_ret": _f(s["abn_ret"].get(day)),
                         "vol_ratio": _f(canon["vol_ratio"].get(day), 2),
                         "context": baseline.market_context(isin, str(day.date()))})
    return tuple(sorted(rows, key=lambda r: (r["day"], r["event_id"] or ""), reverse=True))


def event_list(isin: str, period: str = "3m") -> list[dict]:
    """Calendar entries (by reaction day, with the publication date and time) and unusual days without an
    entry, newest first. Figures are for that day with the impact-card baseline."""
    return [dict(r) for r in _event_list(isin, period)]


def timeline(isin: str, period: str = "3m") -> dict:
    """Daily turnover, trading cost (XLM 25k) and auction share (rolling median) with the index median."""
    dates = window(period)
    idx, _ = _members(isin)
    s = data.stock(isin).set_index("date")
    roll = s["auction_share"].rolling(ROLL, min_periods=3).median()
    bench = {c: baseline.index_benchmark(idx, c) for c in ("turnover_eur", "xlm_25k", "auction_share")}
    iroll = bench["auction_share"].rolling(ROLL, min_periods=3).median()

    def col(series, nd):
        return [_f(series.get(d), nd) for d in dates]

    return {"date": [str(d.date()) for d in dates],
            "turnover_eur": col(s["turnover_eur"], 0), "index_turnover_eur": col(bench["turnover_eur"], 0),
            "xlm_25k": col(s["xlm_25k"], 2), "index_xlm_25k": col(bench["xlm_25k"], 2),
            "auction_share": col(roll, 4), "index_auction_share": col(iroll, 4),
            "auction_share_note": f"{ROLL}-day rolling median"}


def dashboard(isin: str, period: str = "3m") -> dict:
    s = data.stock(isin)
    if s.empty:
        raise KeyError(isin)
    vm = versus_market(isin, period)
    k = baseline.kpis(isin)
    lt = baseline.liquidity_trend(isin)
    rows = event_list(isin, period)
    sector = compare.peer_group(isin, "sector")
    return {
        "isin": isin, "ticker": s["ticker"].iloc[-1], "name": data.display_name(isin), "index": vm["index"],
        "sector": None if sector["fallback"] else sector["name"], "period": period,
        "from": vm["from"], "to": vm["to"], "days": vm["days"],
        "liquidity_category": k["liquidity_check"]["category_estimate"],
        "liquidity_check": k["liquidity_check"], "liquidity_trend": {"verdict": lt["verdict"], "summary": lt["summary"]},
        "tiles": {"turnover_eur": vm["turnover_eur"], "xlm_25k": vm["xlm_25k"], "price": vm["price"],
                  "unusual_days": sum(1 for r in rows if r["unusual"])},
        "versus_market": vm, "market_days": market_days(isin, period), "timeline": timeline(isin, period),
        "events": rows,
    }
