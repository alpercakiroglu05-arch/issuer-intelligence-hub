"""
Part B - the impact card.  OWNER: C2 (engine).
STATUS: v1 works on daily data. Intraday block fills itself once data/intraday_bars.parquet exists.

    impact_card(isin, day, event=None) -> dict      (schema: README -> "impact_card")

Method
------
t0       = reaction day (events: from build_events; notable days: the day itself)
baseline = trading days t-65 .. t-6  (BASELINE_DAYS=60, skipping BASELINE_GAP=5 days before t0)
abnormal return = stock return - equal-weighted return of the other index members
volume z = (log turnover t0 - mean log turnover baseline) / std
CAR      = sum of abnormal returns t0 .. t+5

TODO C2:
  - comparison block: percentile of this event vs. all events of the same type (engine/compare.py)
  - intraday block: news onset ("market started pricing at HH:MM") is in engine/onset.py (C1, done)
  - unit tests on GXI 2026-02-11 (known values: ret -31.4%, abn -30.5%, vol ratio ~20x)
"""
import numpy as np
import pandas as pd

from config import BASELINE_DAYS, BASELINE_GAP, CAR_DAYS, SPREAD_NORMAL_TOL
from engine.data import intraday, stock
from engine.onset import onset

SCHEMA_VERSION = "1.0"


def _f(x, nd: int = 6):
    """float or None (JSON friendly)."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(x) else round(x, nd)


def _intraday_block(isin: str, day: pd.Timestamp, event_time: str | None = None) -> dict | None:
    bars = intraday()
    if bars is None:
        return None
    b = bars[(bars["isin"] == isin) & (bars["ts_local"].dt.date == day.date())]
    if b.empty:
        return None
    hhmm = b["ts_local"].dt.strftime("%H:%M")
    total = b["volume_eur"].sum()
    share = lambda mask: _f(b.loc[mask, "volume_eur"].sum() / total)  # noqa: E731
    cont = b[(hhmm >= "09:00") & (hhmm < "17:30")]
    return {
        "volume_share_first_15min": share((hhmm >= "09:00") & (hhmm < "09:15")),
        "volume_share_first_60min": share((hhmm >= "09:00") & (hhmm < "10:00")),
        "open_auction_eur": _f(b.loc[b["is_auction"] & (hhmm < "09:10"), "volume_eur"].sum(), 0),
        "close_auction_eur": _f(b.loc[b["is_auction"] & (hhmm >= "17:30"), "volume_eur"].sum(), 0),
        "intraday_low": _f(cont["low"].min()), "intraday_high": _f(cont["high"].max()),
        "time_of_low": cont.loc[cont["low"].idxmin(), "ts_local"].strftime("%H:%M") if len(cont) else None,
        "onset": onset(isin, day, event_time),
    }


def impact_card(isin: str, day, event: dict | None = None) -> dict:
    s = stock(isin)
    day = pd.Timestamp(day)
    hit = s.index[s["date"] == day]
    if hit.empty:
        raise ValueError(f"No trading data for {isin} on {day.date()}")
    i = int(hit[0])
    row = s.loc[i]
    base = s.iloc[max(0, i - BASELINE_GAP - BASELINE_DAYS): max(0, i - BASELINE_GAP)]
    post = s.iloc[i: i + CAR_DAYS + 1]
    after = s.iloc[i + 1: i + 21]

    # volume
    lt = np.log(base["turnover_eur"].where(base["turnover_eur"] > 0))
    turnover_base = base["turnover_eur"].median()
    vol_z = (np.log(row["turnover_eur"]) - lt.mean()) / lt.std() if row["turnover_eur"] > 0 else np.nan

    # spread
    xlm_base = base["xlm_25k"].median()
    if pd.notna(row["xlm_25k"]) and row["xlm_25k"] <= SPREAD_NORMAL_TOL * xlm_base:
        days_to_normal = 0
    else:
        days_to_normal = next((k for k, x in enumerate(after["xlm_25k"], start=1)
                               if pd.notna(x) and x <= SPREAD_NORMAL_TOL * xlm_base), None)

    flags = [f for f in ("flow_censored", "flow_multi_day", "possible_corp_action") if bool(row.get(f, False))]
    if len(base) < 20:
        flags.append("short_baseline")

    ev = event or {}
    event_time = ev.get("time_local") if isinstance(ev.get("time_local"), str) and ev.get("time_local") else None
    intra = _intraday_block(isin, day, event_time)
    timing = ev.get("timing", "unknown")
    if not isinstance(timing, str) or timing in ("", "unknown"):
        timing = "unknown"
    timing_source = "announcement" if timing != "unknown" else None
    if timing == "unknown" and intra and intra.get("onset") and intra["onset"].get("inferred_timing"):
        timing, timing_source = intra["onset"]["inferred_timing"], "inferred_from_trading"
    card = {
        "schema_version": SCHEMA_VERSION,
        "isin": isin, "ticker": row["ticker"], "name": row["name"], "index": row["idx_latest"],
        "event": {
            "event_id": ev.get("event_id"), "type": ev.get("type", "NOTABLE_DAY"),
            "title": ev.get("title", "Unusual trading day (detected automatically)"),
            "datetime_local": f"{pd.Timestamp(ev['date']).date()} {ev.get('time_local', '')}".strip() if ev else None,
            "timing": timing, "timing_source": timing_source, "source_url": ev.get("source_url") or None,
            "reaction_day": str(day.date()),
        },
        "baseline": {"window": f"t-{BASELINE_GAP + BASELINE_DAYS}..t-{BASELINE_GAP + 1}", "days_used": len(base)},
        "price": {
            "ret": _f(row["ret"]), "peer_ret": _f(row["peer_ret"]), "abn_ret": _f(row["abn_ret"]),
            "abn_ret_z": _f(row["abn_ret"] / base["abn_ret"].std(), 2),
            "gap_open": _f(row["gap_open"]), "ret_intraday": _f(row["ret_intraday"]),
            "car_0_5": _f(post["abn_ret"].sum()) if len(post) == CAR_DAYS + 1 else None,
        },
        "volume": {
            "turnover_eur": _f(row["turnover_eur"], 0), "baseline_eur": _f(turnover_base, 0),
            "ratio": _f(row["turnover_eur"] / turnover_base, 2), "z": _f(vol_z, 2),
        },
        "liquidity": {
            "xlm_25k_bps": _f(row["xlm_25k"], 2), "xlm_25k_baseline_bps": _f(xlm_base, 2),
            "ratio": _f(row["xlm_25k"] / xlm_base, 2), "days_to_normal": days_to_normal,
        },
        "auctions": {
            "auction_share": _f(row["auction_share"], 4),
            "auction_share_baseline": _f(base["auction_share"].median(), 4),
        },
        "participants": {
            "agent_share": _f(row["agent_share"], 4), "agent_share_baseline": _f(base["agent_share"].median(), 4),
            "agent_aggr_imbalance": _f(row["agent_aggr_imbalance"], 4),
            "agent_aggr_imbalance_baseline": _f(base["agent_aggr_imbalance"].median(), 4),
            "agent_aggr_net_eur": _f(row["agent_aggr_net_eur"], 0),
            "prop_share": _f(row["prop_share"], 4), "mm_share": _f(row["mm_share"], 4),
        },
        "intraday": intra,
        "comparison": None,   # TODO C2: engine/compare.py
        "flags": flags,
    }
    return card
