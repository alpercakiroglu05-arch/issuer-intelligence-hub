# Pitch (target: fit the official time limit with 20 seconds to spare)

| Part | Time | Content |
| --- | --- | --- |
| Hook + problem | 30 s | 27 March: CTS Eventim falls 23 %. The CFO asks IR: *was it us or the market, and who sold?* Today the answer takes days and a paid broker report. Most MDAX/SDAX IR teams have no terminal and no analyst. |
| Solution | 15 s | **Issuer Intelligence Hub**: one click from any announcement to an impact card. Deutsche Börse's own Xetra data, explained in plain German or English. |
| Live demo | 90–120 s | CTS Eventim: dashboard (normal state, "Compare with: Sector/Size", cost of a €1m order) → unusual day 27 Mar (FY results, announced 26 Mar 17:45) → impact card: −21.7 % vs peers, priced from 09:03, closing auction 3.6× normal, #3 of 215 unusual MDAX days → German summary → PDF IR snapshot. |
| How it works | 30 s | OHLC + Flow Dynamics (who traded) + XLM (trading cost) + every single Xetra trade → deterministic engine → the LLM only writes from the computed JSON, so no number is invented. |
| Impact + business | 30 s | 160 DAX/MDAX/SDAX issuers today and 400+ listed in Frankfurt. Fits into the free Issuer Services Hub as "Stock Report 2.0": from monthly PDF to on demand and event-driven. It makes listing in Frankfurt more valuable (listing = structural growth driver on DB's own slide). |
| Team + next step | 15 s | Pilot with 3 SDAX IR teams via the Issuer Services Hub. Next modules: index early warning, Designated Sponsor monitor. |

## Relevance: lines that tie the tool to Deutsche Börse (from the Being Public Guide, Oct 2026)

- **"Stock Report 2.0."** DB already sends issuers a monthly *Stock Report* (guide p. 16): turnover by venue, a peer group, index comparison and XLM by order size. We make it on demand and event-driven, and our "trading cost by order size" chart is the live version of its XLM table.
- **A module for the Issuer Services Hub, not a competitor.** The Hub already has a price chart, KPI comparison and calendar notifications (guide p. 18). We add what it lacks: the impact of each announcement, auctions, who traded, the minute the news was priced, and an explanation in plain DE/EN.
- **"The event data is already yours."** Listed companies must send DB their *Corporate Calendar* via ERS (guide pp. 4–5). We researched 80 events by hand for the demo; in production they come straight from ERS.
- **Liquidity and Designated Sponsors.** XLM ≤ 100 bps and ≥ €2.5m a day decide whether a company needs a Designated Sponsor (guide p. 32). The dashboard estimates the category and shows what a large order really costs. Example: in Heidelberger Druck a €500k round trip (XLM) costs 13.8 % against 4.6 % for the median SDAX stock, and the book absorbs nothing larger on most days.

## Jury scorecard: what we show for each criterion

| Criterion (scorecard question) | Our answer in the pitch |
|---|---|
| **Idea**: different approach? | Event-driven, not a static dashboard. **When** did the market price the news (onset minute)? **Was it us or the market?** (peer-adjusted move plus market context: index days, expiries). **How big was it?** (rank among events of the same type). |
| **Execution**: "more than a good-looking dashboard?" | Built on every single Xetra trade (3.8M one-minute bars), with validations we can show: flow totals = turnover **1.000**; bars = turnover **1.000** for all 44 stocks; auctions from trades = **97.6–99.7 %** of flow auction turnover; Heidelberger Druck ad hoc at 12:00:53 → onset detected **12:02**; 69 automated tests. |
| **Relevance**: solves the challenge, no gimmicks? | All brief points I–VIII are in the app (see `docs/SUBMISSION.md`). Only DB's own data plus public announcements. It builds on what DB already has: the Stock Report, the Issuer Services Hub and the ERS corporate calendar. |
| **Pitch**: problem, idea, value, USP clear? | One flow end to end, driven by the CFO's question. USP in one line: *from announcement to an explained impact card in one click, on Deutsche Börse's own trade data.* Backup video ready. |

## Demo checklist

- [ ] Demo data preloaded, answers cached (`LLM_CACHE=true`, run each scenario once beforehand)
- [ ] Backup screen recording ready by 12 Nov 12:00 (demo submission 13:30) (in `docs/`)
- [ ] One person talks, one person clicks
- [ ] Browser zoom up, notifications off, other tabs closed

## Q&A: one-sentence answers

- **Hallucinations?** Every number is computed in code, and the LLM sees only that JSON. Without a model the same text comes from a template. (An automatic check that rejects any number not in the JSON is planned; only claim it once C4 has merged it.)
- **Which data?** Only Deutsche Börse exchange data plus public corporate calendars. No personal data.
- **Is this investment advice / MAR?** No. It explains past trading, never predicts or recommends.
- **Who buys it, what does it cost?** DB offers it in the Issuer Services Hub (free for Prime/General Standard, Scale); premium tier for deeper analytics.
- **What exists already, and why is this better?** The monthly Stock Report (PDF/Excel) and terminals. One lags, the other needs licences and analysts. We are on demand, event-driven and explained.
- **Where do the reasons come from?** Never from the model. Each event in `events.csv` has a source link, which is shown on the card and in the PDF. Days without company news say so, and the market-context column shows index days and expiries.
- **How do you know the onset minute is right?** For all 7 releases published during trading hours, the detected onset comes after the release (e.g. 12:00:53 → 12:02). For 33 of 39 events with a published time, the timing inferred from trading matches the release time.
- **Why not market cap for "size"?** It is not in the data excerpt. We use turnover terciles as a size proxy and say so on screen.
