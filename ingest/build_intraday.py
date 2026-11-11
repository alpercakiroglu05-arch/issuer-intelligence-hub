#!/usr/bin/env python3
"""
build_intraday.py - 1-minute bars from every single Xetra trade.  OWNER: C1 (data).

Reads XETRA_ONBOOK_TRADES (213 daily files, 1.7 GB gz) for the event stocks and writes
data/intraday_bars.parquet (schema: docs/API_CONTRACT.md -> intraday_bars).

Resumable: each trading day is written to data/intraday_parts/<YYYYMMDD>.parquet and
skipped on the next run, so a slow laptop can process the year in several runs.

Usage:
    python3 ingest/build_intraday.py                       # every stock in events/events.csv + heroes (~160 s)
    python3 ingest/build_intraday.py GXI EVD               # explicit tickers
    python3 ingest/build_intraday.py --max-seconds 150     # stop after ~150 s, rerun to continue
    python3 ingest/build_intraday.py --rebuild             # ignore existing day parts

Raw data location: config.RAW_DIR (env IIH_RAW_DIR) or --raw <path>.

Data notes (XETRA_ONBOOK_TRADES/NOTES.md):
    - FACT_TIMESTAMP is UTC -> converted to Europe/Berlin (DST aware)
    - SIDE: 1 = aggressive buy, 2 = aggressive sell, empty = auction trade (no aggressor)
    - trading runs ~08:00-22:00 local; we keep everything, consumers filter the session
    - one ISIN can trade in several currencies -> EUR only
"""
import argparse
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_DIR, EVENTS_CSV, HERO_TICKERS, RAW_DIR, TZ  # noqa: E402

PARTS = DATA_DIR / "intraday_parts"
OUT = DATA_DIR / "intraday_bars.parquet"


def default_tickers() -> list[str]:
    """Every stock that has an event in events/events.csv, plus the hero stocks."""
    return sorted(set(pd.read_csv(EVENTS_CSV, dtype=str)["ticker"].dropna()) | set(HERO_TICKERS))


def isins_for(tickers: list[str]) -> dict[str, str]:
    """All ISINs of these tickers. A ticker can have several over the year (FRE and QIA changed ISIN in 2026)."""
    uni = pd.read_csv(DATA_DIR / "universe.csv")
    missing = [t for t in tickers if t not in set(uni["ticker"])]
    if missing:
        raise SystemExit(f"Unknown tickers: {missing}")
    hit = uni[uni["ticker"].isin(tickers)]
    return dict(zip(hit["isin"], hit["ticker"]))


def bars_for_day(con: duckdb.DuckDBPyConnection, path: Path, isins: list[str]) -> pd.DataFrame:
    in_list = ", ".join(f"'{i}'" for i in isins)
    t = con.execute(f"""
        SELECT ISIN AS isin, FACT_TIMESTAMP AS ts,
               CAST(QUANTITY AS DOUBLE) AS qty, CAST(PRICE AS DOUBLE) AS px, SIDE AS side
        FROM read_csv('{path.as_posix()}', all_varchar=true, header=true)
        WHERE ISIN IN ({in_list}) AND CURRENCY = 'EUR'
    """).df()
    if t.empty:
        return pd.DataFrame()
    t["ts_local"] = pd.to_datetime(t["ts"], utc=True, format="ISO8601").dt.tz_convert(TZ).dt.floor("min")
    t["eur"] = t["qty"] * t["px"]
    side = t["side"].fillna("")
    t["aggr_buy_eur"] = t["eur"].where(side == "1", 0.0)
    t["aggr_sell_eur"] = t["eur"].where(side == "2", 0.0)
    t["auction_eur"] = t["eur"].where(side == "", 0.0)
    g = t.sort_values("ts").groupby(["isin", "ts_local"], sort=True)
    b = g.agg(open=("px", "first"), high=("px", "max"), low=("px", "min"), close=("px", "last"),
              shares=("qty", "sum"), volume_eur=("eur", "sum"), n_trades=("px", "size"),
              aggr_buy_eur=("aggr_buy_eur", "sum"), aggr_sell_eur=("aggr_sell_eur", "sum"),
              auction_eur=("auction_eur", "sum")).reset_index()
    b["vwap"] = b["volume_eur"] / b["shares"]
    b["is_auction"] = b["auction_eur"] > 0
    return b


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="*", help="default: every stock in events/events.csv + the hero stocks")
    ap.add_argument("--raw", default=str(RAW_DIR))
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args()

    isin_map = isins_for(args.tickers or default_tickers())
    files = sorted((Path(args.raw) / "XETRA" / "XETRA_ONBOOK_TRADES").glob("XETRA_ONBOOK_TRADES_*.csv.gz"))
    if not files:
        raise SystemExit(f"No trade files under {args.raw}/XETRA/XETRA_ONBOOK_TRADES")
    PARTS.mkdir(parents=True, exist_ok=True)
    tag = "_".join(sorted(isin_map.values()))
    tag_file = PARTS / "TICKERS.txt"  # day parts are only valid for one ticker set
    if tag_file.exists() and tag_file.read_text() != tag:
        print(f"ticker set changed ({tag_file.read_text()} -> {tag}): rebuilding all days")
        args.rebuild = True
    tag_file.write_text(tag)

    con = duckdb.connect()
    con.execute("SET threads=2; SET memory_limit='1500MB'")
    start, done, skipped = time.time(), 0, 0
    for f in files:
        day = f.name.split("_")[-1][:8]
        part = PARTS / f"{day}.parquet"
        if part.exists() and not args.rebuild:
            skipped += 1
            continue
        if args.max_seconds and time.time() - start > args.max_seconds:
            break
        bars_for_day(con, f, list(isin_map)).to_parquet(part, index=False)
        done += 1

    remaining = len(files) - skipped - done
    print(f"days processed now: {done}, already done: {skipped}, remaining: {remaining} "
          f"({time.time() - start:.0f}s)")
    if remaining:
        print("-> run again to continue")
        return

    bars = pd.concat([pd.read_parquet(p) for p in sorted(PARTS.glob("2*.parquet"))], ignore_index=True)
    # sorted by stock + small row groups: engine.data.intraday(isin) reads only that stock's row groups
    bars = bars.sort_values(["isin", "ts_local"]).reset_index(drop=True)
    bars.to_parquet(OUT, index=False, row_group_size=50_000)
    print(f"{len(bars):,} bars for {sorted(isin_map.values())} -> {OUT}")


if __name__ == "__main__":
    main()
