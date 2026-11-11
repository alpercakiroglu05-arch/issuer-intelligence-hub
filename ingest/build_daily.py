#!/usr/bin/env python3
"""
build_daily.py - Issuer Intelligence Hub, step 1 (daily layer).

Turns the raw Deutsche Boerse excerpt into ONE small table:
one row per stock per trading day for every DAX/MDAX/SDAX member of 2026.

Usage:
    python3 build_daily.py <data_dir> <out_dir>

Inputs (inside data_dir):
    index_constituents/*_CONSTITUENTS_*.csv.gz        index membership per day
    XETRA/XETRA_OHLC/*.csv.gz                          daily prices, auctions, turnover
    XETRA/XETRA_FLOW_DYNAMICS_EQUITY/*.csv.gz          who traded (MM/AGENT/PROP x role x side)
    dax_mdax_sdax_liquid_spreads.*.tgz                 XLM impact in bps per notional

Outputs (inside out_dir):
    daily_features.parquet   one row per (date, isin)
    universe.csv             one row per stock
    hero_candidates.csv      strongest stock-specific days in MDAX/SDAX

Data pitfalls handled here (see the NOTES.md files):
    - flows: DATE is the publication date; the real day is REPORTED_FLOW_DATES.
      Censored days (<7 executions) are empty; multi-day rows are not split.
    - flows: VOLUME is two-sided; we only use the one-sided BUY/SELL columns.
    - OHLC: open/high/low/close are quoted MID prices -> returns use the
      closing-auction price (fallback: last mid). ADJUSTED_PRICE is ignored.
    - OHLC: an ISIN can have several currency lines -> EUR only.
    - constituents: a missing day uses the previous trading day's file.
"""
import sys
import tarfile
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

DATA = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=True)

con = duckdb.connect()
con.execute("SET threads=2; SET memory_limit='2GB'")


def q(sql: str) -> pd.DataFrame:
    return con.execute(sql).df()


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# 1. Index membership -> universe
# ---------------------------------------------------------------------------
cons = q(f"""
    SELECT "Index" AS idx,
           strptime("Date", '%Y%m%d')::DATE AS file_date,
           Mnemonic AS ticker,
           Isin AS isin
    FROM read_csv('{DATA}/index_constituents/*_CONSTITUENTS_*.csv.gz',
                  all_varchar=true, header=true)
""")
cons["file_date"] = pd.to_datetime(cons["file_date"])
universe_isins = pd.DataFrame({"isin": cons["isin"].unique()})
con.register("universe", universe_isins)
log(f"[1] constituents: {len(cons):,} rows, {len(universe_isins)} distinct ISINs")

# ---------------------------------------------------------------------------
# 2. Xetra OHLC (EUR equity lines of the universe only)
# ---------------------------------------------------------------------------
ohlc = q(f"""
    SELECT CAST(substr(FACT_DATE, 1, 10) AS DATE)       AS date,
           ISIN                                         AS isin,
           INSTRUMENT_NAME                              AS name,
           TRY_CAST(TRADED_VOLUME AS DOUBLE)            AS shares,
           TRY_CAST(TRADED_VALUE AS DOUBLE)             AS turnover_eur,
           TRY_CAST(OPEN_AUCTION_PRICE AS DOUBLE)       AS open_auct_px,
           OPEN_AUCTION_PRICE_TS                        AS open_auct_ts,
           TRY_CAST(MID_AUCTION_PRICE AS DOUBLE)        AS mid_auct_px,
           TRY_CAST(CLOSE_AUCTION_PRICE AS DOUBLE)      AS close_auct_px,
           CLOSE_AUCTION_PRICE_TS                       AS close_auct_ts,
           TRY_CAST(HIGH_PRICE AS DOUBLE)               AS high_mid,
           TRY_CAST(LOW_PRICE AS DOUBLE)                AS low_mid,
           TRY_CAST(CLOSE_PRICE AS DOUBLE)              AS close_mid,
           TRY_CAST(VWAP AS DOUBLE)                     AS vwap
    FROM read_csv('{DATA}/XETRA/XETRA_OHLC/*.csv.gz', all_varchar=true, header=true)
    WHERE CURRENCY = 'EUR'
      AND SEGMENT_NAME = 'EQUITIES'
      AND ISIN IN (SELECT isin FROM universe)
    QUALIFY row_number() OVER (
        PARTITION BY substr(FACT_DATE, 1, 10), ISIN
        ORDER BY TRY_CAST(TRADED_VALUE AS DOUBLE) DESC NULLS LAST) = 1
""")
ohlc["date"] = pd.to_datetime(ohlc["date"])
log(f"[2] OHLC: {len(ohlc):,} rows, {ohlc['isin'].nunique()} ISINs, "
    f"{ohlc['date'].min().date()} .. {ohlc['date'].max().date()}")

# ---------------------------------------------------------------------------
# 3. Xetra flow dynamics (who traded)
# ---------------------------------------------------------------------------
PART = {"MM": "mm", "AGENT": "agent", "PROP": "prop"}
ROLE = {"AGGRESSIVE": "aggr", "PASSIVE": "pass", "AUCTION": "auct"}
SIDE = {"BUY": "buy", "SELL": "sell"}
flow_cols = {
    f"{p}_{r}_{s}_EXECUTION_VOLUME": f"{pl}_{rl}_{sl}"
    for p, pl in PART.items() for r, rl in ROLE.items() for s, sl in SIDE.items()
}
select_flow = ",\n".join(f"TRY_CAST({c} AS DOUBLE) AS {a}" for c, a in flow_cols.items())
flows_raw = q(f"""
    SELECT ISIN AS isin,
           REPORTED_FLOW_DATES AS rfd,
           {select_flow}
    FROM read_csv('{DATA}/XETRA/XETRA_FLOW_DYNAMICS_EQUITY/*.csv.gz',
                  all_varchar=true, header=true)
    WHERE ISIN IN (SELECT isin FROM universe)
      AND REPORTED_FLOW_DATES IS NOT NULL AND REPORTED_FLOW_DATES <> ''
""")
multi = flows_raw["rfd"].str.contains(",")
# multi-day rows: remember which (isin, date) are not available as single days
multi_days = (flows_raw.loc[multi, ["isin", "rfd"]]
              .assign(date=lambda d: d["rfd"].str.split(", "))
              .explode("date")[["isin", "date"]])
multi_days["date"] = pd.to_datetime(multi_days["date"])
multi_days["flow_multi_day"] = True

flows = flows_raw.loc[~multi].copy()
flows["date"] = pd.to_datetime(flows["rfd"])
buy_cols = [a for a in flow_cols.values() if a.endswith("_buy")]
flows["flow_total_eur"] = flows[buy_cols].sum(axis=1)  # one-sided turnover
flows = (flows.sort_values("flow_total_eur", ascending=False)
              .drop_duplicates(["isin", "date"])
              .drop(columns="rfd"))

tot = flows["flow_total_eur"].replace(0, np.nan)
flows["auction_share"] = flows[[f"{p}_auct_buy" for p in PART.values()]].sum(axis=1) / tot
for p in PART.values():
    both = [f"{p}_{r}_{s}" for r in ROLE.values() for s in SIDE.values()]
    flows[f"{p}_share"] = flows[both].sum(axis=1) / (2 * tot)
ab, as_ = flows["agent_aggr_buy"], flows["agent_aggr_sell"]
flows["agent_aggr_imbalance"] = (ab - as_) / (ab + as_).replace(0, np.nan)  # +1 = only buying
flows["agent_aggr_net_eur"] = ab - as_
log(f"[3] flows: {len(flows):,} single-day rows, {multi.sum():,} multi-day rows")

# ---------------------------------------------------------------------------
# 4. XLM spreads (impact in bps per notional)
# ---------------------------------------------------------------------------
tgz = sorted(DATA.glob("dax_mdax_sdax_liquid_spreads*.tgz"))[0]
with tempfile.TemporaryDirectory() as tmp:
    with tarfile.open(tgz) as tf:
        tf.extractall(tmp)
    xlm_long = q(f"""
        SELECT strptime(CAST("Date" AS VARCHAR), '%Y%m%d')::DATE AS date,
               ISIN AS isin,
               CAST(Notional_CCY AS DOUBLE) AS notional,
               TRY_CAST(Impact_bps AS DOUBLE) AS impact_bps
        FROM read_csv('{tmp}/*.csv', all_varchar=true, header=true)
    """)
xlm_long["date"] = pd.to_datetime(xlm_long["date"])


def notional_name(x: float) -> str:
    if x >= 1e6:
        return "xlm_" + f"{x / 1e6:g}".replace(".", "_") + "m"
    return "xlm_" + f"{x / 1e3:g}".replace(".", "_") + "k"


xlm = xlm_long.pivot_table(index=["date", "isin"], columns="notional",
                           values="impact_bps", aggfunc="first")
xlm = xlm[sorted(xlm.columns)]
xlm.columns = [notional_name(c) for c in xlm.columns]
xlm = xlm.reset_index()
xlm_cols = [c for c in xlm.columns if c.startswith("xlm_")]
log(f"[4] XLM: {len(xlm):,} stock-days, notionals: {', '.join(xlm_cols)}")

# ---------------------------------------------------------------------------
# 5. Membership per trading day (missing file -> previous file)
# ---------------------------------------------------------------------------
tdays = pd.DataFrame({"date": np.sort(ohlc["date"].unique())})
members = []
for idx, g in cons.groupby("idx"):
    fdates = pd.DataFrame({"file_date": np.sort(g["file_date"].unique())})
    m = pd.merge_asof(tdays, fdates, left_on="date", right_on="file_date")
    members.append(m.merge(g, on="file_date")[["date", "idx", "isin", "ticker"]])
members = pd.concat(members).drop_duplicates(["date", "isin"])

latest = (members.sort_values("date").groupby("isin").tail(1)
          [["isin", "idx", "ticker"]].rename(columns={"idx": "idx_latest"}))

# ---------------------------------------------------------------------------
# 6. Assemble
# ---------------------------------------------------------------------------
df = (ohlc.merge(members[["date", "isin", "idx"]], on=["date", "isin"], how="left")
          .merge(latest, on="isin", how="left")
          .merge(flows, on=["date", "isin"], how="left")
          .merge(multi_days, on=["date", "isin"], how="left")
          .merge(xlm, on=["date", "isin"], how="left"))
df["flow_multi_day"] = df["flow_multi_day"].eq(True)
df["flow_censored"] = df["flow_total_eur"].isna()
df["name"] = df.groupby("isin")["name"].transform("last")
df = df.sort_values(["isin", "date"]).reset_index(drop=True)

# Prices and returns ------------------------------------------------------
df["price"] = df["close_auct_px"].fillna(df["close_mid"])
g = df.groupby("isin", sort=False)
df["prev_price"] = g["price"].shift(1)
df["ret"] = df["price"] / df["prev_price"] - 1
df["gap_open"] = df["open_auct_px"] / df["prev_price"] - 1      # news before the open
df["ret_intraday"] = df["price"] / df["open_auct_px"] - 1        # move during the session
df["possible_corp_action"] = df["ret"].abs() > 0.40              # splits etc.

# Peer returns: equal-weighted, same index, excluding the stock itself ---------
df["idx_peer"] = df["idx"].fillna(df["idx_latest"])
grp = df.groupby(["date", "idx_peer"])["ret"]
n, s = grp.transform("count"), grp.transform("sum")
df["peer_ret"] = (s - df["ret"]) / (n - 1)
gm = df.groupby("date")["ret"]
df["market_ret"] = (gm.transform("sum") - df["ret"]) / (gm.transform("count") - 1)
df["abn_ret"] = df["ret"] - df["peer_ret"]

# Rolling baselines (previous 60 trading days, current day excluded) -----------
W, MINP = 60, 20


def roll(col: str, fn: str) -> pd.Series:
    return (df.groupby("isin", sort=False)[col]
              .transform(lambda x: getattr(x.shift(1).rolling(W, min_periods=MINP), fn)()))


df["log_turnover"] = np.log(df["turnover_eur"].where(df["turnover_eur"] > 0))
df["turnover_med60"] = roll("turnover_eur", "median")
df["vol_ratio"] = df["turnover_eur"] / df["turnover_med60"]
df["vol_z"] = (df["log_turnover"] - roll("log_turnover", "mean")) / roll("log_turnover", "std")
df["abn_ret_z"] = df["abn_ret"] / roll("abn_ret", "std")
for c in ("xlm_25k", "xlm_100k"):
    if c in df:
        df[f"{c}_med60"] = roll(c, "median")
        df[f"{c}_ratio"] = df[c] / df[f"{c}_med60"]
df["auction_share_med60"] = roll("auction_share", "median")
df = df.drop(columns=["log_turnover", "idx_peer"])

# ---------------------------------------------------------------------------
# 7. Write outputs
# ---------------------------------------------------------------------------
df.to_parquet(OUT / "daily_features.parquet", index=False)

uni = (df.groupby("isin")
         .agg(ticker=("ticker", "last"), name=("name", "last"), idx_latest=("idx_latest", "last"),
              days=("date", "count"), avg_turnover_eur=("turnover_eur", "mean"),
              median_xlm_25k=("xlm_25k", "median") if "xlm_25k" in df else ("ret", "count"),
              flow_censored_days=("flow_censored", "sum"))
         .reset_index().sort_values(["idx_latest", "avg_turnover_eur"], ascending=[True, False]))
last_member = members.groupby("isin")["date"].max().rename("last_member_date")
uni = uni.merge(last_member, on="isin", how="left")
uni["member_now"] = uni["last_member_date"] == df["date"].max()  # XLM only exists while a member
uni.to_csv(OUT / "universe.csv", index=False)

cand = df[df["idx_latest"].isin(["MDAX", "SDAX"]) & ~df["possible_corp_action"]].copy()
cand["score"] = cand["abn_ret_z"].abs() + cand["vol_z"].clip(lower=0)
cand = cand.dropna(subset=["score"]).sort_values("score", ascending=False)
cols = ["date", "ticker", "name", "idx_latest", "ret", "peer_ret", "abn_ret", "gap_open",
        "ret_intraday", "vol_ratio", "vol_z", "abn_ret_z", "xlm_25k_ratio",
        "agent_aggr_imbalance", "auction_share", "score"]
cand[[c for c in cols if c in cand]].head(60).to_csv(OUT / "hero_candidates.csv", index=False)

log(f"[7] daily_features: {len(df):,} rows x {df.shape[1]} cols, "
    f"{df['isin'].nunique()} stocks -> {OUT / 'daily_features.parquet'}")
log(f"    flows censored: {df['flow_censored'].mean():.1%} | "
    f"XLM missing: {df['xlm_25k'].isna().mean():.1%}" if "xlm_25k" in df else "")
