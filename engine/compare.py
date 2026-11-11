"""
Comparisons.  OWNER: C2 (engine).  STATUS: skeleton, to be implemented.

The challenge explicitly asks: "compare events of the same type, e.g. all quarterly
results in the DAX over the past year". Depends on events.csv being filled (research team).

    same_type_events(event_type, index=None) -> DataFrame
        one row per event of that type: ticker, reaction_day, abn_ret, vol_ratio,
        xlm ratio, auction_share delta, agent imbalance  (computed via impact_card)

    percentile(card, table) -> dict
        where this card sits within the table, e.g. {"vol_ratio_pctile": 0.88, ...}
        -> fills card["comparison"]

    sector_peers(isin) -> list[str]
        ISINs in the same sector (events/sectors.csv); fallback: same index
"""
import pandas as pd


def same_type_events(event_type: str, index: str | None = None) -> pd.DataFrame:
    raise NotImplementedError("C2: loop engine.data.events() of this type, call impact_card, collect key metrics")


def percentile(card: dict, table: pd.DataFrame) -> dict:
    raise NotImplementedError("C2: (table[col] < value).mean() for abn_ret, vol_ratio, xlm ratio")


def sector_peers(isin: str) -> list[str]:
    raise NotImplementedError("C2: read events/sectors.csv; fallback to index members")
