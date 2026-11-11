#!/usr/bin/env python3
"""
build_intraday.py - OWNER: C1 (data).  STATUS: skeleton, to be implemented.

Builds 1-minute bars from XETRA_ONBOOK_TRADES (every single trade, 1.7 GB gz)
for the hero stocks (config.HERO_TICKERS) and, if time allows, their peers.

Usage:
    python3 ingest/build_intraday.py            # hero stocks
    python3 ingest/build_intraday.py GXI EVD    # explicit tickers

Output: data/intraday_bars.parquet  (schema in README -> "intraday_bars")

Steps
-----
1. ISINs: map tickers -> ISIN via data/universe.csv.
2. Read with DuckDB, ONE MONTH AT A TIME (the laptop has little RAM):
       read_csv('{RAW_DIR}/XETRA/XETRA_ONBOOK_TRADES/XETRA_ONBOOK_TRADES_202602*.csv.gz',
                all_varchar=true) WHERE ISIN IN (...) AND CURRENCY = 'EUR'
   Columns: FACT_TIMESTAMP (UTC, ns), ISIN, QUANTITY, PRICE, SIDE (1 buy / 2 sell / empty = auction).
3. Timestamps are UTC -> convert to Europe/Berlin (DST!). Keep 08:00-17:45 local.
4. Flag trades:
       is_auction   = SIDE is empty
       session      = 'pre' (<09:00) | 'open_auction' | 'continuous' | 'close_auction' (>=17:30)
5. Aggregate per isin x minute:
       open/high/low/close (trade prices), vwap, volume_eur = sum(qty*price), n_trades,
       aggr_buy_eur (SIDE=1), aggr_sell_eur (SIDE=2), auction_eur (SIDE empty), is_auction (any)
6. Sanity check: per day, sum(volume_eur) must be close to daily_features.turnover_eur
   (small differences = off-book/TES, which is not in this file).
7. Write data/intraday_bars.parquet.

Quick check that already worked (GXI on 2026-02-11): 10,820 trades, EUR 77.2m,
20% of the day's turnover in the first 15 minutes after 09:00.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_DIR, HERO_TICKERS, RAW_DIR  # noqa: E402,F401


def build(tickers: list[str]) -> None:
    raise NotImplementedError("C1: implement steps 1-7 from the module docstring")


if __name__ == "__main__":
    build(sys.argv[1:] or HERO_TICKERS)
