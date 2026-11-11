"""
Trading cost by order size (XLM curve) vs peers.  OWNER: C1.

Deutsche Börse's monthly Stock Report shows XLM for several order sizes; this is the on-demand version.

    cost_curve(isin, by="index", days=60) -> DataFrame, one row per order size:
        notional_eur, label, stock_bps, stock_fill, peer_bps, peer_fill
    curve_summary(curve) -> dict: largest order the book absorbed on most days, cost of a EUR 100k / 1m order

XLM (Impact_bps) is only published when the Xetra order book was deep enough to fill an order of that size.
A missing value therefore means "the book could not absorb it that day", not "no data". So each size gets
  *_bps   median cost over the days with a value, and
  *_fill  share of days with a value (how often the book absorbed that size).
Sizes with fill < FILL_MIN are shown as "not on most days" (bps = None).
Peers: the same numbers for every stock in the peer group (engine.compare.peer_group). A size counts for the
peers when the median peer absorbs it on most days; the peer cost is then the median over the peers that did.
"""
import numpy as np
import pandas as pd

from engine.compare import peer_group
from engine.data import daily

NOTIONALS = [(10e3, "xlm_10k"), (25e3, "xlm_25k"), (50e3, "xlm_50k"), (100e3, "xlm_100k"), (250e3, "xlm_250k"),
             (500e3, "xlm_500k"), (1e6, "xlm_1m"), (2.5e6, "xlm_2_5m"), (5e6, "xlm_5m"), (10e6, "xlm_10m")]
FILL_MIN = 0.5  # a size counts as "absorbed" if the book filled it on at least half of the days


def _label(x: float) -> str:
    return f"€{x / 1e6:g}m" if x >= 1e6 else f"€{x / 1e3:g}k"


def _per_stock(frame: pd.DataFrame) -> pd.DataFrame:
    """Median cost (on days with a value) and fill share per stock and order size."""
    cols = [c for _, c in NOTIONALS]
    g = frame.groupby("isin")[cols]
    return pd.concat({"bps": g.median(), "fill": g.count().div(g.size(), axis=0)}, axis=1)


def cost_curve(isin: str, by: str = "index", days: int = 60) -> pd.DataFrame:
    d = daily()
    dates = np.sort(d["date"].unique())[-days:]
    recent = d[d["date"].isin(dates)]
    peers = peer_group(isin, by)["isins"]
    stats = _per_stock(recent[recent["isin"].isin(set(peers) | {isin})])
    rows = []
    for notional, col in NOTIONALS:
        me = stats.loc[isin] if isin in stats.index else None
        pe = stats.loc[stats.index.isin(peers)]
        s_fill = float(me[("fill", col)]) if me is not None else 0.0
        p_fill = float(pe[("fill", col)].median()) if len(pe) else 0.0
        # peer cost only where the median peer absorbs this size on most days (same rule as for the stock);
        # the cost itself is the median over the peers that absorbed it
        p_ok = pe[pe[("fill", col)] >= FILL_MIN]
        rows.append({
            "notional_eur": notional, "label": _label(notional),
            "stock_bps": float(me[("bps", col)]) if me is not None and s_fill >= FILL_MIN else None,
            "stock_fill": round(s_fill, 3),
            "peer_bps": float(p_ok[("bps", col)].median()) if p_fill >= FILL_MIN and len(p_ok) else None,
            "peer_fill": round(p_fill, 3),
        })
    return pd.DataFrame(rows)


def curve_summary(curve: pd.DataFrame) -> dict:
    ok = curve[curve["stock_bps"].notna()]
    at = lambda n: curve.loc[curve["notional_eur"] == n, "stock_bps"].iloc[0]  # noqa: E731
    peer_at = lambda n: curve.loc[curve["notional_eur"] == n, "peer_bps"].iloc[0]  # noqa: E731
    return {
        "largest_absorbed_eur": float(ok["notional_eur"].max()) if len(ok) else None,
        "largest_absorbed_label": ok["label"].iloc[-1] if len(ok) else None,
        "cost_100k_bps": at(100e3), "peer_cost_100k_bps": peer_at(100e3),
        "cost_1m_bps": at(1e6), "peer_cost_1m_bps": peer_at(1e6),
    }
