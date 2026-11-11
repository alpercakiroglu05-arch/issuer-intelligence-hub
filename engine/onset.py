"""
News onset: the minute the market started pricing the news.  OWNER: C1.

    onset(isin, day) -> dict | None      (goes into card["intraday"]["onset"])

Method (deterministic, explainable to the jury)
------
Grid      every minute 08:00 .. 17:29 local (pre-market + continuous session, closing auction excluded).
Price     last trade price so far; move = price / previous close - 1.
          "Break" when |move| >= ONSET_PRICE_K x sigma, sigma = std of daily returns in the baseline window.
Volume    cumulative turnover since 08:00 vs. the median cumulative turnover at the same clock time
          on baseline days. "Break" when the ratio >= ONSET_VOLUME_K and the turnover is not tiny
          (>= ONSET_MIN_TURNOVER_SHARE of a normal day).
Onset     first minute where both break, in the direction of the day's move, and the price is still
          beyond the threshold ONSET_PERSIST_MIN minutes later (filters single odd prints).
          Before 09:00 or in the opening auction  -> inferred timing "pre_open" (news before the open).
          Later                                   -> "intraday".

Sessions: pre_market (< 09:00), opening_auction, at_open (continuous trading up to 09:05), continuous.
Limitation: the price move is raw (no intraday peer data), so a market-wide move can also trigger it.
Validation (4 stocks x 205 days): onset found on 17 of 19 days with |abnormal return z| >= 3.

Also reports the price at onset, how much of the day's move was priced in 15 minutes after the onset,
and the volatility interruptions (unscheduled auctions) of the day.
"""
import numpy as np
import pandas as pd

from config import (BASELINE_DAYS, BASELINE_GAP, ONSET_MIN_TURNOVER_SHARE, ONSET_PERSIST_MIN, ONSET_PRICE_K,
                    ONSET_VOLUME_K)
from engine.data import intraday, stock

GRID_START, GRID_END = "08:00", "17:29"
OPEN, CLOSE_AUCTION = "09:00", "17:30"
# Scheduled auctions: opening (may be extended a few minutes), midday, closing.
SCHEDULED_AUCTIONS = [("09:00", "09:05"), ("13:00", "13:05"), ("17:30", "23:59")]


def _minute_of_day(ts: pd.Series) -> pd.Series:
    return ts.dt.hour * 60 + ts.dt.minute


def _hhmm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def _grid(bars: pd.DataFrame) -> pd.DataFrame:
    """One day of sparse bars -> full minute grid (price ffilled, turnover cumulative)."""
    lo, hi = (int(h) * 60 + int(m) for h, m in (GRID_START.split(":"), GRID_END.split(":")))
    b = bars.assign(m=_minute_of_day(bars["ts_local"]))
    b = b[(b["m"] >= lo) & (b["m"] <= hi)].groupby("m").agg(
        close=("close", "last"), volume_eur=("volume_eur", "sum"), is_auction=("is_auction", "any"))
    g = b.reindex(range(lo, hi + 1))
    g["price"] = g["close"].ffill()
    g["volume_eur"] = g["volume_eur"].fillna(0.0)
    g["cum_eur"] = g["volume_eur"].cumsum()
    g["is_auction"] = g["is_auction"].fillna(False).astype(bool)
    return g


def _volatility_interruptions(day_bars: pd.DataFrame) -> list[str]:
    a = day_bars[day_bars["is_auction"]]
    hhmm = a["ts_local"].dt.strftime("%H:%M")
    scheduled = np.zeros(len(a), dtype=bool)
    for lo, hi in SCHEDULED_AUCTIONS:
        scheduled |= ((hhmm >= lo) & (hhmm <= hi)).to_numpy()
    in_session = ((hhmm >= OPEN) & (hhmm < CLOSE_AUCTION)).to_numpy()
    return sorted(set(hhmm[in_session & ~scheduled]))


def onset(isin: str, day, event_time: str | None = None) -> dict | None:
    """When did the market start pricing the news? None if there are no bars or no break."""
    bars = intraday()
    if bars is None:
        return None
    day = pd.Timestamp(day)
    s = stock(isin)
    hit = s.index[s["date"] == day]
    if hit.empty or int(hit[0]) == 0:
        return None
    i = int(hit[0])
    prev_close = s.loc[i - 1, "price"]
    day_ret = s.loc[i, "ret"]
    base = s.iloc[max(0, i - BASELINE_GAP - BASELINE_DAYS): max(0, i - BASELINE_GAP)]
    sigma = base["ret"].std()
    if not (prev_close > 0) or not (sigma > 0) or pd.isna(day_ret):
        return None

    mine = bars[bars["isin"] == isin]
    dates = mine["ts_local"].dt.tz_localize(None).dt.normalize()
    today = mine[dates == day]
    if today.empty:
        return None
    g = _grid(today)
    base_days = mine[dates.isin(set(base["date"]))]
    if base_days.empty:
        return None
    base_cum = pd.concat(
        [_grid(x)["cum_eur"] for _, x in base_days.groupby(dates[dates.isin(set(base["date"]))])], axis=1)
    normal_cum = base_cum.median(axis=1)
    normal_day = base["turnover_eur"].median()

    move = g["price"] / prev_close - 1
    thr = ONSET_PRICE_K * sigma
    direction = np.sign(day_ret) if abs(day_ret) >= thr else 0
    price_break = (move.abs() >= thr) & ((direction == 0) | (np.sign(move) == direction))
    vol_ratio = g["cum_eur"] / normal_cum.clip(lower=0.002 * normal_day)
    vol_break = (vol_ratio >= ONSET_VOLUME_K) & (g["cum_eur"] >= ONSET_MIN_TURNOVER_SHARE * normal_day)
    # persistence: price still beyond the threshold ONSET_PERSIST_MIN minutes later
    later = price_break.shift(-ONSET_PERSIST_MIN, fill_value=False)
    candidates = g.index[price_break & vol_break & later]

    out = {
        "method": f"|move vs prev close| >= {ONSET_PRICE_K:g} sigma ({thr:.1%}) and cumulative turnover "
                  f">= {ONSET_VOLUME_K:g}x normal for the time of day",
        "sigma_daily": round(float(sigma), 6),
        "volatility_interruptions": _volatility_interruptions(today),
        "time": None, "session": None, "inferred_timing": None,
    }
    if len(candidates) == 0:
        return out
    m = int(candidates[0])
    if m < 540:
        session = "pre_market"
    elif m <= 545 and g.loc[m, "is_auction"]:  # opening auction, possibly extended to ~09:05
        session = "opening_auction"
    elif m <= 545:                             # first minutes of continuous trading: news was out at the open
        session = "at_open"
    else:
        session = "continuous"
    m15 = min(m + 15, g.index[-1])
    close_move = day_ret
    out.update({
        "time": _hhmm(m), "session": session,
        "inferred_timing": "intraday" if session == "continuous" else "pre_open",
        "ret_at_onset": round(float(move[m]), 6),
        "ret_15min_after": round(float(move[m15]), 6),
        "share_of_day_move_15min_after": round(float(move[m15] / close_move), 4) if close_move else None,
        "volume_ratio_at_onset": round(float(vol_ratio[m]), 2),
        "lag_minutes": None,
    })
    if event_time:
        try:
            h, mm = (int(x) for x in str(event_time).split(":")[:2])
            out["lag_minutes"] = m - (h * 60 + mm) if h * 60 + mm >= 480 else None  # pre-08:00 news: no lag
        except ValueError:
            pass
    return out
