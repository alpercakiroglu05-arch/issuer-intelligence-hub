# Issuer Intelligence Hub

**Decode your share price: AI-powered Xetra trading insights for investor relations.**
Futury Build Days 2026 · Deutsche Börse challenge "Issuer Intelligence Hub and corporate event impact tracker"

Mid- and small-cap IR teams cannot easily see how their own share trades or how the market reacted
to their announcements. They have no terminal and no analyst, so they wait days for broker reports.
This tool answers two questions with one click:

- **Part A, Dashboard: "How does our share normally trade?"** Turnover, trading cost (XLM spread), auctions, who trades, comparison with index peers, unusual days.
- **Part B, Impact card: "What happened when we announced X?"** Move vs. peers, volume vs. normal, spread, auctions, participant flows and intraday reaction, exported as an IR snapshot (DE/EN).

> **Design rule: numbers come from code, words come from the LLM.**
> The engine computes every figure deterministically. The LLM only sees the resulting JSON and writes text.
> Without an API key the app still runs on template texts.

---

## Quick start

```bash
git clone https://github.com/Bthn28/futury-build-days-2026 && cd futury-build-days-2026
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # optional: add LLM key
```

**Data.** Raw data is never in git. Copy the processed files into `data/` from the shared OneDrive folder:
`daily_features.parquet`, `universe.csv`, `events.parquet`, `intraday_bars.parquet`.

```bash
streamlit run app/Home.py      # demo UI -> http://localhost:8501
pytest                         # smoke tests (data tests skip if data/ is empty)
```

Rebuild the processed data. Only the data owner (C1) needs the 8.9 GB raw excerpt for this.

```bash
python ingest/build_daily.py "<path to Futury MDS Data Excerpt>" data     # ~25 s → daily_features.parquet, universe.csv, hero_candidates.csv
python ingest/build_events.py                    # events/events.csv → data/events.parquet
python ingest/build_intraday.py EVD EVT HDD GXI  # ~2 min → data/intraday_bars.parquet (resumable: --max-seconds 150)
```

---

## Architecture

```
 Raw DB excerpt (8.9 GB)              events/events.csv (research team)
  XETRA_OHLC · FLOW_DYNAMICS ·                │
  XLM spreads · index_constituents ·          │
  XETRA_ONBOOK_TRADES                         │
          │  ingest/  (run once)              │
          ▼                                   ▼
  data/daily_features.parquet   data/intraday_bars.parquet   data/events.parquet
  (174 stocks × 213 days)       (1-min bars, hero stocks)    (+ timing, reaction_day)
          └───────────────┬───────────────────┘
                          ▼
  engine/   baseline.py (Part A) · impact.py (Part B) · compare.py      ← deterministic
                          ▼  JSON
  ai/       narrate.py (DE/EN text) · agent.py (Q&A)                    ← LLM sees JSON only
                          ▼
  app/      Streamlit: Dashboard · Impact card · Compare · Assistant
  report/   IR snapshot HTML/PDF
```

```
futury-build-days-2026/
├── config.py              paths, windows, thresholds (single source of truth)
├── ingest/                build_daily.py ✅ · build_events.py ✅ · build_intraday.py ✅
├── engine/                data.py ✅ · baseline.py ✅ · impact.py ✅ (v1) · compare.py 🔲
├── ai/                    llm.py ✅ · narrate.py ✅ · agent.py ✅ (v1)
├── report/                template.html ✅ · export.py ✅
├── app/                   Home.py · pages/1_Dashboard · 2_Impact_Card · 3_Compare · 4_Assistant
├── events/                events.csv · sectors.csv   (filled by the research team)
├── docs/                  API_CONTRACT · SCOPE · PITCH
├── tests/                 smoke tests (pytest)
└── data/                  processed files (gitignored)
```

---

## Work packages (4 coders)

Everyone works on their own files, so merge conflicts are rare. Contracts between modules are fixed (see below).

### C1 · Data. Owner: Oguzhan
- [x] `ingest/build_intraday.py`: 1-min bars (first EVD, EVT, HDD, GXI; now all event stocks)
- [x] Sanity check: daily sum of bars = `turnover_eur` (ratio 1.000 on all 213 days × 4 stocks)
- [x] News onset (`engine/onset.py`, PR #5): "the market started pricing the news at HH:MM" on the card; infers the timing when the announcement time is unknown; lists volatility interruptions
- [x] Opening/closing auctions (`engine/auctions.py`, PR #6): volume vs normal and price formation, measured at the exact uncross minute (= 97.6–99.7 % of flow auction turnover)
- [x] Intraday bars for all 44 stocks in `events.csv` (3.8M bars, ~170 MB; every ISIN of a ticker, FRE and QIA changed ISIN), read per stock with `engine.data.intraday(isin)`. Onset and auction volumes now work for the DAX H1 events too
- [ ] Ongoing: share `data/events.parquet` on OneDrive when `events.csv` changes (the app already rebuilds it from the CSV by itself)
- [ ] Optional: Eurex single-stock options and futures open interest (`EUREX_OPEN_INTEREST_DYNAMICS_EQUITYINDEX`, join on `ISIN_UNDERLYING`) to show derivatives positioning before events

### C2 · Engine. Owner: Kaan (ydnka)
- [x] `engine/compare.py` v1 (PR #7, written by C1 to unblock the demo): `same_type_events`, `percentile`, `comparison_for`, `sector_peers`. Fills `card["comparison"]`; falls back to auto-detected unusual days until `events.csv` has typed events. **C2 owns it from here.**
- [x] `impact.py`: intraday block refined (news onset, exact auction volumes)
- [x] `baseline.py`: liquidity trend ("has liquidity improved?"), merge consecutive anomaly days
- [x] Unit tests: GXI 2026-02-11 should give ret ≈ −31.4 %, abnormal ≈ −30.5 %, volume ≈ 20× normal (`test_impact_card_known_values`)

### C3 · Frontend. Owner: Alper
- [ ] Impact card design (the demo moment): follow the designer's sketch
- [ ] Intraday chart: event-time marker ✅ (onset line, PR #5), highlighted auctions still open
- [x] Compare page: scatter of abnormal return vs volume ratio, selected stock highlighted (PR #7)
- [ ] Polish: colors, empty states, loading, one clean end-to-end flow for the pitch
- [ ] Part A: auction share over time chart on the dashboard (brief point I)

### C4 · AI + report. Owner: ________
- [ ] Get the JAIF / LLM endpoint working in `.env`
- [ ] `narrate.py`: tune the prompt and add a numbers check (every number in the text must exist in the JSON)
- [ ] `agent.py` v2: tool calling with `TOOLS` (kpis, anomalies, impact_card)
- [ ] `report/`: PDF layout, a small chart, **Part A snapshot** (the brief asks for an exportable dashboard report). Auction and comparison rows are already in the event snapshot

### Non-code (research and pitch team)
- [x] `events/events.csv`: 80 sourced events (hero stocks + first H1/Q3 publication of all 40 DAX members). **Please spot-check the hero rows (source link, time) before the pitch.**
- `events/sectors.csv`: sector of every DAX/MDAX/SDAX stock
- Pitch deck (3–5 slides), demo script, backup video (2–3 min), and the list "what else IR needs + which data"

---

## Data contracts

All schemas (`daily_features`, `intraday_bars`, `events.csv`, `impact_card` JSON) and the engine functions are in **[docs/API_CONTRACT.md](docs/API_CONTRACT.md)**. Changing a schema? Tell C3 and C4 first.

## Data pitfalls (already handled in `build_daily.py`, keep in mind for new code)
- **Flows**: `DATE` is the publication date, so use `REPORTED_FLOW_DATES`. Fewer than 7 executions means censored; the row then appears later, summed with other days. `VOLUME` counts both sides.
- **OHLC**: open/high/low/close are **quoted mid prices**. Use auction prices for returns. Ignore `ADJUSTED_PRICE`. Use EUR lines only.
- **Trades**: timestamps are **UTC** and must be converted to Europe/Berlin (watch DST). Empty `SIDE` = auction trade. Trading runs 08:00–22:00, so filter to the session you need.
- **Index lists**: if a day is missing, use the previous file. TKCC was an MDAX member for one day only (spin-off on 28 Oct).

## Conventions
See **[CONTRIBUTING.md](CONTRIBUTING.md)**. In short:
- `main` must always run: `streamlit run app/Home.py` and `pytest`. Use branches `feat/<name>-<topic>` and small PRs.
- Paths and thresholds go in `config.py` only. Never commit data or `.env`.
- Engine functions return plain dicts and DataFrames, never Streamlit objects.
- No investment advice in any text. The tool explains the past and does not predict.

## Timeline
| When | Milestone |
|---|---|
| Wed 18:00 | End-to-end on real daily data (✅ skeleton) + events v1 |
| Wed 22:00 | Intraday bars + comparison + LLM text live |
| Thu 08:30 | Review, cut scope |
| Thu 11:00 | **Feature freeze** |
| Thu 12:00 | Backup demo video recorded |
| Thu 13:30 | Demo submission · 14:30 deck · 15:00 pitch |

**Data:** Deutsche Börse Xetra/Eurex excerpt, 2 Jan to 30 Oct 2026, provided for Futury Build Days. Not for redistribution.
