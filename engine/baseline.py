"""
Part A - the "normal state" of a stock.  OWNER: C2 (engine).  STATUS: v1 works.

    profile(isin)              daily time series for the dashboard
    index_benchmark(idx, col)  median of a column across the stock's index, per day
    anomalies(isin)            unusual days ("notable days") with a reason
    kpis(isin)                 headline numbers vs. index median + Xetra liquidity check

TODO C2:
  - anomalies(): merge consecutive anomaly days into one episode
  - kpis(): add trend arrows (last 60d vs previous 60d) - "has liquidity improved?"
  - sector peers instead of index peers once events/sectors.csv is filled
"""
import numpy as np
import pandas as pd

from config import ANOMALY_Z, DS_LOOKBACK_DAYS, DS_TURNOVER_MIN_EUR, DS_XLM_MAX_BPS
from engine.data import daily, stock

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
    out["reason"] = reasons[hit].apply(lambda r: ", ".join(r.index[r]), axis=1)
    out["severity"] = out["abn_ret_z"].abs().fillna(0) + out["vol_z"].clip(lower=0).fillna(0)
    return out.sort_values("date", ascending=False).reset_index(drop=True)


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

    def pair(col):
        return {"stock": float(recent[col].median()), "index_median": float(peer_med[col])}

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
    }
