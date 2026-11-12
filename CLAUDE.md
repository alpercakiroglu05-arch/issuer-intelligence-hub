# CLAUDE.md: project context for Claude Code

Read this first. It carries the decisions and findings from the planning session
(Wed 11 Nov 2026) so that every Claude Code session starts with full context.
**Talk to Oğuzhan in Turkish. Code, comments, docs and commits stay in English.**

## What we are building

**Futury Build Days #4 (Frankfurt, 11–12 Nov 2026), Deutsche Börse challenge:
"Issuer Intelligence Hub and corporate event impact tracker".**

- **User:** Head of IR at an MDAX/SDAX company. They have no terminal and no analyst, and broker reports arrive days late.
- **Part A, dashboard:** how the share trades normally: turnover, spread (XLM), auctions, who trades, peers, unusual days.
- **Part B, impact card (the core):** an announcement or notable day becomes a card with abnormal return vs. peers, volume vs. normal, spread, auctions, participant flows and intraday reaction. It is exportable as an IR snapshot (DE/EN). It must allow comparing events of the same type (e.g. all DAX results).
- **Also requested:** ideas for what else IR needs and which data that would require (see `docs/SCOPE.md` → Won't).
- **Positioning for the jury (DB people):** a module of DB's free *Issuer Services Hub*, turning the monthly "Stock Report" PDF into something on demand and event-driven. Listing business is a structural growth driver on DB's own slide.

**Design rule: numbers come from code, words come from the LLM.** `engine/` is deterministic.
`ai/` only sees the `impact_card` JSON. Without an LLM key everything falls back to template texts,
so the demo never breaks.

## Deadlines (Thu 12 Nov)

| Time | What |
|---|---|
| 11:00 | Feature freeze (bug fixes only after this) |
| 12:00 | Backup demo video recorded (2–3 min) |
| 13:30 | Demo/prototype submission (SharePoint): link or video + "what data, model, logic" |
| 14:30 | Pitch deck PDF, 3–5 slides, focused on the demo |
| 15:00 | Live pitch: 5 min + 5 min Q&A |

Jury criteria: **Idea, Execution, Relevance, Pitch.** Prize: a ticket to DB's capital markets conference on 23 Nov.

## Team

- 6 people: 4 coders + 2 non-code (research/events + pitch).
- **Oğuzhan** (`Bthn28`) is the tech lead. He merges PRs and owns **C1 (data) together with Claude**, because the raw data is on his laptop.
- C2 engine · C3 app/UI · C4 AI + report: the other coders. Work packages and checklists are in `README.md`.
- GitHub collaborators to invite: `ydnka`, `alpercakiroglu05-arch`, plus one more. Status: pending, blocked on GitHub "Confirm access".

## How to work in this repo

```bash
pip install -r requirements.txt
python web/server.py                      # demo UI (web/hub, C3): http://127.0.0.1:8600 (previous UI: /index.html)
streamlit run app/Home.py                 # backup UI and analyst view: http://localhost:8501
pytest                                    # 205 tests (incl. web API); data tests skip if data/ is empty
python web/warm_cache.py                  # re-warm the demo caches (summaries + assistant) after ANY prompt, card or engine change
```
- Branch `feat/<name>-<topic>` → PR → lead merges. `main` must always run (see `CONTRIBUTING.md`).
- Before a PR, run `pytest` **and** a headless page check:
  ```python
  from streamlit.testing.v1 import AppTest
  for p in ["app/Home.py","app/pages/1_Dashboard.py","app/pages/2_Impact_Card.py","app/pages/3_Compare.py","app/pages/4_Assistant.py"]:
      at = AppTest.from_file(p, default_timeout=120); at.run(); assert not at.exception, (p, at.exception)
  ```
- Paths and thresholds go in `config.py` only. Contracts live in `docs/API_CONTRACT.md`; update it in the same PR when a schema changes.
- Never commit `data/`, `.env` or raw files. The processed data is shared via OneDrive.
- Use `st.plotly_chart(..., width="stretch")`, not `use_container_width` (deprecated).
- pandas gotcha: never write `df.isin` when you mean the column `df["isin"]`. `isin` is a DataFrame method, and this bug has already bitten us twice.

## Data

**Raw excerpt (8.9 GB, Jan 2 – Oct 30 2026, 213 trading days)** lives on Oğuzhan's laptop:
`C:\Users\Oğuzhan\OneDrive\Masaüstü\Futury MDS Data Excerpt\` (set `IIH_RAW_DIR` or pass the path).
Each folder has a `NOTES.md` and a PDF data dictionary.

| Used | Folder | What |
|---|---|---|
| ✅ | `XETRA/XETRA_OHLC` | daily OHLC (**quoted mid prices**), auction prices/times, turnover |
| ✅ | `XETRA/XETRA_FLOW_DYNAMICS_EQUITY` | who traded: MM/AGENT/PROP × AGGRESSIVE/PASSIVE/AUCTION × BUY/SELL |
| ✅ | `dax_mdax_sdax_liquid_spreads.*.tgz` | XLM `Impact_bps` per notional (10k … 30m), daily |
| ✅ | `index_constituents` | daily DAX(40)/MDAX(50)/SDAX(70) lists |
| ✅ | `XETRA/XETRA_ONBOOK_TRADES` (1.7 GB) | every trade, ns UTC timestamps; we build 1-min bars from it |
| optional | `EUREX/EUREX_OPEN_INTEREST_DYNAMICS_EQUITYINDEX` | single-stock options/futures OI by participant, long/short (`ISIN_UNDERLYING`) |
| ❌ | Eurex settlement prices (5.2 GB), other Eurex, ETP flows, Xetra TES | not needed |

Processed files in `data/`: `daily_features.parquet` (174 stocks × 213 days, 76 cols), `universe.csv`,
`events.parquet`, `intraday_bars.parquet` (all 44 stocks in `events.csv`: heroes + DAX 40; 3.8M 1-min bars, ~170 MB; read one stock with `engine.data.intraday(isin)`, never the whole file in app code), `hero_candidates.csv`.
Rebuild: `ingest/build_daily.py <raw> data` (~25 s), `ingest/build_events.py`, `ingest/build_intraday.py` (no arguments = every stock in `events.csv`, ~160 s; add `--rebuild` when the ticker list is unchanged but the code changed).

### Pitfalls (all handled in ingest; keep them in mind for new code)
- **Flows:**
  - `DATE` is the publication date, so use `REPORTED_FLOW_DATES`.
  - Fewer than 7 executions means the day is censored (empty, released later and summed with other days).
  - Delayed-release rows duplicate `(DATE, SECURITY_ID)`.
  - `VOLUME` is two-sided, so use the one-sided BUY/SELL columns.
- **Peers:** `peer_ret` is the equal-weighted **mean** return of the other index members (not a median). Index peer groups and ranks use the current members only (`engine.compare.current_members()`: DAX 40, MDAX 50, SDAX 70), not every share that was ever a member.
- **OHLC:**
  - Open/high/low/close are mid quotes. Returns use `CLOSE_AUCTION_PRICE` (fallback: last mid).
  - Ignore `ADJUSTED_PRICE` (deprecated and wrong).
  - Use EUR lines only.
- **Trades:**
  - Timestamps are UTC; convert to Europe/Berlin (watch DST).
  - Empty `SIDE` means an auction trade. Otherwise 1 = aggressive buy, 2 = aggressive sell.
  - Trading runs 08:00–22:00 local.
- **Index lists:** if a day's file is missing, use the previous day. TKCC (thyssenkrupp spin-off) was an MDAX member for one day only (28 Oct).
- **XLM exists only while a stock is an index member.** `universe.csv` has `member_now` and `last_member_date`.

### Validations already done (good for jury Q&A)
- Flow one-sided total / OHLC turnover = **1.000** (median over all stock-days).
- Sum of 1-min bars / daily turnover = **1.000** for every one of the 44 stocks (46 ISINs).
- Opening + closing auction volume from the trade file = 97.6–99.7 % of flow auction turnover (median per hero stock); the rest is midday auction and volatility interruptions.
- Onset vs announcement time: for all 7 events announced during trading hours (6 hero + Beiersdorf), the detected onset comes after the announcement (lag 2–117 min). Over the 39 sourced events with a release time and a detected onset (44 stocks; 63 events have a release time), the timing inferred from the onset matches the release time in 33 (85 %).
- Auction share is real: EVD on 27 Oct had **83 %** of turnover in the closing auction (raw trades and flows agree).
  60-day medians: DAX 51 %, MDAX 52 %, SDAX 34 %.

## Findings for the demo and pitch

Hero stocks (max 3 per challenge, set in `config.HERO_TICKERS`; the team may still change them):
- **EVD CTS Eventim (MDAX), main demo flow.** Trigger (sourced): FY 2025 results and 2026 targets on 26 Mar at 17:45, after the close; dpa-AFX blamed disappointing targets and the dividend cut (€1.66 → €1.44). On 27 Mar: −23.2 % (peers −1.5 %, abnormal −21.7 %), 8.6× normal turnover, agent orders net selling (−36 %). The opening auction (09:02) was only −2.3 %, but the market started pricing the news at **09:03** (onset detector): −15 % by 09:18, i.e. 65 % of the day's move within 15 minutes, with volatility interruptions at 09:07 and 09:12. The low came at 16:44. The closing auction (17:35) traded **€25.6m** (3.6× normal) and set the price 1.5 % below the last trade (normal ±0.2 %); the opening auction was 9.6× normal.
- **EVT Evotec (SDAX).** Trigger (sourced): ad hoc guidance cut on 13 Jul at 21:17. On 14 Jul: −24 %, a −22 % gap at the open (news before the open). 19 % of turnover traded in the first 15 minutes; the low came at 09:18.
- **HDD Heidelberger Druck (SDAX).** A small cap (~€1.3m/day, XLM ~90 bps, close to the Designated Sponsor thresholds) with several strong days. This is the liquidity story. Sourced triggers: Q3 results 5 Feb 07:30 (−14 %), drone-defense JV ad hoc 18 Mar 14:15 (+9 %), dpa-AFX drone-defense report 14 Apr 06:10 (+19 %), guidance cut 15 Apr 17:59 (−11 % next day), **guidance cut ad hoc 29 Oct at 12:00:53 → onset detector says 12:02**.
- **GXI Gerresheimer, a pitch story only.** Trigger (sourced): ad hoc on 10 Feb at 22:28 (results postponed over an accounting investigation, guidance cut, impairments). On 11 Feb: −31.4 % (peers −0.9 %), 20× turnover, 20 % of turnover in the first 15 minutes, low at 09:22. It **left the SDAX on 9 Apr**, so there is no XLM data after that. This gives the "index early-warning" idea.
- The **reasons** for these moves are NOT in the trading data. They come from `events/events.csv` (80 sourced events, researched 11 Nov). Quote only what the linked source says; never invent causes. Not found (no company news): EVD 27 Feb, 5 Mar, 30 Mar; EVT 3 Feb, 14 Apr (analyst comments), 12 Oct. EVD 31 Aug (19× turnover) = MSCI Germany deletion effective at the close.

Xetra liquidity rule (Being Public Guide p. 32): XLM (EUR 25k) ≤ 100 bps **and** ≥ EUR 2.5m/day (4-month average) means category A; otherwise a Designated Sponsor is needed. `engine.baseline.kpis()` gives an estimate.

## Status (Thu morning, all PRs up to #50 merged, 205 tests green on `fix/oguzhan-full-read`)

Done on `main`:
- **Ingest:** daily (174 stocks x 213 days), events (80 sourced events), intraday (44 event stocks, 3.8M bars).
- **Engine:**
  - `baseline`: KPIs, anomalies with market context, liquidity trend, episodes.
  - `impact`: card incl. auctions vs normal; `onset`: news onset; `auctions`: exact uncross volumes.
  - `compare`: same-type percentiles, summary sentence, one rank text "rank 3 of 215 (incl. this day)" (#38).
  - **One peer benchmark** (#37): `compare.peer_medians()` feeds the web, Streamlit, the Part A report and the
    assistant. Size = the 10 stocks closest in turnover. A test checks that web and `kpis()` agree.
  - `xlm`: trading cost by order size.
- **AI** (JAIF, `hIP_1.0-Mistral/Mistral-Medium-3.5-128B`):
  - Card summary DE/EN with **numbers check** (`ai/checks.py`) and **meaning check** (#38: "the share fell X %"
    must use the share's own move, not the abnormal return). German short dates and English thousands in event
    titles are understood (#40). A failed check shows the template text.
  - **IR analyst dock** on every web page (#36, Alper): the model calls engine functions as tools (find_company,
    company_overview, peer_benchmark, trading_cost_curve, unusual_days, event_calendar, impact_card,
    compare_events, show) and answers from their outputs; without a key a deterministic router answers.
- **Caches warmed** on the code of #40 (#41 changed no prompt or card): 58 card summaries for EVD, EVT, HDD
  (56 from the model, 2 templates: EVT 10 Mar and 6 May EN, where the check caught a number) and 36 assistant
  answers (0 flagged). EVD 27 Mar EN/DE are served from the cache without network.
  **After ANY prompt, card or engine change run `python web/warm_cache.py`** (~4 min).
- **Web (`web/`) = demo UI:** ISIN entry, dashboard (trading over time, peers, liquidity trend, cost by order
  size, unusual days with calendar and market context), impact card, compare, report, ideas, IR analyst dock.
  Own calendar (brief VI): add an event or import CSV/ICS on the card page (`/api/calendar`, #36).
  **One-click PDF** (#41): *Export IR report (PDF)* on every card (snapshot + checked summary) and on the
  dashboard (Part A), DE/EN.
- **Streamlit (`app/`) = backup and analyst view.** Deleted by a direct push to main (2bd0c3c), restored in #39.
- **Docs:** `docs/SUBMISSION.md` (submission text), `docs/PITCH.md` (relevance lines, scorecard map, Q&A),
  `docs/REQUIREMENTS.md` (brief item -> page), `docs/C2_ENGINE.md`.

Since #41 (Thu morning):
- **Engine:** `market` (dashboard in one call: share vs index, ranks, event list), `evidence` (evidence brief and
  explanation check, neutral wording, no leak or insider claims). Liquidity category as the guide defines it
  (daily average of four months; `None` without XLM, e.g. Gerresheimer). Index peers = current members only.
- **AI:** the assistant runs the numbers check and the meaning check; a failed answer is replaced by the
  deterministic one. Deterministic answers work for shares without XLM and ignore impossible dates.
- **Web:** `web/app.js`, `web/app.css` and `web/index.html` belong to **Alper**. Do not change them; report
  findings to him. A card opened without an event id is linked to the calendar event of that reaction day
  (`web/server.card_event`).
- **Reports:** the episode table (Part A report, Streamlit) shows the card's turnover ratio
  (`baseline.episode_card_ratio`).

Open:
1. ~~Assistant policy~~ ✅ Decided: a dock answer with a figure that is not in the tool outputs is replaced by the
   deterministic answer, the same rule as the card summary (`ai/agent._checked`).
2. **Thu morning:** demo dry run on the web UI; backup video at 12:00 on the web UI; Streamlit open as the
   live fallback. Run the demo from Oğuzhan's laptop (key and caches are local). Open the page early (first
   load 8-10 s). Do not press "Regenerate" in the demo (it asks the model again).
3. **Human check:** spot-check the hero rows in `events.csv` (source link, time) before the pitch.
4. **Deliverables:** 13:30 submission (`docs/SUBMISSION.md` + link or video), 14:30 deck (3-5 slides, `docs/PITCH.md`).
5. Optional, cosmetic: the DE model text writes dates as "27. 03. 2026" (a prompt change means a re-warm).

Decided: Eurex open interest is skipped (participant split censored for >90 % of small-cap series), and Xetra TES is a "what's next" idea.

Team rule: nothing goes to `main` without a PR (a direct push deleted the Streamlit app on Wed night).

Housekeeping: the empty repo `Bthn28/issuer-intelligence-hub` can be deleted, and merged branches can be removed.
