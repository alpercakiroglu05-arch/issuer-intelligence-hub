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


INTRADAY = DATA_DIR / "intraday_bars.parquet"


@lru_cache(maxsize=1)
def _intraday_all() -> pd.DataFrame:
    return pd.read_parquet(INTRADAY)


@lru_cache(maxsize=64)
def _intraday_one(isin: str) -> pd.DataFrame:
    # the file is sorted by isin with small row groups, so this reads only this stock's row groups
    return pd.read_parquet(INTRADAY, filters=[("isin", "==", isin)])


@lru_cache(maxsize=1)
def intraday_isins() -> frozenset[str]:
    """Stocks that have 1-minute bars (empty set until C1 has built them)."""
    if not INTRADAY.exists():
        return frozenset()
    return frozenset(pd.read_parquet(INTRADAY, columns=["isin"])["isin"].unique())


def intraday(isin: str | None = None) -> pd.DataFrame | None:
    """1-minute bars from ingest/build_intraday.py, or None until C1 has built them.
    Pass an ISIN: only that stock is read (fast, little memory). Without an ISIN the whole file is
    loaded (millions of rows): use only in tests and validation scripts."""
    if not INTRADAY.exists():
        return None
    return _intraday_all() if isin is None else _intraday_one(isin)


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
