# What the challenge asks for, and where each item lives on the site

Source: *Issuer Intelligence Hub and corporate event impact tracker*, Deutsche Börse, Futury Build Days 2026 (14-page brief; the task is on pages 9–12).
Rule for the web app (`web/`): **every requirement has exactly one home**. Other screens may link to it, but they never repeat it.
The brief calls the two halves "Part A" (dashboard) and "Part B" (impact card). The product never shows those labels: an IR user
sees *Dashboard* (trading profile) and *Impact card* (event impact). The IDs below (A1, B1, I–VIII) are only for this mapping.

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
| A1 | **Dashboard (brief: Part A):** how the share trades day to day | p. 10 | **Dashboard** tab | `baseline.profile`, `baseline.kpis` |
| I | Trading volume, bid-ask spreads and auction participation over time | p. 11 | Dashboard → "Volume, spread and auctions over time" (one chart with three switchable series vs. the index median) | `profile`, `index_benchmark` |
| II | Peer benchmarking (sector, index, market-cap cohort) | p. 10/11 | Dashboard → "Peer benchmark" table (index, sector, size) + "Trading cost by order size" vs peers. Size = the 10 shares closest in median turnover, a proxy because market cap is not in the data (said on screen) | `compare.peer_group`, `xlm.cost_curve` |
| III | Flag anomalies (volume spikes, spread widening) | p. 10/11 | Dashboard → "Unusual days" list with the calendar entry or the market context (index change, expiry, market-wide day). Each row opens its impact card in one click | `baseline.anomaly_episodes`, `anomalies`, `market_context` |
| — | "Has liquidity improved?" (problem statement) | p. 9 | Dashboard → liquidity verdict sentence + Xetra liquidity category check | `baseline.liquidity_trend`, `kpis` |
| B1 | **Impact card (brief: Part B):** link announcements (results, dividends, press releases, ad hoc) to trading data | p. 10 | **Impact card** tab | `impact.impact_card` |
| V | Visual impact card: volume vs. baseline, spread movement, price formation in the opening/closing auctions | p. 10/11 | Impact card → card body: volume gauge, spread gauge, opening and closing auction blocks, intraday chart | `card.volume`, `card.liquidity`, `card.auctions`, `card.intraday` |
| VI | Ingest a corporate event calendar and match events to intraday data | p. 11/12 | Impact card → event list (from `events/events.csv`, with type, time, source and verified flag) **+ "Add event" / "Import calendar" (CSV or ICS from Outlook/Google)** for the company's own dates, with a preview of every row (matched / before or after the data / skipped and why) before saving; ICS time zones are converted; the time decides the reaction day. "Reaction detected in trading at HH:MM" on the chart (inferred from trades, not the publication time) | `data.events`, `POST /api/calendar`, `onset.onset`, `intraday_bars` |
| VII | Compare events of the same type (e.g. all DAX results in the past year) | p. 10/11 | **Compare** tab (type + index filters, table, scatter; the open card is highlighted) | `compare.same_type_events`, `card.comparison` |
| IV | Package insights into a shareable "IR snapshot" report | p. 11 | **Export IR report (PDF)** on the dashboard (Part A) and on every impact card (snapshot), one click, DE/EN; **Report** tab for a custom mix | `GET /api/export` → `report.export.part_a_html` / `to_html` + `to_pdf` |
| VIII | Exportable summary for IR teams | p. 10/11 | IR snapshot tab: choose trading profile, peers, liquidity, unusual days and/or impact card, DE/EN, PDF | same |
| AI | Easy-to-use **AI assistant**: generate an impact card for an event or notable day with one click, plus an exportable short report | p. 10 | **IR analyst** dock on every page (agent with tools over the engine; answers with figures, then offers one-click buttons: open card, compare, report) + **AI summary** box inside the impact card | `ai.agent.run`, `ai.narrate.narrate_with_meta`, `ai.checks` |
| + | Evidence, not just numbers (our signature) | — | Impact card → **evidence brief** (what changed, market, trading, how unusual, what the data cannot tell, next step) + **Test an explanation** (supported / contradicted / partly / not testable, with a better wording); in the report and the analyst | `engine.evidence.brief`, `classify` |
| Ideas | What else could be relevant for IR, and which data it needs | p. 10 | **Ideas** tab (have / need data per idea) | — |
| Data | DAX/MDAX/SDAX with ISIN, up to three showcase stocks; OHLC, flows, XLM, open interest; public event calendars | p. 12 | ISIN entry screen (all 174 shares; EVD, EVT and HDD as quick picks), footer data sources | `data.universe` |

## 3. Site structure (no duplicates)

```
ISIN entry (full screen) ── enter ISIN / name / ticker ──►  Company workspace
                                                            ├─ Dashboard      A1, I, II, III, liquidity verdict, cost by order size
                                                            ├─ Impact card    B1, V, VI (+ own calendar) + AI summary
                                                            ├─ Compare        VII
                                                            ├─ IR snapshot    IV, VIII (custom report; one-click PDF on dashboard and card)
                                                            └─ Ideas          next ideas + data needed
                                          IR analyst dock (every page): AI questions; opens the pages above in one click
```

- **One company switcher** (the ISIN chip in the header) replaces the old search button, which only repeated the menu.
- **One click to a PDF, Report for a custom mix.** The dashboard and every impact card have *Export IR report (PDF)*
  (brief: "with one click … including an exportable short report"): the server returns the same PDF as Streamlit
  (`GET /api/export`, `report/export.py`). The card's *Put in report* link still opens Report with that card selected.
- **The AI writes words, the engine computes numbers.** Without an LLM key the AI box shows the template text and says so.
- **The analyst is a dock, not a page**, so it never repeats a page: it answers and hands over to the page that owns the topic.
- **Data date is explicit:** the excerpt ends with the close on 30 Oct 2026. The header says "Xetra data as of the close on 30 October 2026".
  In production the same pipeline would run every evening after the close (T+1).

## 4. Checklist for the demo

- [ ] Enter `DE0005470306` (CTS Eventim) → dashboard loads with real data.
- [ ] Unusual days → 27 Mar → "Create impact card" → card with −23 % / 8.6× / closing auction.
- [ ] AI summary EN → DE.
- [ ] IR analyst (key A): "What were our biggest moves this year?" → button opens the card.
- [ ] Impact card → evidence brief → "The whole market sold off" → Contradicted.
- [ ] Impact card → Import calendar (CSV/ICS) → preview → Add → card in one click.
- [ ] Compare → FY results across indices.
- [ ] Report → PDF.
- [ ] Ideas → GXI index exit story.
