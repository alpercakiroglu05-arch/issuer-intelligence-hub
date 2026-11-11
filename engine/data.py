"""Loaders. Every module reads data through these functions (one place to fix paths/caching)."""
from functools import lru_cache

import pandas as pd

from config import DATA_DIR, EVENTS_CSV, NAMES_CSV


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


_SHARE_CLASS = {"NA", "INH", "INH.", "VZO", "ST", "NAM", "O.N.", "ON", "VNA", "ZO", "SP.ADR"}
_LEGAL = {"AG": "AG", "SE": "SE", "KGAA": "KGaA", "NV": "N.V.", "SA": "SA", "PLC": "plc", "GMBH": "GmbH",
          "AG+CO.KGAA": "AG & Co. KGaA", "SE+CO.KGAA": "SE & Co. KGaA"}


def _clean_name(raw: str) -> str:
    """'ADIDAS AG NA O.N.' -> 'Adidas AG': drop share-class tokens, keep legal forms upper case."""
    words = str(raw).split()
    while words and (words[-1].upper() in _SHARE_CLASS or words[-1].upper().startswith(("EO", "-,"))):
        words.pop()
    return " ".join(_LEGAL.get(w.upper(), w.capitalize()) for w in words) or str(raw)


@lru_cache(maxsize=1)
def _display_names() -> dict:
    p = NAMES_CSV
    return dict(pd.read_csv(p, dtype=str).itertuples(index=False)) if p.exists() else {}


def display_name(isin: str) -> str:
    """Readable company name: curated list (events/names.csv) for the event stocks, else a cleaned exchange name."""
    u = universe()
    row = u[u["isin"] == isin]
    if row.empty:
        return isin
    ticker, raw = row["ticker"].iloc[0], row["name"].iloc[0]
    return _display_names().get(ticker) or _clean_name(raw)


def isin_of(ticker: str) -> str:
    u = universe()
    return u.loc[u["ticker"] == ticker, "isin"].iloc[0]


def ticker_of(isin: str) -> str:
    u = universe()
    return u.loc[u["isin"] == isin, "ticker"].iloc[0]


def stock(isin: str) -> pd.DataFrame:
    d = daily()
    return d[d["isin"] == isin].sort_values("date").reset_index(drop=True)
