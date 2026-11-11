# C2 · Engine notes

Owner: Kaan (`ydnka`). For teammates and their Claude sessions: what the C2 functions return and how to use them.
Contracts (short form) are in `docs/API_CONTRACT.md`; this file has the details and examples.

C2 modules: `engine/baseline.py` (Part A, "how does our share normally trade?"), `engine/impact.py`
(impact card), `engine/compare.py` (same-type comparison; v1 by C1 in PR #7, follow-up PR #11; peer groups by
index, sector and turnover cohort).

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

## Peer groups: index, sector, turnover cohort (size proxy)

Briefing II asks to compare a stock with peers by **sector and size**, not only by index.
`engine.compare.peer_group(isin, by)` returns `{by, name, label, isins, n, fallback}` for `by` = `"index"`, `"sector"`
or `"size"`. The stock itself and other ISINs of the same ticker (FRE, QIA) are never in `isins`.

### Sector: `events/sectors.csv`

- **Source:** Deutsche Börse, *Listed Companies Frankfurt Stock Exchange* (Issuer Services), file
  [Listed-companies.xlsx](https://www.cashmarket.deutsche-boerse.com/resource/blob/67858/c0cedb209ed3143463ce6675b641225b/data/Listed-companies.xlsx).
  The file is dated 31 Oct 2026 (Excel date 46327) and covers the Prime Standard, General Standard, Scale and Basic Board sheets.
- **Matching:** matched on **ISIN**, using the `Sector` and `Subsector` columns. 169 of the 174 universe ISINs match directly.
  Cells are stripped first; some ISIN cells end with a non-breaking space, e.g. Vincorion's.
- **Classification:** one classification, the Deutsche Börse **Prime Standard sectors** (18). They are mapped to
  **11 groups** so that each group has enough peers:

| Group | Deutsche Börse Prime Standard sector | Stocks |
|---|---|---|
| Industrials | Industrial, Construction | 47 |
| Technology | Software, Technology | 22 |
| Consumer | Consumer, Food & Beverages, Retail | 20 |
| Healthcare | Pharma & Healthcare | 18 |
| Financials | Banks, Financial Services (except subsector Real Estate), Insurance | 17 |
| Materials | Chemicals, Basic Resources | 12 |
| Automotive | Automobile | 11 |
| Media & Telecom | Media, Telecommunication | 11 |
| Real Estate | Financial Services with subsector "Real Estate" | 9 |
| Transport & Logistics | Transportation & Logistics | 4 |
| Utilities | Utilities | 2 (E.ON, RWE → `small_peer_group`) |

- **ISIN changes:** 4 ISINs are no longer in the file because the company changed its ISIN. Each takes the sector of
  the ISIN the file lists today:
  - FRE `DE0005785604` → `DE000FRE5EN2`
  - QIA `NL0015002CX3` → `NL0015002SN0`
  - ACT (Alzchem, old) `DE000A2YNT30` → `DE000A41YHG1` (= our ACT0)
  - VRV (Verve) `SE0018538068` → `IE000ZVY0237` (same name and trading symbol VRV)
- **Left blank on purpose** (not in the Deutsche Börse file, no guess): **KCO** Klöckner & Co `DE000KC01000`.
  For it, `peer_group(..., "sector")` falls back to the index (`fallback: "index"`, flag `no_sector`).
- **Rebuild:** `ingest/build_sectors.py` takes the xlsx as a local path **or** a URL. The xlsx is not committed.
  ```bash
  python ingest/build_sectors.py https://www.cashmarket.deutsche-boerse.com/resource/blob/67858/c0cedb209ed3143463ce6675b641225b/data/Listed-companies.xlsx
  python ingest/build_sectors.py path/to/Listed-companies.xlsx [out.csv]   # default out: events/sectors.csv
  ```
  - The script reads the xlsx with the standard library (no `openpyxl`), strips labels and normalises their case
    (`Financial services` → `Financial Services`), then applies `GROUP` and `SAME_COMPANY`.
  - It stops with an error if a new Deutsche Börse sector has no group.
  - Every filled row carries the source URL. Download page:
    https://www.cashmarket.deutsche-boerse.com/cash-en/Data-Tech/statistics/listed-companies (the blob URL changes when
    Deutsche Börse publishes a new file).

### Size: turnover cohort (size proxy), NOT market cap

Market capitalisation is not in the data. The size group is a **turnover cohort**:
- take each ISIN's median daily turnover over its last `config.SIZE_COHORT_DAYS` (60) trading days;
- split all 174 ISINs into terciles: `large`, `mid`, `small` (58 each, `config.SIZE_COHORT_LABELS`).

Always call it **"turnover cohort (size proxy)"** in the UI. `peer_group(..., "size")["label"]` already says
`"Turnover cohort (size proxy): mid"`.

### Where the groups are used

- **`kpis()`:** every median pair now has `index_median` (unchanged), `sector_median` and `size_median`, computed the
  same way as the index median (per-stock median over the window, then the median across the group including the stock).
  - `peer_groups`: `{index, sector, size}` with `name, label, n, fallback`.
  - `flags`: `small_peer_group` when any group has fewer than `config.MIN_PEER_GROUP` (3) peers; `no_sector` when the
    sector is unknown.
- **`liquidity_trend()`:** `vs_sector` (`"stock-specific"` / `"sector-wide"` / `null`) next to `vs_index`, same rule,
  plus `sector`, `sector_median`, `sector_xlm_25k_change_pct`, `sector_turnover_change_pct`. `vs_sector` is `null` when
  the sector is unknown (`no_sector`) or has fewer than 3 peers (`small_peer_group`). The `summary` sentence is unchanged.
- **Not changed:** `impact_card` and its abnormal return (index peers, computed in ingest), and `comparison_for()`.

Example, HDD (SDAX, small cap), median XLM 25k over the last 60 days:
- the stock: 72 bps
- index (SDAX): 71 bps
- sector (Industrials, 45 peers): 32 bps
- turnover cohort `small` (57 peers): 77 bps

The sector mixes large and small industrials, so for a small cap the turnover cohort is the fairer benchmark.

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

### For C3: "Compare with: Index / Sector / Size" on the Dashboard

C2 does not touch the Dashboard page; this is a suggestion. It was tested headless for HDD, RWE (`small_peer_group`)
and KCO (`no_sector`) with every option.

```python
from components import bps

k = baseline.kpis(isin)
LABELS = {"Index": "index", "Sector": "sector", "Size": "size"}
choice = st.segmented_control("Compare with", list(LABELS), default="Index") or "Index"
by = LABELS[choice]
key = {"index": "index_median", "sector": "sector_median", "size": "size_median"}[by]
g = k["peer_groups"][by]
st.caption(f"Peer group: {g['label']} ({g['n']} peers)"
           + (" - sector unknown, showing the index" if g["fallback"] else ""))
if g["n"] < 3:
    st.warning("Small peer group: medians rest on fewer than 3 other stocks.")
c = st.columns(2)
c[0].metric("Trading cost XLM 25k", bps(k["median_xlm_25k_bps"]["stock"]),
            f"peers {bps(k['median_xlm_25k_bps'][key])}", delta_color="off")
c[1].metric("Median turnover", f"€{k['median_turnover_eur']['stock'] / 1e6:.1f}m",
            f"peers €{k['median_turnover_eur'][key] / 1e6:.1f}m", delta_color="off")
```
- Use the engine's `label` as is; it says "Turnover cohort (size proxy)" and never "market cap".
- For charts over time, build a peer series like `index_benchmark()` does, from `peer_group(isin, by)["isins"]`:
  `daily()[daily()["isin"].isin(isins)].groupby("date")[col].median()`. Mind the column vs `DataFrame.isin` gotcha.

## Known limits

- The index median uses `idx_latest`, so a stock that changed index is compared with its current index.
- Medians over 60 trading days react slowly; one huge day hardly moves them (by design).
- DS category is an estimate (order book turnover only, XLM median), not the official Deutsche Börse classification.
- `monthly` covers Jan–Oct 2026 (the data excerpt); the first and last months can be partial.
- Sectors are a snapshot (Deutsche Börse list of 31 Oct 2026); 1 stock (KCO) is blank. Utilities has only 2 stocks.
- The turnover cohort is a size proxy: a large but rarely traded company can land in `small`. Old ISINs (FRE, QIA,
  ACT) are ranked on their own last 60 trading days.
- Alzchem's two ISINs have different tickers (ACT, ACT0), so they can appear in each other's peer lists.
