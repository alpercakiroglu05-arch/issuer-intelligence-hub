# C2 · Engine notes

Owner: Kaan (`ydnka`). For teammates and their Claude sessions: what the C2 functions return and how to use them.
Contracts (short form) are in `docs/API_CONTRACT.md`; this file has the details and examples.

C2 modules: `engine/baseline.py` (Part A, "how does our share normally trade?"), `engine/impact.py`
(impact card), `engine/compare.py` (same-type comparison; v1 by C1 in PR #7, follow-up PR #11; peer groups by
index, sector and the 10 shares closest by turnover).

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

## Market context: `baseline.market_context(isin, day) -> list[str]` and the `context` column

**The problem:** `anomalies()` flags index days as a "volume spike", but there is no company news behind them.
Real example: EVD on 31 Aug 2026 traded 19x its normal turnover with a price move of only -1.8%. That day
MSCI Germany deleted the stock at the close (`events.csv`, type `INDEX`).

**What was added:** every unusual day now carries a `context`, one string of comma-separated flags in this order:

| Flag | Rule | Source |
|---|---|---|
| `index_event` | `events.csv` has a `type == INDEX` row for this ISIN with this `reaction_day` | research team, sourced (most reliable) |
| `index_change` | the stock's `idx` differs from its previous trading day (entry or exit) | daily index lists (`daily_features.idx`) |
| `quarterly_expiry` | third Friday of Mar/Jun/Sep/Dec (options/futures expiry and DAX family rebalancing) | calendar |
| `monthly_expiry` | third Friday of the other months | calendar |
| `month_end_review` | last trading day of Feb/May/Aug/Nov, a **possible** MSCI review date | calendar |
| `market_wide_volume` | at least `config.MARKET_WIDE_SHARE` (25 %) of all stocks traded > `MARKET_WIDE_VOL_RATIO` (2x) normal turnover | data, all 174 stocks |

- If the third Friday is not a trading day, the expiry flag goes to the previous trading day.
- `month_end_review` is only set for complete months in the data.
- `CONTEXT_HELP` has a short English explanation per flag, meant as a tooltip. `CONTEXT_FLAGS` gives the order.
- **Columns:** `anomalies()` and `anomaly_episodes()` have a new last column, `context`; for an episode it is the union of
  its days' flags. Every `compare.same_type_events()` table (NOTABLE_DAY and typed events) also has `context` as its
  last column. No other column changed, `reason` included.
- **Context is an alternative explanation, not a verdict.**
  - It says there is a known non-news reason for heavy trading on that day. EVD on 29 May has `month_end_review`
    *and* a +10 % stock-specific move, so read `context` together with `reason` and the abnormal return.
  - The typical index day is `volume spike` only, with a small price move and a context flag.

**In the data (2026):**
- 196 of the 871 unusual days (22.5 %) have a context:
  - `market_wide_volume` 175
  - `quarterly_expiry` 112
  - `month_end_review` 49
  - `monthly_expiry` 18
  - `index_change` 3
  - `index_event` 1
- 8 trading days are market-wide: 20 Mar, 19 Jun, 18 Sep (quarterly expiries); 27 Feb, 29 May, 31 Aug (Feb/May/Aug
  month ends); 3 Mar; 23 Mar.
- The share of stocks above 2x normal turnover has a median of 7 % and a 95th percentile of 18 %, so 25 % is well
  above a normal day.
- EVD on 27 Mar (the real news day, -23 %) has no context; its market-wide share was 14.7 %.

Examples, EVD:
```
date        reason                             context
2026-08-31  volume spike                       index_event, month_end_review, market_wide_volume
2026-05-29  volume spike, stock-specific move  month_end_review, market_wide_volume
2026-03-27  volume spike, stock-specific move  (empty)
2026-02-27  volume spike, stock-specific move  month_end_review, market_wide_volume
```

## Peer groups: index, sector, similar size

**One benchmark everywhere.** `engine.compare.peer_medians(isin)` is the only place that computes peer medians:
for each group, the median over the peers of each peer's median over the market's last `config.PEER_DAYS` (60)
trading days; the stock itself is never in its peer group. `kpis()` (Streamlit, assistant, Part A report) and the
web API (`web/server.py` `peers()`) both read it, and `tests/test_compare.py` checks that they agree.
(Before, the web and the report used different size groups and aggregations: EVD's size peers showed €12.8m / 18 bps
in the web and €4.5m / 35 bps in the report.)

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

### Size: the 10 stocks closest in turnover, NOT market cap

Market capitalisation is not in the data. The size group is the **`config.SIZE_PEERS_N` (10) stocks whose median
daily turnover over the last 60 trading days is closest** to the stock's (log distance, any index).
`peer_group(..., "size")["label"]` says `"Similar size: 10 closest by turnover"`.
The old terciles (`size_cohort()`, `size_cohorts()`) still exist but are no longer a peer group: a third of all
stocks was too wide a group for "similar size".

### Where the groups are used

- **`kpis()`:** every median pair has `index_median`, `sector_median` and `size_median`, all from `peer_medians()`
  (per-stock median over the window, then the median across the peers, the stock itself excluded).
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
- turnover cohort `small` (57 peers): 77 bps (old definition; now the 10 closest by turnover)

The sector mixes large and small industrials, so for a small cap the size group is the fairer benchmark.

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
- Use the engine's `label` as is; it says "Similar size: 10 closest by turnover" and never "market cap".
- For charts over time, build a peer series like `index_benchmark()` does, from `peer_group(isin, by)["isins"]`:
  `daily()[daily()["isin"].isin(isins)].groupby("date")[col].median()`. Mind the column vs `DataFrame.isin` gotcha.

### For C3: show context days in grey with an "index day" badge

C2 does not touch `app/`; this is a suggestion.

- **Chart markers:** colour unusual days with a non-empty `context` grey and use the normal colour for the rest, so that
  company news stands out.
  ```python
  anom = baseline.anomalies(isin)
  news, ctx = anom[anom["context"] == ""], anom[anom["context"] != ""]
  # fig.add_scatter(... news ...)                       normal colour, hover: reason
  # fig.add_scatter(... ctx ..., marker_color="grey")   hover: reason + context
  ```
- **Tables (episodes, Compare page):** add a badge column, e.g. `"🏷️ index day"` when `"index_event"` or
  `"index_change"` is in `context`, and `"📅 calendar / market-wide"` for the other flags. Show the flag text as a tooltip
  from `CONTEXT_HELP`:
  ```python
  from engine.baseline import CONTEXT_HELP
  help_text = "\n".join(CONTEXT_HELP[f] for f in row["context"].split(", ") if f)
  st.caption(f"🏷️ index day", help=help_text)   # or column_config / hover text
  ```
- Word it as "index day" / "possible index or calendar effect", never "no news": the flags give a likely reason,
  not proof.

## Part A report: `report.export.part_a_html(isin, lang="en", peer_by="index") -> str`

Brief: the dashboard result "can be exported as a short report for the IR department". The Dashboard has an
**Export IR report** area at the bottom (language EN/DE, HTML and PDF buttons; PDF via `to_pdf(html)`, xhtml2pdf).
`peer_by` follows the Dashboard's "Compare with" choice and is printed in the report.

Template `report/template_part_a.html`, data from `part_a_data(isin, peer_by)`. **No new numbers**: every value
comes from the engine and is only formatted (`_fmt()`, same as the impact card snapshot).

| Section | Source |
|---|---|
| 1. Header: name, ticker, index, sector, size group, data period | `kpis()["peer_groups"]`, `data.stock()` dates |
| 2. KPIs vs index / sector / size + DS category estimate | `kpis()` |
| 3. Liquidity trend: verdict, vs index / sector, before/now/change, DS category, summary, help | `liquidity_trend()` |
| 4. Cost by order size vs the `peer_by` group | `xlm.curve_summary(xlm.cost_curve(isin, peer_by))` |
| 5. Unusual episodes (largest 8 by severity, newest first) + linked event + market context explanations | `anomaly_episodes()`, `events.csv`, `CONTEXT_HELP` |
| 6. Footer: source, "numbers computed in code; no investment advice" | fixed text |

- **DE/EN are templates, no LLM.** `liquidity_trend()["summary"]` and `help` are English only, so the DE report
  builds the summary from the same fields (`_summary_de`); verdict, help, reasons and context words have DE tables
  in `export.py`.
- **Number and date format** comes from `report/fmt.py` (`formatters(lang)`), shared with `ai/narrate.py` and the
  impact card snapshot. EN: `-23.2%`, `EUR 2.5m`, `8.6x`, `2026-03-27`. DE: `−23,2 %`, `2,5 Mio. EUR` / `561 Tsd. EUR`,
  `8,6-fach`, `27.03.2026`; bps stays `21 bps`. The PDF base font has no U+2212, so `to_pdf()` prints an ASCII `-`
  (the HTML keeps the real minus). Event titles from `events.csv` are source text and stay as written.
- The DE comparison label (`report.fmt.group_label(cmp, "de")`, e.g. "auffälligen Handelstagen, MDAX, Jan.–Okt. 2026")
  is built from `comparison.group_type`, `group_index`, `period_start`, `period_end`.
- Missing data never fails: no XLM (GXI after April, old QIA ISIN) → note in section 4; short history → verdict
  n/a; no sector (KCO) → "sector unknown, the index is used"; no episodes (HAG) → "No unusual days".
- Tests: `tests/test_report_part_a.py` (EVD, HDD, HAG, GXI, KCO, old QIA; DE+EN HTML, `%PDF`, numbers equal to
  `kpis()` / `liquidity_trend()` / `curve_summary()`).

## Known limits

- The index median uses `idx_latest`, so a stock that changed index is compared with its current index.
- Medians over 60 trading days react slowly; one huge day hardly moves them (by design).
- DS category is an estimate (order book turnover and XLM as the daily average of the last four months; unknown without XLM), not the official Deutsche Börse classification.
- `monthly` covers Jan–Oct 2026 (the data excerpt); the first and last months can be partial.
- Sectors are a snapshot (Deutsche Börse list of 31 Oct 2026); 1 stock (KCO) is blank. Utilities has only 2 stocks.
- Size is a turnover proxy: a large but rarely traded company gets small-cap peers. Old ISINs (FRE, QIA) have no
  turnover in the last 60 days and get no size peers.
- Alzchem's two ISINs have different tickers (ACT, ACT0), so they can appear in each other's peer lists.
- Context: an INDEX event matches on its `reaction_day` only. GXI's row is the STOXX announcement (8 Apr); the exit
  itself shows up as `index_change` on 10 Apr, the first day off the list, and the last member day (9 Apr) has no flag.
- `month_end_review` is a calendar rule ("possible" MSCI review), not the official MSCI calendar. Only the 2 INDEX
  rows in `events.csv` are confirmed index events.
