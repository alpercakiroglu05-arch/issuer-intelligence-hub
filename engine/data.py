"""Loaders. Every module reads data through these functions (one place to fix paths/caching)."""
from functools import lru_cache

import pandas as pd

from config import DATA_DIR, EVENTS_CSV


@lru_cache(maxsize=1)
def daily() -> pd.DataFrame:
    """One row per (date, isin). Built by ingest/build_daily.py."""
    return pd.read_parquet(DATA_DIR / "daily_features.parquet")


@lru_cache(maxsize=1)
def universe() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "universe.csv")


@lru_cache(maxsize=1)
def intraday() -> pd.DataFrame | None:
    """1-minute bars from ingest/build_intraday.py, or None until C1 has built them."""
    p = DATA_DIR / "intraday_bars.parquet"
    return pd.read_parquet(p) if p.exists() else None


def events() -> pd.DataFrame:
    """Events with isin/timing/reaction_day. Uses data/events.parquet if built, else events.csv directly."""
    p = DATA_DIR / "events.parquet"
    if p.exists() and p.stat().st_mtime >= EVENTS_CSV.stat().st_mtime:
        return pd.read_parquet(p)
    from ingest.build_events import build
    return build()


def isin_of(ticker: str) -> str:
    u = universe()
    return u.loc[u["ticker"] == ticker, "isin"].iloc[0]


def ticker_of(isin: str) -> str:
    u = universe()
    return u.loc[u["isin"] == isin, "ticker"].iloc[0]


def stock(isin: str) -> pd.DataFrame:
    d = daily()
    return d[d["isin"] == isin].sort_values("date").reset_index(drop=True)
