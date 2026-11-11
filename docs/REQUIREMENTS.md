# What the challenge asks for, and where each item lives on the site

Source: *Issuer Intelligence Hub and corporate event impact tracker*, Deutsche Börse, Futury Build Days 2026 (14-page brief; the task is on pages 9–12).
Rule for the web app (`web/`): **every requirement has exactly one home**. Other screens may link to it, but they never repeat it.

## 1. The problem (p. 9)

- Mid and small caps cannot easily see how their own shares trade. Terminals and analysts are expensive, and broker reports lag.
- IR teams have to explain price moves, liquidity and the trading profile, both internally and externally.
- Basic questions take days or go unanswered:
  - *"Has liquidity improved?"*
  - *"How do our spreads compare with peers?"*
  - *"Did trading change after results?"*

So the user is an IR person **without a terminal**. They enter their company and get answers in minutes.

## 2. Requirements, one by one

| # | Requirement (brief wording, shortened) | Page | Home in `web/` | Engine source |
|---|---|---|---|---|
| A1 | **Part A dashboard:** how the share trades day to day | p. 10 | **Dashboard** tab | `baseline.profile`, `baseline.kpis` |
| I | Trading volume, bid-ask spreads and auction participation over time | p. 11 | Dashboard → "Volume, spread and auctions over time" (one chart with three switchable series vs. the index median) | `profile`, `index_benchmark` |
| II | Peer benchmarking (sector, index, market-cap cohort) | p. 10/11 | Dashboard → "Peers" table (index median, sector peers, size cohort) | `daily()` grouped by index, sector and turnover cohort |
| III | Flag anomalies (volume spikes, spread widening) | p. 10/11 | Dashboard → "Unusual days" list. Each row has a **one-click "Create impact card"** | `baseline.anomaly_episodes`, `anomalies` |
| — | "Has liquidity improved?" (problem statement) | p. 9 | Dashboard → liquidity verdict sentence + Xetra liquidity category check | `baseline.liquidity_trend`, `kpis` |
| B1 | **Part B impact card:** link announcements (results, dividends, press releases, ad hoc) to trading data | p. 10 | **Impact card** tab | `impact.impact_card` |
| V | Visual impact card: volume vs. baseline, spread movement, price formation in the opening/closing auctions | p. 10/11 | Impact card → card body: volume gauge, spread gauge, opening and closing auction blocks, intraday chart | `card.volume`, `card.liquidity`, `card.auctions`, `card.intraday` |
| VI | Ingest a corporate event calendar and match events to intraday data | p. 11/12 | Impact card → event list (from `events/events.csv`, with type, time, source and verified flag) + "market started pricing at HH:MM" on the chart | `data.events`, `onset.onset`, `intraday_bars` |
| VII | Compare events of the same type (e.g. all DAX results in the past year) | p. 10/11 | **Compare** tab (type + index filters, table, scatter; the open card is highlighted) | `compare.same_type_events`, `card.comparison` |
| IV | Package insights into a shareable "IR snapshot" report | p. 11 | **Report** tab (one place for every export) | `report.export.to_html` / `to_pdf` |
| VIII | Exportable summary for IR teams | p. 10/11 | Report tab: choose Part A summary and/or impact card, DE/EN, PDF | same |
| AI | Easy-to-use **AI assistant**: generate an impact card for an event or notable day with one click, plus an exportable short report | p. 10 | **AI summary** box inside the impact card (one click) + **Assistant** tab (questions in plain language) | `ai.narrate.narrate`, `ai.agent.ask` |
| Ideas | What else could be relevant for IR, and which data it needs | p. 10 | **Ideas** tab (have / need data per idea) | — |
| Data | DAX/MDAX/SDAX with ISIN, up to three showcase stocks; OHLC, flows, XLM, open interest; public event calendars | p. 12 | ISIN entry screen (all 174 shares; EVD, EVT and HDD as quick picks), footer data sources | `data.universe` |

## 3. Site structure (no duplicates)

```
ISIN entry (full screen) ── enter ISIN / name / ticker ──►  Company workspace
                                                            ├─ Dashboard      Part A: I, II, III, liquidity verdict
                                                            ├─ Impact card    Part B: B1, V, VI + AI summary
                                                            ├─ Compare        VII
                                                            ├─ Assistant      AI Q&A
                                                            ├─ Report         IV, VIII (all exports)
                                                            └─ Ideas          next ideas + data needed
```

- **One company switcher** (the ISIN chip in the header) replaces the old search button, which only repeated the menu.
- **Exports live only in Report.** The impact card has a "Put in report" link that opens Report with that card selected.
- **The AI writes words, the engine computes numbers.** Without an LLM key the AI box shows the template text and says so.

## 4. Checklist for the demo

- [ ] Enter `DE0005470306` (CTS Eventim) → dashboard loads with real data.
- [ ] Unusual days → 27 Mar → "Create impact card" → card with −23 % / 8.6× / closing auction.
- [ ] AI summary EN → DE.
- [ ] Compare → FY results across indices.
- [ ] Report → PDF.
- [ ] Ideas → GXI index exit story.
