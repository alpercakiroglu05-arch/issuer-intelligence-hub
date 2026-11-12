# Issuer Intelligence Hub: data, model and logic

**Deutsche Börse challenge, Futury Build Days #4 (Frankfurt, 11–12 Nov 2026)**

The Issuer Intelligence Hub is a self-service tool for the IR team of an MDAX/SDAX company, which typically has no terminal and no analyst.
- **Part A** shows how the company's share normally trades.
- **Part B** turns any announcement or unusual day into an **impact card**: what happened to price, turnover, trading cost, auctions and participants compared with normal, when the market started pricing the news, and how the event ranks against comparable events.
- One click exports the card as a DE/EN IR snapshot.

All numbers come from Deutsche Börse exchange data and deterministic code. The language model only writes text from the computed numbers.

---

## 1. Data

All data is the Deutsche Börse excerpt for **2 Jan – 30 Oct 2026 (213 trading days)**, plus public announcements.

| Dataset | What we use it for |
|---|---|
| **Xetra OHLC** (daily) | Closing-auction price (our official daily price), opening-auction price and time, closing-auction time, daily turnover |
| **Xetra Flow Dynamics** | Who traded: agent (client), proprietary and market maker × aggressive / passive / auction × buy / sell, in EUR |
| **XLM spreads** (`dax_mdax_sdax_liquid_spreads`) | Trading cost (Xetra Liquidity Measure, `Impact_bps`) for order sizes from EUR 10k to 30m; we headline EUR 25k |
| **Index constituents** | Daily DAX (40) / MDAX (50) / SDAX (70) membership, used as the peer group of each day |
| **Xetra on-book trades** (1.7 GB, every trade, ns timestamps) | 1-minute bars for the 44 stocks with events (46 ISINs: Fresenius and Qiagen changed ISIN): **3.8 million bars**, used for intraday price path, news onset and exact auction volumes |
| **Public sources** (`events/events.csv`) | **80 corporate events**, each with a source link, and the release time when the source shows it |

**Events.** We cover every 2026 event of the four focus stocks: CTS Eventim (EVD, MDAX), Evotec (EVT, SDAX), Heidelberger Druck (HDD, SDAX), and Gerresheimer (GXI) as a pitch story. We also cover the first H1/Q3 publication of **all 40 DAX members**. Two rules apply:
- A results event is the first moment the figures became public. If a company pre-released by ad hoc, that ad hoc is the event.
- Times come from the EQS/DGAP release header. Unknown times stay empty and are never guessed.

**Not used, and why:**
- **Eurex open interest:** single-stock options exist for our focus stocks, but the participant split (agent/prop/MM, long/short) is censored for more than 90 % of their series (sample day 25 Mar: EVD has participant data for 2 of 75 series, HDD for 1 of 38). It cannot show small-cap positioning.
- **Eurex settlement prices, other Eurex data and ETP flows:** these cover derivatives and ETFs, not the issuer's share on Xetra.
- **Xetra TES (off-book):** in the excerpt, but it holds only 4 trades in our 174 index stocks (SAP, EUR 559 in total); the rest are ETF request-for-quote trades. It cannot show block trades in these shares.

**Data pitfalls handled in the ingest:**
- **Flows:**
  - `DATE` is the publication date, so we use the reported trading date.
  - Days with fewer than 7 executions are censored (flagged on the card).
  - Delayed releases duplicate rows, which we de-duplicate.
  - Volume is two-sided, so we use the one-sided buy/sell columns.
- **OHLC:** prices are quoted mids, so returns use the closing-auction price. The deprecated `ADJUSTED_PRICE` is ignored. Only EUR lines are used.
- **Trades:**
  - Timestamps are converted from UTC to Frankfurt time (DST aware).
  - An empty `SIDE` marks an auction trade.
  - Two stocks changed ISIN in 2026 (Fresenius, Qiagen); we merge both ISINs.
- **XLM** exists only while a stock is an index member (Gerresheimer after it left the SDAX on 9 Apr).

## 2. Model and logic

Design rule: **numbers come from code, words come from the LLM.** The engine is deterministic. The AI layer only sees the impact card's JSON. Without an LLM key every text falls back to a template, so the demo cannot break.

```
raw Deutsche Börse files ──ingest (DuckDB, pandas)──▶ parquet ──engine (deterministic)──▶ impact_card JSON ──▶ app · IR snapshot (HTML/PDF) · AI text
```

### Part A: the normal state
- **Headline numbers** are 60-day medians of turnover, XLM (EUR 25k), auction share and agent share, each against the median stock of the same index.
- **Xetra liquidity category (estimate):** category A if XLM (EUR 25k) ≤ 100 bps and order book turnover ≥ EUR 2.5m a day, both as the daily average of the last four months (Being Public Guide, p. 32). Otherwise category B, which needs a Designated Sponsor for continuous trading. A share without XLM (not a DAX, MDAX or SDAX member in that window) gets no category.
- **Unusual days:** volume z ≥ 3, |abnormal return z| ≥ 3, or XLM ≥ 2× normal. Possible corporate actions (|return| > 40 %) are excluded. Consecutive unusual days are merged into one episode.
- **Trading cost by order size:** XLM from €10k to €10m against the peer median, plus the largest order the Xetra book absorbed on most of the last 60 days. This is the live version of the XLM table in Deutsche Börse's monthly Stock Report.
- **Liquidity trend** ("has our liquidity improved?"): the last 60 trading days against the 60 before, for the stock and for its index, with a ±10 % tolerance.

### Part B: the impact card
- **Reaction day:** a release after the closing auction (17:35) or on a non-trading day counts on the next trading day.
- **Baseline:** trading days t-65 … t-6, i.e. 60 days, skipping the 5 days before the event so a pre-event run-up does not pollute "normal".
- **Price:**
  - Abnormal return = stock return − equal-weighted return of the other members of its index that day.
  - z-score against the baseline.
  - Abnormal return summed over t0 … t+5.
  - Gap at the open (opening auction vs previous close) and move during the session.
- **Volume:** turnover / baseline median, and a z-score on log turnover.
- **Trading cost:** XLM (EUR 25k) against the baseline median, and the number of days until it is back within 1.2× normal.
- **Opening and closing auction:**
  - Volume against the baseline median, measured at the exact uncross minute (from the OHLC auction timestamps), so pre-market, volatility-interruption and after-close trades are not counted.
  - Price formation: opening auction vs previous close, and closing auction vs the last continuous trade before 17:30, each with its normal range.
- **Who traded:** agent (client) share of turnover and the aggressive agent order imbalance ((buy − sell) / (buy + sell)) against normal.
- **News onset**, "the market started pricing the news at HH:MM": the first minute from 08:00 where *both* of these hold:
  - the price is ≥ 2σ (daily return std of the baseline) away from the previous close;
  - cumulative turnover is ≥ 3× normal for that clock time (and ≥ 1 % of a normal day).

  The break must go in the direction of the day's move and still hold 5 minutes later. A break before 09:15 means the news was out before the open. If the release time is unknown, the card fills the timing from this and labels it "inferred from trading". The onset also lists volatility interruptions (unscheduled auctions).
- **Comparison with events of the same type** (the brief's "all earnings releases in the DAX"):
  - The card's metrics are computed with identical definitions for every stock-day (36,060 rows).
  - The event is ranked within its group: same type in the same index if there are ≥ 5 other events, else all indices, else all automatically detected unusual days (871 in 2026).
  - Shown as percentiles of stock-specific move, turnover and trading cost against normal, plus the rank.

### AI and export
- **Summary text (DE/EN):** the model gets only the card JSON and is told to use only its numbers, never invent causes, and give no advice. A **numbers check** (`ai/checks.py`) then compares every figure in the text with the JSON, allowing for percent, EUR m and rounding. Any unknown figure means the template text is shown instead, and the card says which one it is. Model: an open model through the JAIF gateway (OpenAI-compatible), swappable in `.env`. Answers are cached so the live demo does not depend on the network.
- **IR analyst (dock on every page):** the model calls engine functions as tools (company overview, peer benchmark, trading cost curve, unusual days, event calendar, impact card, comparison) and answers from their outputs only. Every number in the answer is checked against the tool outputs; an answer with a figure that cannot be traced is replaced by the deterministic answer, the same rule as the card summary. Without a model key a deterministic router answers from the same tools.
- **Meaning check:** a sentence like "the share fell X %" must use the share's own move, not the stock-specific (abnormal) move; otherwise the template is shown. The numbers check alone cannot catch this mix-up, because both numbers are in the card.
- **IR snapshot:** one click on the card (*Export IR report (PDF)*) gives the card plus its checked summary as a PDF, in DE or EN; the same button on the dashboard gives the Part A report (key figures vs peers, liquidity trend, cost by order size, unusual days).

## 3. Validation (all reproducible, 175 automated tests)

| Check | Result |
|---|---|
| One-sided flow total vs Xetra turnover | **1.000** (median over all stock-days) |
| Sum of 1-minute bars vs daily turnover | **1.000** for every one of the 44 stocks |
| Opening + closing auction from single trades vs flow auction turnover | **97.6–99.7 %** per stock (the rest is the midday auction and volatility interruptions) |
| News onset on clearly unusual days (focus stocks) | found on **17 of 19** days with \|abnormal z\| ≥ 3 |
| Inferred timing vs published release time | consistent for **33 of 39** sourced events with a time (85 %) |
| Releases during trading hours | onset after the release in **7 of 7**. Heidelberger Druck, 29 Oct: ad hoc at 12:00:53, onset **12:02** |
| Card vs comparison table | identical metrics (tested) |
| Event days vs normal | median turnover on guidance changes 7.7×, ad hocs 4.6×, H1 results 1.8×, AGMs 0.65× |

**Example, CTS Eventim, 27 Mar 2026.**
- **Trigger:** FY 2025 results and 2026 targets on 26 Mar at 17:45, after the closing auction.
- **Price:** −23.2 % against peers −1.5 %, so −21.7 % stock-specific.
- **Activity:** 8.6× normal turnover, with agent orders net selling.
- **Timing:** the opening auction was only −2.3 %, but the market started pricing at **09:03** and was −15 % by 09:18.
- **Auctions:** the closing auction traded EUR 25.6m (3.6× normal) and set the price 1.5 % below the last trade (normally ±0.2 %).
- **Rank:** the third-largest stock-specific move among 215 unusual MDAX days in 2026.

## 4. Limitations

- **Causes:** the data shows *what* happened, not *why*. Reasons come only from the linked public sources. Some unusual days have no company news, and we say so.
- **Intraday peers:** the onset uses the raw price move because there are no intraday peer prices. A market-wide move can also trigger it.
- **Event times:** the 80 events were researched with AI-assisted web search, and every row has its source link. 17 have no published time, and 7 DAX times are pre-announced dpa-AFX slots (marked in the title).
- **Peer groups:** the dashboard engine compares a stock with three groups: its index, its sector, and the stocks of similar size.
  - **Sector:** 11 groups built from Deutsche Börse's official Prime Standard sectors (`events/sectors.csv`, 173 of 174 stocks; the last one falls back to the index).
  - **Similar size:** the 10 stocks closest in median turnover over the last 60 days (a size proxy).
  - Every screen, the report and the assistant use one peer benchmark (median over the peers of each peer's 60-day median).
  - Market capitalisation is not in the data, so the size groups are turnover-based, not market-cap-based.
  - The impact card's abnormal return still uses index peers.
- **AI text:** the numbers check catches invented figures with decimals or large values; a small integer could match an unrelated value by chance. The meaning check covers only the share's own move. Without a model key the texts come from templates.

## 5. What else IR teams need, and which data

| Idea | Value for IR | Data needed |
|---|---|---|
| Index early warning | See an index exit coming (Gerresheimer left the SDAX on 9 Apr) | Index rules, free-float market cap, ranking lists |
| Designated Sponsor monitor | Does our DS deliver the quote quality we pay for? | DS identity, quote and spread data per DS |
| Block trades and placements | How much traded off the order book around an event | Off-exchange and block trade reports (the Xetra TES excerpt has only 4 small trades in index stocks) |
| Surprise vs consensus | Separate "the figures" from "the expectations" | Analyst consensus estimates |
| Shareholder identification | Who sold after the results? | Share register, custody data |
| Derivatives positioning | Hedging and short build-up before events | Eurex open interest (usable for large caps; censored for most small-cap series) |

## 6. How to run

```bash
pip install -r requirements.txt
python ingest/build_daily.py <raw> data        # ~25 s
python ingest/build_events.py
python ingest/build_intraday.py                # ~3 min, every stock in events.csv
python web/server.py                           # demo UI: http://127.0.0.1:8600
streamlit run app/Home.py                      # backup UI: http://localhost:8501
pytest                                         # 175 tests
```
