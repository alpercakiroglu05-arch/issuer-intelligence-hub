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
streamlit run app/Home.py                 # http://localhost:8501
pytest                                    # 8 tests; data tests skip if data/ is empty
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
`events.parquet`, `intraday_bars.parquet` (EVD, EVT, HDD, GXI; 163k 1-min bars), `hero_candidates.csv`.
Rebuild: `ingest/build_daily.py <raw> data` (~25 s), `ingest/build_events.py`, `ingest/build_intraday.py <tickers>` (~130 s).

### Pitfalls (all handled in ingest; keep them in mind for new code)
- **Flows:**
  - `DATE` is the publication date, so use `REPORTED_FLOW_DATES`.
  - Fewer than 7 executions means the day is censored (empty, released later and summed with other days).
  - Delayed-release rows duplicate `(DATE, SECURITY_ID)`.
  - `VOLUME` is two-sided, so use the one-sided BUY/SELL columns.
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
- Sum of 1-min bars / daily turnover = **1.000** on all 852 stock-days.
- Auction share is real: EVD on 27 Oct had **83 %** of turnover in the closing auction (raw trades and flows agree).
  60-day medians: DAX 51 %, MDAX 52 %, SDAX 34 %.

## Findings for the demo and pitch

Hero stocks (max 3 per challenge, set in `config.HERO_TICKERS`; the team may still change them):
- **EVD CTS Eventim (MDAX), main demo flow.** On 27 Mar: −23.2 % (peers −1.5 %, abnormal −21.7 %), 8.6× normal turnover, agent orders net selling (−36 %). The opening auction (09:02) was only −2.3 %, but the market started pricing the news at **09:03** (onset detector): −15 % by 09:18, i.e. 65 % of the day's move within 15 minutes, with volatility interruptions at 09:07 and 09:12. The low came at 16:44 and **€25.8m** traded in the closing auction.
- **EVT Evotec (SDAX).** On 14 Jul: −24 %, a −22 % gap at the open (news before the open). 19 % of turnover traded in the first 15 minutes; the low came at 09:18.
- **HDD Heidelberger Druck (SDAX).** A small cap (~€1.3m/day, XLM ~90 bps, close to the Designated Sponsor thresholds) with several strong days. This is the liquidity story.
- **GXI Gerresheimer, a pitch story only.** On 11 Feb: −31.4 % (peers −0.9 %), 20× turnover, 20 % of turnover in the first 15 minutes, low at 09:22. It **left the SDAX on 9 Apr**, so there is no XLM data after that. This gives the "index early-warning" idea.
- The **reasons** for these moves are NOT in the data. The research team must verify them; never invent causes.

Xetra liquidity rule (Being Public Guide p. 32): XLM (EUR 25k) ≤ 100 bps **and** ≥ EUR 2.5m/day (4-month average) means category A; otherwise a Designated Sponsor is needed. `engine.baseline.kpis()` gives an estimate.

## Status (end of Wed 15:40)

Done and merged: PR #1 (skeleton) and PR #2 (intraday).
- **Ingest:** daily, events and intraday all ✅.
- **Engine:** `baseline` ✅ and `impact` v1 ✅. Its intraday block is filled.
- **AI:** LLM wrapper (none/openai/azure/anthropic) ✅, template + LLM narrative ✅, assistant v1 ✅.
- **Report:** HTML/PDF ✅.
- **App:** 5 pages ✅, running on real data.

Open (see README checklists):
1. ~~Event timing from data~~ ✅ `engine/onset.py` → `card["intraday"]["onset"]`; fills `event.timing` when the time is unknown. Hits 17 of 19 days with |abn z| ≥ 3. Onsets: EVT/GXI 08:02 pre-market, EVD 09:03, HDD 29 Oct 12:02.
2. `engine/compare.py` (C2): same-type event table + percentiles → `card["comparison"]`. Depends on `events.csv`.
3. LLM: JAIF endpoint/key from the organisers → `.env`. Then a numbers check (every number in the text must exist in the JSON) and an answer cache for the live demo (C4).
4. `events/events.csv`: the research team adds verified events **with time of day**, plus DAX results dates. Today the rows are `TBD` seeds.
5. UI polish of the impact card (the demo moment), the compare page and the intraday chart with an event marker (C3).
6. Optional: sector peers (`events/sectors.csv`), Eurex OI positioning, a Part A PDF.

Housekeeping: the empty repo `Bthn28/issuer-intelligence-hub` can be deleted, and merged branches can be removed.
