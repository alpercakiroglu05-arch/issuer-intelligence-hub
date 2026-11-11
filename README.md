# Issuer Intelligence Hub

**Decode your share price: AI-powered Xetra trading insights for investor relations.**
Futury Build Days 2026 · Deutsche Börse challenge "Issuer Intelligence Hub and corporate event impact tracker"

Mid- and small-cap IR teams cannot easily see how their own share trades or how the market reacted
to their announcements. They have no terminal and no analyst, so they wait days for broker reports.
This tool answers two questions with one click:

- **Part A, Dashboard: "How does our share normally trade?"** Turnover, trading cost (XLM spread, also by order size), auctions, who trades, peers by index / sector / size, liquidity trend ("has our liquidity improved?"), unusual days with the linked announcement and market context, exportable as a short IR report (DE/EN).
- **Part B, Impact card: "What happened when we announced X?"** Move vs. peers, volume vs. normal, spread, opening/closing auction vs normal, participant flows, the minute the market started pricing the news, and a rank among events of the same type, exported as an IR snapshot (DE/EN).

> **Design rule: numbers come from code, words come from the LLM.**
> The engine computes every figure deterministically. The LLM only sees the resulting JSON and writes text.
> A numbers check rejects any model text with a figure that is not in the JSON, and the screen says which text you read.
> Without an API key the app still runs on template texts. LLM: open models via the JAIF gateway (OpenAI-compatible).

---

## Quick start

```bash
git clone https://github.com/Bthn28/futury-build-days-2026 && cd futury-build-days-2026
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # optional: add LLM key
```

**Data.** Data is never in git. Everyone has the raw excerpt: set `IIH_RAW_DIR` in `.env` and run the three ingest steps below (about 4 minutes in total).
`events.parquet` is rebuilt from `events/events.csv` automatically when the CSV is newer.

```bash
python web/server.py           # demo UI (web front end) -> http://127.0.0.1:8600
streamlit run app/Home.py      # backup UI / analyst view -> http://localhost:8501
pytest                         # 108 tests incl. the web API (data tests skip if data/ is empty)
```

Build the processed data from the 8.9 GB raw excerpt (once, and after `git pull` when `events.csv` changed):

```bash
python ingest/build_daily.py "<path to Futury MDS Data Excerpt>" data     # ~25 s → daily_features.parquet, universe.csv, hero_candidates.csv
python ingest/build_events.py                    # events/events.csv → data/events.parquet
python ingest/build_intraday.py                  # ~3 min, every stock in events.csv → data/intraday_bars.parquet (resumable: --max-seconds 150)
```

---

## Architecture

```
 Raw DB excerpt (8.9 GB)              events/events.csv (80 sourced events)
  XETRA_OHLC · FLOW_DYNAMICS ·                │
  XLM spreads · index_constituents ·          │
  XETRA_ONBOOK_TRADES                         │
          │  ingest/  (run once)              │
          ▼                                   ▼
  data/daily_features.parquet   data/intraday_bars.parquet   data/events.parquet
  (174 stocks × 213 days)       (1-min bars, 44 event stocks) (80 events + timing, reaction_day)
          └───────────────┬───────────────────┘
                          ▼
  engine/   baseline.py (Part A) · impact.py · onset.py · auctions.py (Part B) · compare.py · xlm.py  ← deterministic
                          ▼  JSON
  ai/       narrate.py (DE/EN text) · checks.py (numbers check) · agent.py (Q&A)  ← LLM sees JSON only
                          ▼
  web/      demo UI: server.py (JSON API) + app.js (Issuer Services look): ISIN entry · Dashboard ·
            Impact card · Compare · Assistant · Report (Part A + B) · Ideas
  app/      backup UI / analyst view (Streamlit): Dashboard · Impact card · Compare · Assistant
  report/   IR snapshot HTML/PDF (impact card + Part A report)
```

```
futury-build-days-2026/
├── config.py              paths, windows, thresholds (single source of truth)
├── ingest/                build_daily.py ✅ · build_events.py ✅ · build_intraday.py ✅
├── engine/                data.py ✅ · baseline.py ✅ · impact.py ✅ · onset.py ✅ · auctions.py ✅ · compare.py ✅ · xlm.py ✅
├── ai/                    llm.py ✅ (JAIF, answer cache) · narrate.py ✅ · checks.py ✅ (numbers check) · agent.py ✅ (v1)
├── report/                template.html ✅ · export.py ✅
├── web/                   demo UI: server.py · index.html · app.js · app.css (C3)
├── app/                   backup UI (Streamlit): Home.py · pages/1_Dashboard · 2_Impact_Card · 3_Compare · 4_Assistant
├── events/                events.csv (80 sourced events) · sectors.csv (174 stocks, Deutsche Börse sectors)
├── docs/                  API_CONTRACT · SUBMISSION (data, model, logic) · REQUIREMENTS (brief → web page) · C2_ENGINE · SCOPE · PITCH · design/
├── tests/                 108 tests: engine, data, Streamlit pages, web API over HTTP, numbers check
└── data/                  processed files (gitignored)
```

---

## Work packages (4 coders)

Everyone works on their own files, so merge conflicts are rare. Contracts between modules are fixed (see below).

### C1 · Data. Owner: Oguzhan
- [x] `ingest/build_intraday.py`: 1-min bars (first EVD, EVT, HDD, GXI; now all event stocks)
- [x] Sanity check: daily sum of bars = `turnover_eur` (ratio 1.000 for all 44 stocks)
- [x] News onset (`engine/onset.py`, PR #5): "the market started pricing the news at HH:MM" on the card; infers the timing when the announcement time is unknown; lists volatility interruptions
- [x] Opening/closing auctions (`engine/auctions.py`, PR #6): volume vs normal and price formation, measured at the exact uncross minute (= 97.6–99.7 % of flow auction turnover)
- [x] Intraday bars for all 44 stocks in `events.csv` (3.8M bars, ~170 MB; every ISIN of a ticker, FRE and QIA changed ISIN), read per stock with `engine.data.intraday(isin)`. Onset and auction volumes now work for the DAX H1 events too
- [x] `events/events.csv`: 80 sourced events (the research team could not, so C1 took it over)
- [x] `build_intraday.py` without arguments builds every stock in `events.csv` (PR #16)
- [x] `docs/SUBMISSION.md`: submission text (data, model, logic, validation)
- [x] Trading cost by order size (`engine/xlm.py`) on the dashboard: XLM €10k–€10m vs peers, largest order the book absorbs
- [x] Eurex open interest checked and skipped: the participant split is censored for >90 % of small-cap series

### C2 · Engine. Owner: Kaan (ydnka)
- [x] `engine/compare.py` v1 (PR #7, written by C1 to unblock the demo): `same_type_events`, `percentile`, `comparison_for`, `sector_peers`. Fills `card["comparison"]`; falls back to auto-detected unusual days until `events.csv` has typed events. **C2 owns it from here.**
- [x] `impact.py`: intraday block refined (news onset, exact auction volumes)
- [x] `baseline.py`: liquidity trend ("has liquidity improved?"), merge consecutive anomaly days
- [x] Unit tests: GXI 2026-02-11 should give ret ≈ −31.4 %, abnormal ≈ −30.5 %, volume ≈ 20× normal (`test_impact_card_known_values`)
- [x] `compare.py` extras: summary sentence, percentiles never round up to 100 % (PR #11); `anomalies()` crash fix (PR #10)
- [x] **Peer benchmarking by sector and size** (brief point II, PR #20): `sectors.csv` from Deutsche Börse's listed-companies file + a turnover cohort as size proxy (market cap is not in the data)
- [x] Index-day context in `anomalies()` (expiry Fridays, index reviews, market-wide days; use the `INDEX` rows of `events.csv`)

### C3 · Frontend. Owner: Alper
- [x] **Web front end** (`web/`, PR #27; Windows/NaN fixes in #30): the **demo UI**. Issuer Services look, ISIN entry, dashboard (volume, spread, auctions over time; peers; liquidity verdict; unusual days), impact card (minute chart with onset, auctions, who traded, aftershocks, AI summary with numbers check), compare, assistant, report (Part A + B, DE/EN, PDF) and ideas. Every brief item has one page (`docs/REQUIREMENTS.md`)
- [x] Streamlit (`app/`, backup UI): liquidity trend, episodes with events and market context, Compare with Index / Sector / Size, cost by order size, Part A report button (PRs #19–#29)
- [ ] Web: show Kaan's market context (index days, expiries, MSCI) in *Unusual days*; optional: the cost-by-order-size block (`engine.xlm`). Agree with Kaan before building

### C4 · AI + report. Owner: AskingAtlas (no commits so far; C1 and C2 took the items over)
- [x] **Part A report** (brief: the dashboard result "can be exported as a short report"): web Report tab (C3) and Streamlit button (C2, PR #29)
- [x] **Numbers check** (`ai/checks.py`, PR #28): every number in a model text must be in the card JSON, else the template is shown; both UIs say which text it is
- [x] **Assistant without a model**: short answer + liquidity summary instead of a JSON dump (Streamlit, PR #28); the web has its own fallback answers
- [x] **Answer cache** (`LLM_CACHE`, PR #28) so the live demo survives Wi-Fi/API outages
- [ ] **German formatting** in the DE texts and snapshots (`−23,2 %`, `27.03.2026`, German group label): Kaan, tonight
- [x] **JAIF**: gateway `https://hip-gw.hessian.ai/v1`, model `hIP_1.0-Mistral/Mistral-Medium-3.5-128B` (accurate, 5–7 s, good German; Kolibri-1 made meaning errors). The key is at the top of the JAIF Model Handbook HTML in Discord. The demo texts are pre-cached
- [ ] Optional: `agent.py` v2 with tool calling

### Non-code (research and pitch team)
- **Please spot-check the hero rows of `events/events.csv`** (source link, time) before the pitch.
- [x] `events/sectors.csv`: sector of every DAX/MDAX/SDAX stock (done by C2, PR #20)
- Pitch deck (3–5 slides), demo script, backup video (2–3 min), and the list "what else IR needs + which data"

---

## Data contracts

All schemas (`daily_features`, `intraday_bars`, `events.csv`, `impact_card` JSON) and the engine functions are in **[docs/API_CONTRACT.md](docs/API_CONTRACT.md)**. Changing a schema? Tell C3 and C4 first.

## Data pitfalls (already handled in `build_daily.py`, keep in mind for new code)
- **Flows**: `DATE` is the publication date, so use `REPORTED_FLOW_DATES`. Fewer than 7 executions means censored; the row then appears later, summed with other days. `VOLUME` counts both sides.
- **OHLC**: open/high/low/close are **quoted mid prices**. Use auction prices for returns. Ignore `ADJUSTED_PRICE`. Use EUR lines only.
- **Trades**: timestamps are **UTC** and must be converted to Europe/Berlin (watch DST). Empty `SIDE` = auction trade. Trading runs 08:00–22:00, so filter to the session you need.
- **Index lists**: if a day is missing, use the previous file. TKCC was an MDAX member for one day only (spin-off on 28 Oct).
- **ISIN changes**: Fresenius (FRE) and Qiagen (QIA) changed ISIN in 2026, so one ticker can map to two ISINs in `universe.csv`.

## Conventions
See **[CONTRIBUTING.md](CONTRIBUTING.md)**. In short:
- `main` must always run: `python web/server.py`, `streamlit run app/Home.py` and `pytest`. Use branches `feat/<name>-<topic>` and small PRs.
- Paths and thresholds go in `config.py` only. Never commit data or `.env`.
- Engine functions return plain dicts and DataFrames, never Streamlit objects.
- No investment advice in any text. The tool explains the past and does not predict.

## Timeline
| When | Milestone |
|---|---|
| Wed 18:00 | End-to-end on real daily data (✅ skeleton) + events v1 |
| Wed 22:00 | Intraday bars ✅ + comparison ✅ + web front end ✅ + numbers check ✅ · LLM key still open |
| Thu 08:30 | JAIF key in `.env`, demo dry run on the **web** UI, cut scope |
| Thu 11:00 | **Feature freeze** |
| Thu 12:00 | Backup demo video recorded |
| Thu 13:30 | Demo submission · 14:30 deck · 15:00 pitch |

**Data:** Deutsche Börse Xetra/Eurex excerpt, 2 Jan to 30 Oct 2026, provided for Futury Build Days. Not for redistribution.
