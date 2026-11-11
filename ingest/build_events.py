#!/usr/bin/env python3
"""
build_events.py - turns the hand-maintained events/events.csv into data/events.parquet.

Adds for every event:
    isin          looked up from the ticker (data/universe.csv)
    timing        pre_open | intraday | post_close | unknown
    reaction_day  first trading day on which the market could react
                  (post_close or weekend/holiday -> next trading day)

Usage:
    python3 ingest/build_events.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_DIR, EVENTS_CSV, XETRA_CLOSE_AUCTION, XETRA_OPEN  # noqa: E402


def trading_days() -> pd.DatetimeIndex:
    d = pd.read_parquet(DATA_DIR / "daily_features.parquet", columns=["date"])
    return pd.DatetimeIndex(sorted(d["date"].unique()))


def classify(time_local: str | float) -> str:
    if not isinstance(time_local, str) or not time_local.strip():
        return "unknown"
    t = time_local.strip()[:5]
    if t < XETRA_OPEN:
        return "pre_open"
    if t < XETRA_CLOSE_AUCTION:
        return "intraday"
    return "post_close"


def build(events_csv: Path = EVENTS_CSV) -> pd.DataFrame:
    ev = pd.read_csv(events_csv, dtype=str).fillna("")
    uni = pd.read_csv(DATA_DIR / "universe.csv", dtype=str)
    ev["isin"] = ev["isin"].where(ev["isin"] != "", ev["ticker"].map(dict(zip(uni["ticker"], uni["isin"]))))
    ev["date"] = pd.to_datetime(ev["date"])
    ev["timing"] = ev["time_local"].map(classify)

    days = trading_days()
    pos = days.searchsorted(ev["date"].values)            # first trading day >= event date
    same_day = days[np.minimum(pos, len(days) - 1)].values == ev["date"].values
    pos = pos + ((ev["timing"] == "post_close").values & same_day).astype(int)
    ev["reaction_day"] = [days[p] if p < len(days) else pd.NaT for p in pos]

    ev["event_id"] = ev["ticker"] + "_" + ev["type"] + "_" + ev["date"].dt.strftime("%Y%m%d")
    missing = ev["isin"].isna() | (ev["isin"] == "")
    if missing.any():
        print("WARNING unknown tickers:", ev.loc[missing, "ticker"].unique().tolist())
    return ev[~missing].drop_duplicates("event_id")


if __name__ == "__main__":
    out = build()
    out.to_parquet(DATA_DIR / "events.parquet", index=False)
    print(f"{len(out)} events -> {DATA_DIR / 'events.parquet'}")
    print(out[["event_id", "timing", "reaction_day"]].to_string(index=False))
