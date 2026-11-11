"""
Part A - the "normal state" of a stock.  OWNER: C2 (engine).  STATUS: v1 works.

    profile(isin)              daily time series for the dashboard
    index_benchmark(idx, col)  median of a column across the stock's index, per day
    anomalies(isin)            unusual days ("notable days") with a reason and a market context
    kpis(isin)                 headline numbers vs. index, sector and size-proxy medians + Xetra liquidity check
    liquidity_trend(isin)      "has our liquidity improved?" last 60 vs previous 60 trading days
    anomaly_episodes(isin)     consecutive unusual days merged into one episode
    market_context(isin, day)  index / calendar / market-wide flags of a day (CONTEXT_HELP explains them)

Peer groups (index / sector / turnover cohort as size proxy) come from engine.compare.peer_group.
"""
from functools import lru_cache

import numpy as np
import pandas as pd

from config import (ANOMALY_Z, DS_LOOKBACK_DAYS, DS_TURNOVER_MIN_EUR, DS_XLM_MAX_BPS, LIQUIDITY_TREND_TOL,
                    MARKET_WIDE_SHARE, MARKET_WIDE_VOL_RATIO, MIN_PEER_GROUP)
from engine.compare import peer_group
from engine.data import daily, events, stock

PROFILE_COLS = [
    "date", "price", "ret", "abn_ret", "peer_ret", "turnover_eur", "turnover_med60", "vol_ratio",
    "vol_z", "abn_ret_z", "xlm_25k", "xlm_100k", "xlm_25k_ratio", "auction_share",
    "agent_share", "prop_share", "mm_share", "agent_aggr_imbalance", "flow_censored",
]


def profile(isin: str, start=None, end=None) -> pd.DataFrame:
    s = stock(isin)
    if start is not None:
        s = s[s["date"] >= pd.Timestamp(start)]
    if end is not None:
        s = s[s["date"] <= pd.Timestamp(end)]
    return s[[c for c in PROFILE_COLS if c in s]]


def index_benchmark(idx: str, col: str) -> pd.Series:
    """Daily median of `col` across all stocks whose latest index is `idx`."""
    d = daily()
    return d[d["idx_latest"] == idx].groupby("date")[col].median()


def anomalies(isin: str, z: float = ANOMALY_Z) -> pd.DataFrame:
    s = stock(isin)
    reasons = pd.DataFrame({
        "volume spike": s["vol_z"] >= z,
        "stock-specific move": s["abn_ret_z"].abs() >= z,
        "spread widening": s.get("xlm_25k_ratio", pd.Series(np.nan, index=s.index)) >= 2,
    })
    hit = reasons.any(axis=1) & ~s["possible_corp_action"]
    out = s.loc[hit, ["date", "ret", "abn_ret", "vol_ratio", "vol_z", "abn_ret_z", "xlm_25k_ratio"]].copy()
    if out.empty:  # apply() on an empty frame returns a DataFrame, not a Series
        return out.assign(reason=pd.Series(dtype=str), severity=pd.Series(dtype=float),
                          context=pd.Series(dtype=str))
    out["reason"] = reasons[hit].apply(lambda r: ", ".join(r.index[r]), axis=1)
    out["severity"] = out["abn_ret_z"].abs().fillna(0) + out["vol_z"].clip(lower=0).fillna(0)
    out["context"] = context_frame(out.assign(isin=isin))
    return out.sort_values("date", ascending=False).reset_index(drop=True)


# ---------- market context: is an unusual day company news or an index / calendar day? ----------
CONTEXT_FLAGS = ("index_event", "index_change", "quarterly_expiry", "monthly_expiry", "month_end_review",
                 "market_wide_volume")
CONTEXT_HELP = {
    "index_event": "Index inclusion or deletion listed in events.csv (type INDEX). Index funds trade at the close, "
                   "so volume jumps without company news.",
    "index_change": "The stock's DAX/MDAX/SDAX membership changed on this day (from the daily index lists).",
    "quarterly_expiry": "Third Friday of Mar/Jun/Sep/Dec: options and futures expiry and the DAX index family "
                        "rebalancing. Volume is high for many stocks.",
    "monthly_expiry": "Third Friday of the month: monthly options expiry. Volume can be higher than normal.",
    "month_end_review": "Last trading day of Feb/May/Aug/Nov: possible MSCI index review date. "
                        "Index funds may rebalance at the close.",
    "market_wide_volume": f"At least {MARKET_WIDE_SHARE:.0%} of all stocks traded more than "
                          f"{MARKET_WIDE_VOL_RATIO:.0f}x their normal turnover: a market-wide day, not company news.",
}


@lru_cache(maxsize=1)
def _calendar_context() -> dict:
    """trading day -> calendar / market-wide flags, for every trading day in the data."""
    d = daily()
    days = pd.DatetimeIndex(sorted(d["date"].unique()))
    flags = {day: [] for day in days}
    for month in days.to_period("M").unique():
        first = month.start_time
        third_friday = first + pd.Timedelta(days=(4 - first.weekday()) % 7 + 14)
        expiry = days[(days <= third_friday) & (days >= first)]   # holiday -> previous trading day
        if len(expiry):
            flags[expiry[-1]].append("quarterly_expiry" if month.month in (3, 6, 9, 12) else "monthly_expiry")
    for month in days.to_period("M").unique():
        in_month = days[days.to_period("M") == month]
        if month.month in (2, 5, 8, 11) and days[-1] > in_month[-1]:  # only complete months
            flags[in_month[-1]].append("month_end_review")
    share = (d["vol_ratio"] > MARKET_WIDE_VOL_RATIO).groupby(d["date"]).mean()
    for day in share.index[share >= MARKET_WIDE_SHARE]:
        flags[day].append("market_wide_volume")
    return flags


@lru_cache(maxsize=1)
def _index_events() -> frozenset:
    """(isin, reaction_day) of every INDEX event in events.csv."""
    e = events()
    e = e[(e["type"] == "INDEX") & e["isin"].notna() & e["reaction_day"].notna()]
    return frozenset(zip(e["isin"], pd.to_datetime(e["reaction_day"])))


@lru_cache(maxsize=1)
def _index_changes() -> frozenset:
    """(isin, date) where the stock's index differs from its previous trading day (entry and exit included)."""
    d = daily().sort_values(["isin", "date"])
    idx = d["idx"].fillna("none")
    changed = (idx != idx.groupby(d["isin"]).shift()) & d["isin"].duplicated()
    return frozenset(zip(d.loc[changed, "isin"], d.loc[changed, "date"]))


def context_frame(df: pd.DataFrame) -> pd.Series:
    """Context flags for each row of `df` (columns isin, date) as one string, e.g. "index_event, month_end_review"."""
    cal, ev, ch = _calendar_context(), _index_events(), _index_changes()
    out = []
    for isin, day in zip(df["isin"], pd.to_datetime(df["date"])):
        f = (["index_event"] if (isin, day) in ev else []) + (["index_change"] if (isin, day) in ch else [])
        out.append(", ".join(f + cal.get(day, [])))
    return pd.Series(out, index=df.index, dtype=object)


def market_context(isin: str, day) -> list[str]:
    """Why a day may be unusual without company news. Flags in CONTEXT_FLAGS order; see CONTEXT_HELP."""
    s = context_frame(pd.DataFrame({"isin": [isin], "date": [pd.Timestamp(day)]})).iloc[0]
    return s.split(", ") if s else []


def kpis(isin: str, days: int = 60) -> dict:
    s = stock(isin)
    idx = s["idx_latest"].iloc[-1]
    recent = s.tail(days)
    d = daily()
    peers = d[(d["idx_latest"] == idx) & (d["date"] >= recent["date"].min())]
    peer_med = peers.groupby("isin")[["turnover_eur", "xlm_25k", "auction_share", "agent_share"]].median().median()

    lookback = s.tail(DS_LOOKBACK_DAYS)
    avg_turnover = float(lookback["turnover_eur"].mean())
    xlm = float(lookback["xlm_25k"].median())
    category = "A" if (xlm <= DS_XLM_MAX_BPS and avg_turnover >= DS_TURNOVER_MIN_EUR) else "B"

    # Sector and turnover-cohort (size proxy) medians, computed like the index median (group incl. the stock)
    kcols = ["turnover_eur", "xlm_25k", "auction_share", "agent_share"]
    groups = {by: peer_group(isin, by) for by in ("index", "sector", "size")}
    group_med = {}
    for by in ("sector", "size"):
        g = groups[by]
        members = d[d["isin"].isin(g["isins"] + [isin]) & (d["date"] >= recent["date"].min())]
        group_med[by] = members.groupby("isin")[kcols].median().median()
    flags = ["small_peer_group"] if any(g["n"] < MIN_PEER_GROUP for g in groups.values()) else []
    if groups["sector"]["fallback"]:
        flags.append("no_sector")  # sector unknown -> the sector median is the index median

    def _num(v):
        return None if pd.isna(v) else float(v)

    def pair(col):
        return {"stock": float(recent[col].median()), "index_median": float(peer_med[col]),
                "sector_median": _num(group_med["sector"][col]), "size_median": _num(group_med["size"][col])}

    return {
        "isin": isin, "ticker": s["ticker"].iloc[-1], "name": s["name"].iloc[-1], "index": idx,
        "period": f"last {days} trading days",
        "median_turnover_eur": pair("turnover_eur"),
        "median_xlm_25k_bps": pair("xlm_25k"),
        "median_auction_share": pair("auction_share"),
        "median_agent_share": pair("agent_share"),
        "liquidity_check": {
            "avg_turnover_eur_4m": avg_turnover, "median_xlm_25k_bps_4m": xlm,
            "category_estimate": category,
            "note": "Approximation of Xetra liquidity category A (XLM <= 100 bps and >= EUR 2.5m/day); "
                    "category B needs a Designated Sponsor for continuous trading.",
        },
        "anomaly_days_last_period": int((anomalies(isin)["date"] >= recent["date"].min()).sum()),
        "peer_groups": {by: {k: g[k] for k in ("name", "label", "n", "fallback")} for by, g in groups.items()},
        "flags": flags,
    }


# ---------- liquidity trend: "has our liquidity improved?" ----------
TREND_HELP = {
    "improved": "Trading got cheaper and/or more shares traded, and nothing got worse by more than 10%. "
                "A good message for the board; check whether the whole index moved the same way.",
    "worsened": "Trading got more expensive and/or fewer shares traded, and nothing improved by more than 10%. "
                "Worth a conversation with the Designated Sponsor or a look at investor outreach.",
    "mixed": "Trading got cheaper, but fewer shares traded (or the other way round). "
             "Check both before telling the board that liquidity improved.",
    "stable": "Trading cost and turnover both stayed within 10% of the previous period.",
    None: "Not enough trading history for a comparison yet.",
}


def _chg(new, old):
    """Relative change, None when a value is missing or the base is zero."""
    if new is None or old is None or old == 0:
        return None
    return round(float(new / old - 1), 4)


def _med(x: pd.Series, nd: int = 2):
    v = x.median()
    return None if pd.isna(v) else round(float(v), nd)


def _word(chg: float, lower_is_better: bool) -> str:
    if abs(chg) < LIQUIDITY_TREND_TOL:
        return "about the same"
    return "better" if (chg < 0) == lower_is_better else "worse"


def _verdict(xlm_chg, to_chg, tol: float = LIQUIDITY_TREND_TOL) -> str:
    """Absolute verdict. Lower XLM = better, higher turnover = better. A missing metric is ignored."""
    better = (xlm_chg is not None and xlm_chg <= -tol) or (to_chg is not None and to_chg >= tol)
    worse = (xlm_chg is not None and xlm_chg >= tol) or (to_chg is not None and to_chg <= -tol)
    return "mixed" if better and worse else "improved" if better else "worsened" if worse else "stable"


def _ds_category(frame: pd.DataFrame) -> str | None:
    """Same rule as kpis(): XLM 25k <= DS_XLM_MAX_BPS and average turnover >= DS_TURNOVER_MIN_EUR -> A."""
    xlm, avg = frame["xlm_25k"].median(), frame["turnover_eur"].mean()
    if pd.isna(xlm) or pd.isna(avg):
        return None
    return "A" if (xlm <= DS_XLM_MAX_BPS and avg >= DS_TURNOVER_MIN_EUR) else "B"


def liquidity_trend(isin: str, window: int = 60) -> dict:
    """Last `window` trading days vs the `window` days before, for the stock and its index median."""
    s = stock(isin)
    idx = s["idx_latest"].iloc[-1]
    n = len(s)
    flags = ["short_history"] if n < 2 * window else []
    now, before = s.tail(window), s.iloc[max(0, n - 2 * window): max(0, n - window)]

    metrics = (("xlm_25k_bps", "xlm_25k"), ("turnover_eur", "turnover_eur"))
    bench = {col: index_benchmark(idx, col) for _, col in metrics}
    nd = {"xlm_25k": 2, "turnover_eur": 0}
    stock_vals = {k: {"before": _med(before[col], nd[col]), "now": _med(now[col], nd[col])} for k, col in metrics}
    index_vals = {k: {"before": _med(bench[col].reindex(before["date"]), nd[col]),
                      "now": _med(bench[col].reindex(now["date"]), nd[col])} for k, col in metrics}
    chg = {k: _chg(v["now"], v["before"]) for k, v in stock_vals.items()}
    ichg = {k: _chg(v["now"], v["before"]) for k, v in index_vals.items()}
    if chg["xlm_25k_bps"] is None:
        flags.append("no_xlm")  # XLM only exists while the stock is an index member

    verdict = None if "short_history" in flags else _verdict(chg["xlm_25k_bps"], chg["turnover_eur"])

    # Market-wide or just us? Only the metrics that moved beyond the threshold count.
    vs_index = None
    if verdict in ("improved", "worsened", "mixed"):
        moved = [k for k, c in chg.items() if c is not None and abs(c) >= LIQUIDITY_TREND_TOL]
        own = [k for k in moved if ichg[k] is None or abs(chg[k] - ichg[k]) >= LIQUIDITY_TREND_TOL]
        vs_index = "stock-specific" if own else "market-wide"

    # Same check against the sector median (vs_sector); only when the sector group is real and big enough.
    sec = peer_group(isin, "sector")
    d = daily()
    sbench = d[d["isin"].isin(sec["isins"] + [isin])].groupby("date")[["xlm_25k", "turnover_eur"]].median()
    sector_vals = {k: {"before": _med(sbench[col].reindex(before["date"]), nd[col]),
                       "now": _med(sbench[col].reindex(now["date"]), nd[col])} for k, col in metrics}
    schg = {k: _chg(v["now"], v["before"]) for k, v in sector_vals.items()}
    vs_sector = None
    if sec["fallback"]:
        flags.append("no_sector")
    elif sec["n"] < MIN_PEER_GROUP:
        flags.append("small_peer_group")
    elif verdict in ("improved", "worsened", "mixed"):
        moved = [k for k, c in chg.items() if c is not None and abs(c) >= LIQUIDITY_TREND_TOL]
        own = [k for k in moved if schg[k] is None or abs(chg[k] - schg[k]) >= LIQUIDITY_TREND_TOL]
        vs_sector = "stock-specific" if own else "sector-wide"

    ds = {"now": _ds_category(s.tail(DS_LOOKBACK_DAYS)),
          "before": _ds_category(s.iloc[max(0, n - 2 * DS_LOOKBACK_DAYS): max(0, n - DS_LOOKBACK_DAYS)])}

    m = s.assign(month=s["date"].dt.strftime("%Y-%m"),
                 index_xlm=bench["xlm_25k"].reindex(s["date"]).to_numpy(),
                 index_to=bench["turnover_eur"].reindex(s["date"]).to_numpy())
    monthly = [{"month": mo, "xlm_25k_bps": _med(g["xlm_25k"]), "turnover_eur": _med(g["turnover_eur"], 0),
                "index_xlm_25k_bps": _med(g["index_xlm"]), "index_turnover_eur": _med(g["index_to"], 0)}
               for mo, g in m.groupby("month")]

    # Summary: every number comes from the fields above.
    period = f"last {window} vs previous {window} trading days"
    if verdict is None:
        summary = f"Not enough trading history for a liquidity trend ({n} trading days, need {2 * window})."
    else:
        parts = []
        if chg["xlm_25k_bps"] is not None:
            parts.append(f"trading cost {chg['xlm_25k_bps'] * 100:+.0f}% ({_word(chg['xlm_25k_bps'], True)})")
        if chg["turnover_eur"] is not None:
            parts.append(f"turnover {chg['turnover_eur'] * 100:+.0f}% ({_word(chg['turnover_eur'], False)})")
        summary = f"{verdict.capitalize()}: " + ", ".join(parts) + f", {period}."
        iparts = [f"{label} {ichg[k] * 100:+.0f}%" for k, label in
                  (("xlm_25k_bps", "trading cost"), ("turnover_eur", "turnover")) if ichg[k] is not None]
        if iparts:
            summary += f" {idx} median: " + ", ".join(iparts) + "."
        if ds["now"] and ds["before"] and ds["now"] != ds["before"]:
            summary += f" Designated Sponsor category estimate: {ds['before']} -> {ds['now']}."

    return {
        "isin": isin, "ticker": s["ticker"].iloc[-1], "index": idx, "window": window, "period": period,
        "stock": stock_vals, "index_median": index_vals,
        "xlm_25k_change_pct": chg["xlm_25k_bps"], "turnover_change_pct": chg["turnover_eur"],
        "index_xlm_25k_change_pct": ichg["xlm_25k_bps"], "index_turnover_change_pct": ichg["turnover_eur"],
        "sector": None if sec["fallback"] else sec["name"], "sector_median": sector_vals,
        "sector_xlm_25k_change_pct": schg["xlm_25k_bps"], "sector_turnover_change_pct": schg["turnover_eur"],
        "verdict": verdict, "vs_index": vs_index, "vs_sector": vs_sector, "help": TREND_HELP[verdict],
        "ds_category": ds, "monthly": monthly, "summary": summary, "flags": flags,
    }


# ---------- anomaly episodes ----------
EPISODE_COLS = ["start", "end", "days", "peak_date", "peak_abn_ret", "total_abn_ret", "max_vol_ratio",
                "reason", "severity", "context"]


def anomaly_episodes(isin: str, z: float = ANOMALY_Z) -> pd.DataFrame:
    """Consecutive unusual trading days (Fri + Mon count as consecutive) merged into one episode.
    peak = the day with the highest severity; total_abn_ret = sum of abnormal returns of the episode days."""
    a = anomalies(isin, z)
    if a.empty:
        return pd.DataFrame(columns=EPISODE_COLS)
    day_no = pd.Series(np.arange(len(stock(isin))), index=stock(isin)["date"])  # trading-day number
    a = a.sort_values("date").reset_index(drop=True)
    a["episode"] = day_no.reindex(a["date"]).to_numpy() - np.arange(len(a))  # constant within a run of days
    rows = []
    for _, g in a.groupby("episode", sort=False):
        peak = g.loc[g["severity"].idxmax()]
        reasons = dict.fromkeys(r for rs in g["reason"] for r in rs.split(", "))
        ctx = {f for cs in g["context"] for f in cs.split(", ") if f}
        rows.append({"start": g["date"].min(), "end": g["date"].max(), "days": len(g),
                     "peak_date": peak["date"], "peak_abn_ret": peak["abn_ret"],
                     "total_abn_ret": g["abn_ret"].sum(min_count=1), "max_vol_ratio": g["vol_ratio"].max(),
                     "reason": ", ".join(reasons), "severity": g["severity"].max(),
                     "context": ", ".join(f for f in CONTEXT_FLAGS if f in ctx)})
    return pd.DataFrame(rows, columns=EPISODE_COLS).sort_values("start", ascending=False).reset_index(drop=True)
