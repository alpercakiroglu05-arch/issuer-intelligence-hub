"""
Opening and closing auctions per day: volume and price formation.  OWNER: C1.

    auction_profile(isin) -> DataFrame, one row per trading day:
        date, open_auction_eur, close_auction_eur, close_auction_share,
        last_cont_px (last continuous trade before the closing auction call), close_auction_move

Volumes come from the 1-minute trade bars (auction trades = empty SIDE). The uncross minute is taken from
the daily OHLC auction timestamps, so pre-market trades, volatility interruptions and extended-hours trades
after the close (also auction-like, empty SIDE) are NOT counted.
Without bars for this stock the volume columns are empty; prices still come from the daily OHLC.
"""
from functools import lru_cache

import numpy as np
import pandas as pd

from engine.data import intraday, stock

CLOSING_CALL = "17:30"


@lru_cache(maxsize=16)
def auction_profile(isin: str) -> pd.DataFrame:
    s = stock(isin)[["date", "open_auct_px", "open_auct_ts", "close_auct_px", "close_auct_ts", "turnover_eur"]]
    out = s[["date"]].copy()
    mine = intraday(isin)
    if mine is None or mine.empty:
        for c in ("open_auction_eur", "close_auction_eur", "close_auction_share", "last_cont_px",
                  "close_auction_move"):
            out[c] = np.nan
        return out

    b = pd.DataFrame({
        "date": mine["ts_local"].dt.tz_localize(None).dt.normalize(),
        "hhmm": mine["ts_local"].dt.strftime("%H:%M"),
        "auction_eur": mine["auction_eur"], "is_auction": mine["is_auction"], "close": mine["close"],
    })
    days = set(b["date"])

    def at_minute(ts_col: str) -> pd.Series:
        key = s[["date"]].assign(hhmm=s[ts_col].astype("string").str[:5])
        hit = key.merge(b[b["is_auction"]], on=["date", "hhmm"], how="left")
        return hit.groupby("date")["auction_eur"].sum(min_count=1)

    out["open_auction_eur"] = out["date"].map(at_minute("open_auct_ts"))
    out["close_auction_eur"] = out["date"].map(at_minute("close_auct_ts"))
    # a day with bars but no trade in the auction minute had a zero-volume (or no) auction
    has_bars = out["date"].isin(days)
    for c in ("open_auction_eur", "close_auction_eur"):
        out.loc[has_bars & out[c].isna(), c] = 0.0
    out["close_auction_share"] = out["close_auction_eur"] / s["turnover_eur"].where(s["turnover_eur"] > 0)

    cont = b[~b["is_auction"] & (b["hhmm"] >= "09:00") & (b["hhmm"] < CLOSING_CALL)]
    out["last_cont_px"] = out["date"].map(cont.groupby("date")["close"].last())
    out["close_auction_move"] = s["close_auct_px"] / out["last_cont_px"] - 1
    return out
