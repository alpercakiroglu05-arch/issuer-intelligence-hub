# C2 · Engine: comparisons (`engine/compare.py`)

Owner: Kaan (`ydnka`). Branch: `feat/kaan-compare`. Status: v1 done, tested, **not yet wired into `impact_card`**.

This file is for teammates (and their Claude sessions) who need to use or integrate the comparison block.

## What was done

| File | Change |
|---|---|
| `engine/compare.py` | `same_type_events`, `percentile`, `add_comparison`, `sector_peers` implemented |
| `engine/baseline.py` | bug fix: `anomalies()` raised `ValueError` for a stock with no unusual day (3 stocks in the data). It now returns an empty DataFrame with the usual columns |
| `app/pages/3_Compare.py` | minimal: `NOTABLE_DAY` added to the type list, real table instead of "Coming soon", fallback caption, spinner, empty state |
| `tests/test_compare.py` | 8 tests (3 without data, 5 with data) |

Not touched on purpose (Oğuzhan's open branch `feat/oguzhan-news-onset` changes them):
`engine/impact.py`, `docs/API_CONTRACT.md`, `tests/test_smoke.py`, `config.py`, `app/components.py`.

## Functions

### `same_type_events(event_type: str, index: str | None = None) -> pd.DataFrame`
One row per event of `event_type` in `index` (`"DAX" | "MDAX" | "SDAX"`, `None` = all), each computed with
`impact_card(isin, reaction_day, event)`. Index membership uses `idx_latest` (the same field `card["index"]` uses).

**Fallback:** if `event_type == "NOTABLE_DAY"` or fewer than `MIN_EVENTS = 5` events of that type exist in
`events.csv`, the rows are the notable days of the index (`baseline.anomalies()` for every member,
z ≥ `ANOMALY_Z`). The `source` column tells you which: `"event"` or `"notable_day"`.
Today `events.csv` only has 5 `TBD` rows, so **every type currently falls back to notable days**.

Columns:
`isin, ticker, name, index, reaction_day (str YYYY-MM-DD), title, abn_ret, car_0_5, vol_ratio, vol_z,
xlm_25k_ratio, auction_share_delta (day − baseline median), agent_aggr_imbalance, source`

Rows whose `impact_card` raises are skipped; the count is logged (`logging.warning`, logger `engine.compare`).
Cached with `lru_cache` per `(event_type, index)`; the function returns a copy, so mutating it is safe.

Sizes and cold build times (laptop, ~30 ms per card): DAX 214 rows / ~7 s, MDAX 216 / ~7 s,
SDAX 441 / ~14 s, all ~26 s. Warm calls are instant. To pre-warm before the demo, open the Compare page
once per universe (or call `add_comparison` once for each hero).

Example (`same_type_events("NOTABLE_DAY", "MDAX").head(1)`):
```
isin          ticker name               index reaction_day title                             abn_ret  car_0_5 vol_ratio vol_z xlm_25k_ratio auction_share_delta agent_aggr_imbalance source
DE0005089031  UTDI   UTD.INTERNET AG NA MDAX  2026-09-22   Notable day: stock-specific move  -0.0524  -0.0736 1.62      1.11  0.96          0.2082              0.1762               notable_day
```

### `percentile(card: dict, table: pd.DataFrame) -> dict`
Where `card` sits in `table`. The card's own row (same `isin` and `reaction_day`) is excluded.
Percentile = share of the other non-null rows with a **lower** value (0..1). Metrics: `abn_ret`,
`abs_abn_ret` (size of the move, either direction), `vol_ratio`, `xlm_25k_ratio`.
The summary rounds percentiles **down** (0.995 → "99%"), so the text never claims "100%".
All numbers in `summary` come from the card or the table (design rule: numbers from code).

### `add_comparison(card: dict, index: str | None = None) -> dict`
`card["comparison"] = percentile(card, same_type_events(card["event"]["type"], index or card["index"]))`.
Mutates and returns the card.

### `sector_peers(isin: str) -> list[str]`
Other ISINs in the same sector from `events/sectors.csv` (tickers mapped to ISINs via `universe.csv`).
Falls back to the other members of the stock's `idx_latest` when the stock is not in the file or has no
sector peer. Example: `sector_peers(GXI) == [EVT]` (both Healthcare); `sector_peers(SAP)` → 41 DAX ISINs.
Not used by the engine yet (peer returns are still index-based in `ingest/build_daily.py`).

## `card["comparison"]` schema (draft, to be added to `docs/API_CONTRACT.md`)

```json
{
  "event_type": "NOTABLE_DAY",        // type compared against ("NOTABLE_DAY" when the fallback was used)
  "index": "MDAX",                    // universe of the table
  "source": "notable_day",            // "event" | "notable_day"
  "n": 215,                           // rows compared against (own row excluded)
  "pctile": {"abn_ret": 0.005, "abs_abn_ret": 0.995, "vol_ratio": 0.94, "xlm_25k_ratio": 0.732},  // 0..1 or null
  "median": {"abn_ret": 0.0097, "abs_abn_ret": 0.0545, "vol_ratio": 3.46, "xlm_25k_ratio": 1.09}, // of the table
  "summary": "Compared with 215 notable days in the MDAX, the move (-21.7% vs peers) is larger than 99% of them and turnover (8.6x normal) is higher than 94%."
}
```
Real output for EVD 2026-03-27 (above) and EVT 2026-07-14:
`n=440 (SDAX), abs_abn_ret 0.993, vol_ratio 0.816` → "…the move (-23.8% vs peers) is larger than 99% of them and turnover (8.3x normal) is higher than 81%."

## What is left for integration

1. **`impact.py`** (with Oğuzhan, after `feat/oguzhan-news-onset` is merged): replace `"comparison": None`
   by a call to `add_comparison(card)`. Mind the import cycle (`compare` imports `impact`), so import inside
   the function or call `add_comparison` from the app/report layer instead. Consider making it optional
   (`impact_card(..., compare=True)`) because the first call per index costs 7–14 s.
2. **`docs/API_CONTRACT.md`**: add the schema above in the same PR as step 1; tell C3 and C4.
3. **C3 UI**: render `comparison.summary` + the percentiles in `components.render_card`; scatter
   `abn_ret` vs `vol_ratio` on the Compare page with the selected stock highlighted.
4. **C4 AI/report**: `narrate` may quote `comparison.summary`; the numbers check must include the
   `comparison` block.
5. **Research team**: once `events.csv` has ≥ 5 verified rows of one type (e.g. DAX Q3 results), that type
   switches to real events automatically. No code change needed.

## Known limits

- `events.csv` is effectively empty → all comparisons are "vs. notable days of the same index", not vs.
  same-type corporate events. The UI says so.
- Notable days come from `anomalies()` per stock without merging consecutive days, so an episode of
  several days counts several times.
- Index = `idx_latest`, not the index on the event day (a stock that left the SDAX, like GXI, is compared
  with its current universe).
- `sectors.csv` has 4 rows, so `sector_peers` mostly falls back to index members.
- Cache is per process; a Streamlit restart rebuilds tables on first use.
