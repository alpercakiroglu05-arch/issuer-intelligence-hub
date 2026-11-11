# Data & API contracts

Module boundaries. Code against these, not against each other's internals.
**Changing a contract? Tell the consumers (C3 UI, C4 AI/report) first and update this file in the same PR.**

### `data/daily_features.parquet`: one row per (date, isin)
| Group | Columns |
|---|---|
| keys | `date`, `isin`, `ticker`, `name`, `idx` (index that day), `idx_latest` |
| price | `price` (closing auction, fallback last mid), `ret`, `gap_open`, `ret_intraday`, `peer_ret`, `market_ret`, `abn_ret`, `possible_corp_action` |
| activity | `shares`, `turnover_eur`, `turnover_med60`, `vol_ratio`, `vol_z`, `abn_ret_z` |
| auctions | `open_auct_px`, `open_auct_ts`, `mid_auct_px`, `close_auct_px`, `close_auct_ts`, `auction_share`, `auction_share_med60` |
| spread | `xlm_10k` … `xlm_30m` (bps per notional), `xlm_25k_ratio`, `xlm_100k_ratio` |
| who traded | `{mm,agent,prop}_{aggr,pass,auct}_{buy,sell}` (EUR, one-sided), `agent_share`, `prop_share`, `mm_share`, `agent_aggr_imbalance` (−1 sell … +1 buy), `agent_aggr_net_eur`, `flow_total_eur`, `flow_censored`, `flow_multi_day` |

Rolling baselines (`*_med60`, `vol_z`, `abn_ret_z`) use the previous 60 trading days and exclude the current day.

### `data/intraday_bars.parquet`: one row per (isin, minute). C1 builds this.
`isin, ts_local (tz Europe/Berlin, minute start), open, high, low, close (trade prices), shares, vwap, volume_eur, n_trades, aggr_buy_eur, aggr_sell_eur, auction_eur, is_auction`
All trading hours (08:00–22:00) are kept. Filter the session you need. `is_auction` = minute contains auction trades (empty SIDE): opening ~09:00, intraday ~13:00, closing ~17:35.

### `events/events.csv`, filled by hand
`ticker, isin (optional), type, date (YYYY-MM-DD), time_local (HH:MM), title, source_url, verified (0/1)`
Types: `FY Q1 H1 Q3 DIVIDEND_EX AGM ADHOC GUIDANCE MA CMD`.
`build_events.py` adds `timing` (pre_open / intraday / post_close) and `reaction_day`. A release after 17:35 counts on the next trading day.

### `impact_card()`: JSON (engine → app, AI, report)
```json
{ "schema_version": "1.0", "isin": "…", "ticker": "GXI", "name": "…", "index": "SDAX",
  "event":        {"event_id", "type", "title", "datetime_local", "timing", "source_url", "reaction_day"},
  "baseline":     {"window": "t-65..t-6", "days_used": 60},
  "price":        {"ret", "peer_ret", "abn_ret", "abn_ret_z", "gap_open", "ret_intraday", "car_0_5"},
  "volume":       {"turnover_eur", "baseline_eur", "ratio", "z"},
  "liquidity":    {"xlm_25k_bps", "xlm_25k_baseline_bps", "ratio", "days_to_normal"},
  "auctions":     {"auction_share", "auction_share_baseline"},
  "participants": {"agent_share", "agent_share_baseline", "agent_aggr_imbalance", "agent_aggr_imbalance_baseline", "agent_aggr_net_eur", "prop_share", "mm_share"},
  "intraday":     {"volume_share_first_15min", "volume_share_first_60min", "open_auction_eur", "close_auction_eur", "intraday_low", "intraday_high", "time_of_low"} | null,
  "comparison":   null,
  "flags":        ["flow_censored", "short_baseline", …] }
```
**Changing the schema? Tell C3 and C4 first.**

---

### Engine functions (Python API used by app/ and ai/)
| Function | Returns | Owner |
|---|---|---|
| `engine.data.daily()` / `stock(isin)` / `events()` / `intraday()` | DataFrames | C1/C2 |
| `engine.baseline.profile(isin, start, end)` | daily time series for the dashboard | C2 |
| `engine.baseline.kpis(isin, days=60)` | dict: medians vs index + liquidity category estimate | C2 |
| `engine.baseline.anomalies(isin)` | DataFrame: unusual days with `reason`, `severity` | C2 |
| `engine.impact.impact_card(isin, day, event=None)` | dict (schema above) | C2 |
| `engine.compare.same_type_events(type, index)` / `percentile(card, table)` | DataFrame / dict | C2 |
| `ai.narrate.narrate(card, lang)` | str (DE/EN), template fallback without LLM | C4 |
| `ai.agent.ask(question, isin)` | str | C4 |
| `report.export.to_html(card, text, lang)` / `to_pdf(html)` | str / bytes | C4 |
