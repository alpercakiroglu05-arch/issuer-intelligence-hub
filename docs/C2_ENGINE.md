# C2 · Engine notes

Owner: Kaan (`ydnka`). For teammates and their Claude sessions: what the C2 functions return and how to use them.
Contracts (short form) are in `docs/API_CONTRACT.md`; this file has the details and examples.

C2 modules: `engine/baseline.py` (Part A, "how does our share normally trade?"), `engine/impact.py`
(impact card), `engine/compare.py` (same-type comparison; v1 by C1 in PR #7, follow-up PR #11).

## `baseline.liquidity_trend(isin, window=60) -> dict`

The IR question: **"Has our liquidity improved?"** Compares the last `window` trading days with the `window`
days before, for the stock and for the median of its index (`idx_latest`, via `index_benchmark()`).

- **Trading cost** = median XLM 25k (bps). Lower is better.
- **Turnover** = median daily Xetra order book turnover (EUR). Higher is better.
- **`verdict`** (absolute, threshold `config.LIQUIDITY_TREND_TOL` = ±10 %):

  | verdict | rule |
  |---|---|
  | `improved` | at least one metric better by ≥ 10 %, none worse by ≥ 10 % |
  | `worsened` | at least one metric worse by ≥ 10 %, none better by ≥ 10 % |
  | `mixed` | one better and one worse (e.g. cheaper to trade, but less turnover) |
  | `stable` | both within ±10 % |
  | `null` | fewer than `2 × window` trading days (`flags: ["short_history"]`) |

  Without XLM (a stock is not an index member, e.g. GXI after 9 Apr) only turnover decides (`flags: ["no_xlm"]`).
- **`vs_index`**: `"stock-specific"` if a metric that moved ≥ 10 % moved at least 10 points differently from
  the index median, else `"market-wide"`. `null` for `stable`/`null` verdicts.
- **`ds_category`**: Designated Sponsor category estimate `{"now", "before"}`, same rule as `kpis()`
  (XLM 25k ≤ 100 bps and average turnover ≥ EUR 2.5m → A, else B) over the last `DS_LOOKBACK_DAYS` (84)
  days vs the 84 days before. `null` when XLM is missing.
- **`monthly`**: list of `{month "YYYY-MM", xlm_25k_bps, turnover_eur, index_xlm_25k_bps, index_turnover_eur}`
  (monthly medians) for a chart.
- **`summary`**: one English sentence; every number comes from the fields above. Percent changes are
  whole numbers with ASCII signs (`-33%`), so a numbers check can find them in the JSON.
- **`help`**: a fixed 1–2 sentence explanation of the verdict (see "For C3" below).

Example, HDD (Heidelberger Druck, SDAX), `monthly` shortened:
```json
{"isin": "DE0007314007", "ticker": "HDD", "index": "SDAX", "window": 60,
 "period": "last 60 vs previous 60 trading days",
 "stock":        {"xlm_25k_bps": {"before": 108.19, "now": 72.2},   "turnover_eur": {"before": 1128746.0, "now": 560655.0}},
 "index_median": {"xlm_25k_bps": {"before": 82.22,  "now": 69.84},  "turnover_eur": {"before": 1010427.0, "now": 1074745.0}},
 "xlm_25k_change_pct": -0.3327, "turnover_change_pct": -0.5033,
 "index_xlm_25k_change_pct": -0.1506, "index_turnover_change_pct": 0.0637,
 "verdict": "mixed", "vs_index": "stock-specific",
 "help": "Trading got cheaper, but fewer shares traded (or the other way round). Check both before telling the board that liquidity improved.",
 "ds_category": {"now": "B", "before": "B"},
 "monthly": [{"month": "2026-01", "xlm_25k_bps": 82.29, "turnover_eur": 1245866.0, "index_xlm_25k_bps": 69.8, "index_turnover_eur": 1150711.0}, "…"],
 "summary": "Mixed: trading cost -33% (better), turnover -50% (worse), last 60 vs previous 60 trading days. SDAX median: trading cost -15%, turnover +6%.",
 "flags": []}
```
Other stocks (Oct 2026 data):
- EVD: `stable`, "trading cost +3% (about the same), turnover -1% (about the same) … MDAX median: trading cost +3%, turnover -13%."
- HAG: `worsened`, stock-specific (turnover -41% vs MDAX median -13%).

## `baseline.anomaly_episodes(isin) -> DataFrame`

`anomalies()` lists every unusual day separately; a news story often spans several days. Episodes merge
**consecutive trading days** (Fri + Mon count as consecutive) into one row:

| column | meaning |
|---|---|
| `start`, `end`, `days` | first/last day and number of unusual days |
| `peak_date`, `peak_abn_ret` | the day with the highest `severity` and its abnormal return |
| `total_abn_ret` | sum of abnormal returns over the episode days |
| `max_vol_ratio` | highest turnover vs normal |
| `reason` | union of the daily reasons (`volume spike, stock-specific move, spread widening`) |
| `severity` | max daily severity |

Sorted newest first. A stock without unusual days (HAG, TKCC) gets an empty frame with these columns.

Example, HDD:
```
start       end         days  peak_date   peak_abn_ret  total_abn_ret  max_vol_ratio  reason
2026-10-29  2026-10-29  1     2026-10-29  -0.114        -0.114         7.7            volume spike, stock-specific move
2026-04-14  2026-04-16  3     2026-04-14  +0.168        +0.100         17.7           volume spike, stock-specific move
2026-03-18  2026-03-18  1     2026-03-18  +0.096        +0.096         4.5            volume spike, stock-specific move
2026-02-05  2026-02-05  1     2026-02-05  -0.133        -0.133         5.2            volume spike, stock-specific move
```
EVD 27 Mar (Fri) + 30 Mar (Mon) become one 2-day episode with the peak on 27 Mar.

## For C3: using this on the Dashboard (`app/pages/1_Dashboard.py`)

C2 does not touch the Dashboard page; this is a suggestion.

```python
from engine import baseline
from components import pct

t = baseline.liquidity_trend(isin)
c = st.columns(3)
c[0].metric("Liquidity trend", (t["verdict"] or "n/a").capitalize(), t["vs_index"] or "",
            delta_color="off", help=t["help"])        # help = tooltip explaining the verdict
if t["stock"]["xlm_25k_bps"]["now"] is not None:            # None when the stock is not an index member
    c[1].metric("Trading cost XLM 25k", f"{t['stock']['xlm_25k_bps']['now']:.0f} bps",
                pct(t["xlm_25k_change_pct"]), delta_color="inverse")   # lower is better
c[2].metric("Median turnover", f"€{t['stock']['turnover_eur']['now'] / 1e6:.1f}m", pct(t["turnover_change_pct"]))
st.caption(t["summary"])
```
- Tested headless for HDD and GXI (`no_xlm`). For `short_history` (verdict `null`) the `before` values and all `*_change_pct` are `None`; `pct(None)` shows "n/a".
- **Chart:** `pd.DataFrame(t["monthly"])` → line chart of `xlm_25k_bps` vs `index_xlm_25k_bps` (and turnover vs
  index turnover), one point per month.
- **DS badge:** show `t["ds_category"]["now"]`. If `before != now`, the summary already says
  "Designated Sponsor category estimate: B -> A."
- **Episodes:** `baseline.anomaly_episodes(isin)` is a cleaner list than `anomalies()` for the "unusual days" table;
  keep `anomalies()` for the chart markers (one marker per day).

## Known limits

- The index median uses `idx_latest`, so a stock that changed index is compared with its current index.
- Medians over 60 trading days react slowly; one huge day hardly moves them (by design).
- DS category is an estimate (order book turnover only, XLM median), not the official Deutsche Börse classification.
- `monthly` covers Jan–Oct 2026 (the data excerpt); the first and last months can be partial.
