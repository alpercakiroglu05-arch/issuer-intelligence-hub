"""
Comparisons.  OWNER: C2 (engine, Kaan).  STATUS: v1 works. Docs: docs/C2_ENGINE.md.

The challenge explicitly asks: "compare events of the same type, e.g. all quarterly
results in the DAX over the past year".

    same_type_events(event_type, index=None) -> DataFrame
        one row per event of that type (computed via impact_card). Falls back to the
        notable days of the index (baseline.anomalies) while events.csv has < MIN_EVENTS rows.

    percentile(card, table) -> dict          -> card["comparison"]
    add_comparison(card, index=None) -> card  fills card["comparison"]
    sector_peers(isin) -> list[str]           events/sectors.csv; fallback: same index
"""
import logging
from functools import lru_cache

import numpy as np
import pandas as pd

from config import SECTORS_CSV
from engine import baseline
from engine.data import daily, events, universe
from engine.impact import impact_card

log = logging.getLogger(__name__)

MIN_EVENTS = 5  # fewer real events than this -> compare against notable days instead
NOTABLE = "NOTABLE_DAY"
COLUMNS = ["isin", "ticker", "name", "index", "reaction_day", "title", "abn_ret", "car_0_5",
           "vol_ratio", "vol_z", "xlm_25k_ratio", "auction_share_delta", "agent_aggr_imbalance", "source"]
# comparison metric -> table column
METRICS = {"abn_ret": "abn_ret", "abs_abn_ret": "abs_abn_ret", "vol_ratio": "vol_ratio",
           "xlm_25k_ratio": "xlm_25k_ratio"}


def _members(index: str | None) -> list[str]:
    """ISINs whose latest index is `index` (all stocks if None)."""
    d = daily()
    if index is not None:
        d = d[d["idx_latest"] == index]
    return list(d["isin"].unique())


def _row(card: dict, source: str) -> dict:
    a, base = card["auctions"]["auction_share"], card["auctions"]["auction_share_baseline"]
    return {
        "isin": card["isin"], "ticker": card["ticker"], "name": card["name"], "index": card["index"],
        "reaction_day": card["event"]["reaction_day"], "title": card["event"]["title"],
        "abn_ret": card["price"]["abn_ret"], "car_0_5": card["price"]["car_0_5"],
        "vol_ratio": card["volume"]["ratio"], "vol_z": card["volume"]["z"],
        "xlm_25k_ratio": card["liquidity"]["ratio"],
        "auction_share_delta": None if a is None or base is None else round(a - base, 4),
        "agent_aggr_imbalance": card["participants"]["agent_aggr_imbalance"],
        "source": source,
    }


def _jobs(event_type: str, index: str | None) -> tuple[list[tuple], str]:
    """(isin, day, event-dict-or-None, title) per row, plus the source label."""
    members = set(_members(index))
    jobs = []
    if event_type != NOTABLE:
        e = events()
        e = e[(e["type"] == event_type) & e["isin"].isin(members)]
        jobs = [(r["isin"], r["reaction_day"], r.to_dict(), None) for _, r in e.iterrows()]
    if len(jobs) >= MIN_EVENTS:
        return jobs, "event"
    jobs = []
    for isin in sorted(members):
        try:
            a = baseline.anomalies(isin)
        except Exception as exc:  # noqa: BLE001 - one bad stock must not kill the table
            log.warning("compare: anomalies(%s) failed: %s", isin, exc)
            continue
        jobs += [(isin, r.date, None, f"Notable day: {r.reason}") for r in a.itertuples()]
    return jobs, "notable_day"


@lru_cache(maxsize=32)
def _table(event_type: str, index: str | None) -> pd.DataFrame:
    jobs, source = _jobs(event_type, index)
    rows, skipped = [], 0
    for isin, day, ev, title in jobs:
        try:
            card = impact_card(isin, day, ev)
        except Exception as exc:  # noqa: BLE001
            skipped += 1
            log.debug("compare: impact_card(%s, %s) failed: %s", isin, day, exc)
            continue
        row = _row(card, source)
        if title:
            row["title"] = title
        rows.append(row)
    if skipped:
        log.warning("compare: skipped %d of %d rows (%s, %s)", skipped, len(jobs), event_type, index)
    return pd.DataFrame(rows, columns=COLUMNS)


def same_type_events(event_type: str, index: str | None = None) -> pd.DataFrame:
    """One row per event of `event_type` in `index` (None = all). `source` says whether the rows are
    real events ("event") or the notable-day fallback ("notable_day"). Cached per (type, index)."""
    return _table(event_type, index).copy()


def _pct(x) -> str:
    return f"{x * 100:+.1f}%"


def _share(p: float) -> str:
    """Percentile as text, rounded down so 0.995 never reads as "100%"."""
    return f"{int(p * 100)}%"


def percentile(card: dict, table: pd.DataFrame) -> dict:
    """Where this card sits in `table` (0..1 = share of other rows with a lower value).
    The card's own row is excluded. This dict becomes card["comparison"]."""
    t = table[~((table["isin"] == card["isin"]) & (table["reaction_day"] == card["event"]["reaction_day"]))]
    t = t.assign(abs_abn_ret=t["abn_ret"].abs())
    abn = card["price"]["abn_ret"]
    value = {"abn_ret": abn, "abs_abn_ret": None if abn is None else abs(abn),
             "vol_ratio": card["volume"]["ratio"], "xlm_25k_ratio": card["liquidity"]["ratio"]}
    pctile, median = {}, {}
    for key, col in METRICS.items():
        s = pd.to_numeric(t[col], errors="coerce").dropna()
        v = value[key]
        pctile[key] = None if v is None or s.empty else round(float((s < v).mean()), 3)
        median[key] = None if s.empty else round(float(s.median()), 4)

    source = table["source"].iloc[0] if len(table) else None
    etype = card["event"]["type"] if source == "event" else NOTABLE
    index = table["index"].iloc[0] if len(table) and table["index"].nunique() == 1 else "selected universe"
    what = "notable days" if source == "notable_day" else f"{etype} events"
    parts = []
    if pctile["abs_abn_ret"] is not None:
        parts.append(f"the move ({_pct(abn)} vs peers) is larger than {_share(pctile['abs_abn_ret'])} of them")
    if pctile["vol_ratio"] is not None:
        parts.append(f"turnover ({value['vol_ratio']:.1f}x normal) is higher than {_share(pctile['vol_ratio'])}")
    if len(t) == 0:
        summary = f"No other {what} to compare with."
    elif parts:
        summary = f"Compared with {len(t)} {what} in the {index}, " + " and ".join(parts) + "."
    else:
        summary = f"Compared with {len(t)} {what} in the {index}; not enough data on this day for a ranking."
    return {"event_type": etype, "index": index, "source": source, "n": int(len(t)),
            "pctile": pctile, "median": median, "summary": summary}


def add_comparison(card: dict, index: str | None = None) -> dict:
    """Fill card["comparison"] against same-type events in `index` (default: the card's index)."""
    table = same_type_events(card["event"]["type"], index or card["index"])
    card["comparison"] = percentile(card, table)
    return card


def sector_peers(isin: str) -> list[str]:
    """Other ISINs in the same sector (events/sectors.csv). Falls back to the members of the
    stock's latest index when the stock or its sector peers are not in the file."""
    if SECTORS_CSV.exists():
        sec = pd.read_csv(SECTORS_CSV, dtype=str)
        u = universe()[["ticker", "isin"]].rename(columns={"isin": "isin_u"})
        sec = sec.merge(u, on="ticker", how="left")
        sec["isin"] = sec["isin"].replace("", np.nan).fillna(sec["isin_u"])
        mine = sec.loc[sec["isin"] == isin, "sector"]
        if not mine.empty:
            peers = sec.loc[(sec["sector"] == mine.iloc[0]) & (sec["isin"] != isin), "isin"].dropna()
            if not peers.empty:
                return sorted(peers.unique())
    d = daily()
    idx = d.loc[d["isin"] == isin].sort_values("date")["idx_latest"].iloc[-1]
    return sorted(i for i in _members(idx) if i != isin)
