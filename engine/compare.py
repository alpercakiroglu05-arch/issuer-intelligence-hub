"""
Compare events of the same type.  OWNER: C2 (engine); first version by C1.

The challenge asks: "compare events of the same type, e.g. all quarterly results in the DAX over the past year".

    metrics_all()                          -> DataFrame, every stock-day with the impact-card metrics
    event_types()                          -> list of comparable types (NOTABLE_DAY + types in events.csv)
    same_type_events(event_type, index)    -> DataFrame, one row per event of that type
    percentile(card, table)                -> dict, where this card sits in the table
    comparison_for(card)                   -> dict | None, fills card["comparison"]
    sector_peers(isin)                     -> list[str] of ISINs (events/sectors.csv, fallback: same index)
    size_peers(isin)                       -> the SIZE_PEERS_N stocks closest in median turnover (size proxy, NOT market cap)
    peer_group(isin, by)                   -> dict, by = "index" | "sector" | "size"
    stock_medians(days) / peer_medians(isin) -> THE peer benchmark; web, Streamlit, report and assistant all use it

Event sources
-------------
- events.csv (research team): typed announcements (FY, Q1, H1, Q3, DIVIDEND_EX, ADHOC, ...), matched on reaction_day.
- NOTABLE_DAY: every unusual stock-day in the data, same rules as the dashboard (engine.baseline.anomalies):
  volume z >= 3, |abnormal return z| >= 3 or spread (XLM 25k) >= 2x normal; possible corporate actions excluded.
  So the comparison works even before the calendar is filled.

Metrics use exactly the impact-card definitions (baseline t-65..t-6, see engine/impact.py), computed
vectorised for all stocks, so a card and its comparison table always agree.
"""
import math
from functools import lru_cache

import numpy as np
import pandas as pd

from config import (ANOMALY_Z, BASELINE_DAYS, BASELINE_GAP, CAR_DAYS, COMPARE_MIN_GROUP, PEER_DAYS, SECTORS_CSV,
                    SIZE_COHORT_DAYS, SIZE_COHORT_LABELS, SIZE_PEERS_N)
from engine.data import daily, events

AUTO_TYPE = "NOTABLE_DAY"
PCTILE_COLS = {"abs_abn_ret": "Stock-specific move (abs.)", "vol_ratio": "Turnover vs normal",
               "xlm_ratio": "Trading cost vs normal"}
TABLE_COLS = ["ticker", "name", "index", "type", "reaction_day", "title", "ret", "abn_ret", "abs_abn_ret",
              "abn_ret_z", "gap_open", "car_0_5", "vol_ratio", "xlm_ratio", "auction_share",
              "auction_share_delta", "agent_aggr_imbalance", "isin", "event_id", "context"]


@lru_cache(maxsize=1)
def metrics_all() -> pd.DataFrame:
    d = daily().sort_values(["isin", "date"]).reset_index(drop=True)
    g = d.groupby("isin", group_keys=False)
    lag = BASELINE_GAP + 1  # baseline = t-65 .. t-6

    def base(col: str, how: str) -> pd.Series:
        return g[col].transform(lambda x: getattr(x.shift(lag).rolling(BASELINE_DAYS, min_periods=2), how)())

    m = d[["date", "isin", "ticker", "name", "idx", "idx_latest", "ret", "abn_ret", "gap_open", "auction_share",
           "agent_aggr_imbalance", "vol_z", "abn_ret_z", "xlm_25k_ratio", "possible_corp_action"]].copy()
    m = m.rename(columns={"abn_ret_z": "abn_ret_z_60", "xlm_25k_ratio": "xlm_ratio_60"})
    m["index"] = d["idx"].fillna(d["idx_latest"])
    m["vol_ratio"] = d["turnover_eur"] / base("turnover_eur", "median")
    m["xlm_ratio"] = d["xlm_25k"] / base("xlm_25k", "median")
    m["abn_ret_z"] = d["abn_ret"] / base("abn_ret", "std")
    m["auction_share_delta"] = d["auction_share"] - base("auction_share", "median")
    m["car_0_5"] = g["abn_ret"].transform(lambda x: x.rolling(CAR_DAYS + 1).sum().shift(-CAR_DAYS))
    m["abs_abn_ret"] = m["abn_ret"].abs()
    reasons = pd.DataFrame({
        "volume spike": m["vol_z"] >= ANOMALY_Z,
        "stock-specific move": m["abn_ret_z_60"].abs() >= ANOMALY_Z,
        "spread widening": m["xlm_ratio_60"] >= 2,
    })
    m["notable"] = reasons.any(axis=1) & ~m["possible_corp_action"].astype(bool)
    m["reason"] = ""
    m.loc[m["notable"], "reason"] = reasons[m["notable"]].apply(lambda r: ", ".join(r.index[r]), axis=1)
    return m.replace([np.inf, -np.inf], np.nan)


def event_types() -> list[str]:
    typed = sorted(t for t in events()["type"].dropna().unique() if t)
    return [AUTO_TYPE] + [t for t in typed if t != AUTO_TYPE]


def same_type_events(event_type: str, index: str | None = None) -> pd.DataFrame:
    """One row per event of this type (optionally only one index), with the impact-card metrics."""
    m = metrics_all()
    if event_type == AUTO_TYPE:
        t = m[m["notable"]].copy()
        t["type"], t["title"], t["reaction_day"] = AUTO_TYPE, t["reason"], t["date"]
        t["event_id"] = t["ticker"] + "_" + AUTO_TYPE + "_" + t["date"].dt.strftime("%Y%m%d")
    else:
        ev = events()
        ev = ev[ev["type"] == event_type].dropna(subset=["reaction_day"]).copy()
        ev["reaction_day"] = pd.to_datetime(ev["reaction_day"]).astype(m["date"].dtype)
        t = ev[["isin", "type", "title", "reaction_day", "event_id"]].merge(
            m.drop(columns=["ticker"]).merge(ev[["isin", "ticker"]].drop_duplicates(), on="isin"),
            left_on=["isin", "reaction_day"], right_on=["isin", "date"], how="inner")
    if index:
        t = t[t["index"] == index]
    from engine.baseline import context_frame  # imported here, not at the top: baseline imports compare
    t = t.assign(context=context_frame(t[["isin", "reaction_day"]].rename(columns={"reaction_day": "date"})))
    return t[TABLE_COLS].sort_values("reaction_day", ascending=False).reset_index(drop=True)


def percentile(card: dict, table: pd.DataFrame) -> dict:
    """Share of the other events in `table` with a smaller value than this card (0..1), per metric."""
    me = f"{card['isin']}_{card['event']['reaction_day']}"
    key = table["isin"] + "_" + table["reaction_day"].dt.strftime("%Y-%m-%d")
    others = table[key != me]
    abn = card["price"]["abn_ret"]
    mine = {"abs_abn_ret": None if abn is None else abs(abn), "vol_ratio": card["volume"]["ratio"],
            "xlm_ratio": card["liquidity"]["ratio"]}
    out = {"n": int(len(others))}
    for col, v in mine.items():
        x = others[col].dropna()
        out[f"{col}_pctile"] = None if v is None or x.empty else round(float((x < v).mean()), 3)
        out[f"{col}_median"] = None if x.empty else round(float(x.median()), 4)
    x = others["abs_abn_ret"].dropna()
    out["rank_abs_abn_ret"] = None if mine["abs_abn_ret"] is None else int((x > mine["abs_abn_ret"]).sum()) + 1
    out["rank_of"] = out["n"] + 1  # the rank counts this event too: "rank 3 of 215 (incl. this day)"
    return out


def _share(p: float) -> str:
    """Percentile as text, rounded down so 0.995 never reads as "100%" (round() first kills float noise)."""
    return f"{math.floor(round(p * 100, 6))}%"


def _summary(card: dict, group: str, res: dict) -> str:
    """One English sentence; every number comes from the card or the percentile result."""
    abn, vol = card["price"]["abn_ret"], card["volume"]["ratio"]
    parts = []
    if res["abs_abn_ret_pctile"] is not None:
        p = res["abs_abn_ret_pctile"]
        rank = "the biggest of them" if p == 1.0 else f"bigger than {_share(p)} of them"
        parts.append(f"the stock-specific move ({abn * 100:+.1f}%) was {rank}")
    if res["vol_ratio_pctile"] is not None:
        parts.append(f"turnover ({vol:.1f}x normal) was higher than {_share(res['vol_ratio_pctile'])}")
    if not parts:
        return f"Compared with {res['n']} {group}; not enough data on this day for a ranking."
    return f"Compared with {res['n']} {group}, " + " and ".join(parts) + "."


def comparison_for(card: dict) -> dict | None:
    """Same type in the same index if there are enough events, else all indices, else unusual days."""
    day = pd.Timestamp(card["event"]["reaction_day"])
    m = metrics_all()
    row = m[(m["isin"] == card["isin"]) & (m["date"] == day)]
    index = row["index"].iloc[0] if len(row) else card["index"]
    etype = card["event"]["type"]
    tries = [(etype, index), (etype, None)] if etype not in (AUTO_TYPE, "TBD", None) else []
    tries += [(AUTO_TYPE, index), (AUTO_TYPE, None)]
    for t, idx in tries:
        table = same_type_events(t, idx)
        res = percentile(card, table)
        if res["n"] >= COMPARE_MIN_GROUP:
            label = "unusual trading days" if t == AUTO_TYPE else f"{t} events"
            period = f"{m['date'].min():%b} – {m['date'].max():%b %Y}"
            group = f"{label}, {idx or 'DAX, MDAX and SDAX'}, {period}"
            return {"group_type": t, "group_index": idx or "DAX+MDAX+SDAX", "group": group, **res,
                    "period_start": f"{m['date'].min():%Y-%m-%d}", "period_end": f"{m['date'].max():%Y-%m-%d}",
                    "summary": _summary(card, group, res)}
    return None


# ---------- peer groups: index / sector / similar size (closest turnover) ----------
PEER_BY = ("index", "sector", "size")
SIZE_LABEL = "Similar size"


def _latest() -> pd.DataFrame:
    return daily().drop_duplicates("isin", keep="last")[["isin", "ticker", "idx_latest"]]


@lru_cache(maxsize=1)
def _sectors() -> pd.Series:
    """isin -> sector from events/sectors.csv (11 groups from Deutsche Boerse Prime Standard sectors)."""
    try:
        sec = pd.read_csv(SECTORS_CSV, dtype=str)
    except FileNotFoundError:
        return pd.Series(dtype=str)
    return sec.dropna(subset=["sector"]).drop_duplicates("isin").set_index("isin")["sector"]


@lru_cache(maxsize=1)
def size_cohorts() -> pd.Series:
    """isin -> "large" / "mid" / "small": terciles of each stock's median turnover over its last
    SIZE_COHORT_DAYS trading days. A size PROXY (market cap is not in the data)."""
    d = daily().sort_values("date")
    med = d.groupby("isin").tail(SIZE_COHORT_DAYS).groupby("isin")["turnover_eur"].median()
    rank = med.rank(method="first", ascending=False)   # 1 = highest turnover
    return pd.qcut(rank, len(SIZE_COHORT_LABELS), labels=list(SIZE_COHORT_LABELS)).astype(str)


def size_cohort(isin: str) -> str | None:
    return size_cohorts().get(isin)


PEER_COLS = ("turnover_eur", "xlm_25k", "auction_share", "agent_share", "volatility")


@lru_cache(maxsize=4)
def stock_medians(days: int = PEER_DAYS) -> pd.DataFrame:
    """Per ISIN: medians over the market's last `days` trading days (one window for every stock).
    volatility = annualised std of daily returns. The base of every peer benchmark."""
    d = daily()
    dates = np.sort(d["date"].unique())[-days:]
    last = d[d["date"].isin(dates)]
    m = last.groupby("isin").agg(turnover_eur=("turnover_eur", "median"), xlm_25k=("xlm_25k", "median"),
                                 auction_share=("auction_share", "median"), agent_share=("agent_share", "median"),
                                 volatility=("ret", "std"))
    m["volatility"] = m["volatility"] * math.sqrt(252)
    return m


def _closest_turnover(isin: str, candidates: list[str], n: int = SIZE_PEERS_N) -> list[str]:
    """The n candidates whose median turnover is closest to the stock's (log distance)."""
    to = stock_medians()["turnover_eur"]
    mine = to.get(isin)
    if mine is None or not mine > 0:
        return []
    cand = to.reindex(candidates)
    cand = cand[cand > 0]
    return (np.log(cand) - math.log(mine)).abs().sort_values(kind="stable").head(n).index.tolist()


def peer_medians(isin: str, days: int = PEER_DAYS) -> dict:
    """THE peer benchmark: for index, sector and size, the median over the peers of each peer's median over the
    last `days` trading days. Peers exclude the stock and other ISINs of the same company."""
    m = stock_medians(days)
    me = m.reindex([isin]).iloc[0]

    def num(v):
        return None if pd.isna(v) else float(v)

    groups = {}
    for by in PEER_BY:
        g = peer_group(isin, by)
        frame = m.reindex(g["isins"]).dropna(how="all")
        groups[by] = {**g, "values": {c: num(frame[c].median()) for c in PEER_COLS} if len(frame) else None}
    return {"isin": isin, "period": f"median of the last {days} trading days; peers exclude the stock itself",
            "stock": {c: num(me[c]) for c in PEER_COLS}, "groups": groups}


def peer_group(isin: str, by: str = "index") -> dict:
    """Peers of `isin` (the stock itself and other ISINs of the same ticker excluded).
    by="sector" falls back to the index when the sector is unknown or has no other member."""
    if by not in PEER_BY:
        raise ValueError(f"by must be one of {PEER_BY}")
    u = _latest()
    me = u[u["isin"] == isin]
    if me.empty:
        raise ValueError(f"Unknown ISIN {isin}")
    others = u[u["ticker"] != me["ticker"].iloc[0]]
    idx = me["idx_latest"].iloc[0]
    fallback = None
    if by == "sector":
        sector = _sectors().get(isin)
        peers = others[others["isin"].map(_sectors()) == sector] if sector else others.iloc[0:0]
        if len(peers):
            return {"by": "sector", "name": sector, "label": f"Sector: {sector}",
                    "isins": peers["isin"].tolist(), "n": len(peers), "fallback": None}
        fallback = "index"
    if by == "size":
        peers = _closest_turnover(isin, others["isin"].tolist())
        name = f"{len(peers)} closest by turnover"
        return {"by": "size", "name": name, "label": f"{SIZE_LABEL}: {name}",
                "isins": peers, "n": len(peers), "fallback": None}
    peers = others[others["idx_latest"] == idx]
    return {"by": "index", "name": idx, "label": f"Index: {idx}",
            "isins": peers["isin"].tolist(), "n": len(peers), "fallback": fallback}


def sector_peers(isin: str) -> list[str]:
    """ISINs in the same sector (events/sectors.csv); fallback: same latest index."""
    return peer_group(isin, "sector")["isins"]


def size_peers(isin: str) -> list[str]:
    """The SIZE_PEERS_N ISINs closest in median turnover (size proxy, not market cap)."""
    return peer_group(isin, "size")["isins"]


def day_ratios(isin: str) -> pd.DataFrame:
    """Turnover and trading cost vs normal for every day of one stock, with THE impact-card baseline
    (median of t-65..t-6). Every "x normal" the product shows (dashboard, unusual days, card, assistant,
    report) comes from here or from the card itself, so the same day never shows two different ratios.
    (The anomaly screen in engine.baseline uses z-scores against the previous 60 days; that only decides
    WHICH days are flagged, it is not shown as a ratio.)"""
    m = metrics_all()
    m = m[m["isin"] == isin]
    out = m.set_index("date")[["vol_ratio", "xlm_ratio", "abn_ret"]].copy()
    out[["vol_ratio", "xlm_ratio"]] = out[["vol_ratio", "xlm_ratio"]].round(2)  # the card's precision: 8.55 -> "8.6x" in both
    return out
