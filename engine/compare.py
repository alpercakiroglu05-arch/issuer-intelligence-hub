"""
Compare events of the same type.  OWNER: C2 (engine); first version by C1.

The challenge asks: "compare events of the same type, e.g. all quarterly results in the DAX over the past year".

    metrics_all()                          -> DataFrame, every stock-day with the impact-card metrics
    event_types()                          -> list of comparable types (NOTABLE_DAY + types in events.csv)
    same_type_events(event_type, index)    -> DataFrame, one row per event of that type
    percentile(card, table)                -> dict, where this card sits in the table
    comparison_for(card)                   -> dict | None, fills card["comparison"]
    sector_peers(isin)                     -> list[str] of ISINs (events/sectors.csv, fallback: same index)

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

from config import ANOMALY_Z, BASELINE_DAYS, BASELINE_GAP, CAR_DAYS, COMPARE_MIN_GROUP, SECTORS_CSV
from engine.data import daily, events

AUTO_TYPE = "NOTABLE_DAY"
PCTILE_COLS = {"abs_abn_ret": "Stock-specific move (abs.)", "vol_ratio": "Turnover vs normal",
               "xlm_ratio": "Trading cost vs normal"}
TABLE_COLS = ["ticker", "name", "index", "type", "reaction_day", "title", "ret", "abn_ret", "abs_abn_ret",
              "abn_ret_z", "gap_open", "car_0_5", "vol_ratio", "xlm_ratio", "auction_share",
              "auction_share_delta", "agent_aggr_imbalance", "isin", "event_id"]


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
    return out


def _share(p: float) -> str:
    """Percentile as text, rounded down so 0.995 never reads as "100%" (round() first kills float noise)."""
    return f"{math.floor(round(p * 100, 6))}%"


def _summary(card: dict, group: str, res: dict) -> str:
    """One English sentence; every number comes from the card or the percentile result."""
    abn, vol = card["price"]["abn_ret"], card["volume"]["ratio"]
    parts = []
    if res["abs_abn_ret_pctile"] is not None:
        parts.append(f"the stock-specific move ({abn * 100:+.1f}%) was bigger than {_share(res['abs_abn_ret_pctile'])} of them")
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
                    "summary": _summary(card, group, res)}
    return None


def sector_peers(isin: str) -> list[str]:
    """ISINs in the same sector (events/sectors.csv); fallback: same latest index."""
    u = daily().drop_duplicates("isin", keep="last")[["isin", "ticker", "idx_latest"]]
    try:
        sec = pd.read_csv(SECTORS_CSV, dtype=str).dropna(subset=["sector"])
        sec = sec.merge(u, on="ticker")
        mine = sec.loc[sec["isin_y"] == isin, "sector"]
        if len(mine):
            peers = sec.loc[(sec["sector"] == mine.iloc[0]) & (sec["isin_y"] != isin), "isin_y"].tolist()
            if peers:
                return peers
    except (FileNotFoundError, KeyError):
        pass
    idx = u.loc[u["isin"] == isin, "idx_latest"]
    return u.loc[(u["idx_latest"] == idx.iloc[0]) & (u["isin"] != isin), "isin"].tolist() if len(idx) else []
