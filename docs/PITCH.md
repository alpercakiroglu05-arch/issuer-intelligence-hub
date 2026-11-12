# Pitch (target: fit the official time limit with 20 seconds to spare)

| Part | Time | Content |
| --- | --- | --- |
| Hook + problem | 30 s | 27 March: CTS Eventim falls 23 %. The CFO asks IR: *was it us or the market, and when did it start?* Today the answer takes days and a paid broker report. Most MDAX/SDAX IR teams have no terminal and no analyst. |
| Solution | 15 s | **Issuer Intelligence Hub**: one click from any announcement to an impact card. Deutsche Börse's own Xetra data, explained in plain German or English. |
| Live demo | 90–120 s | **Web front end** (`python web/server.py`, http://127.0.0.1:8600); the click path is in *Demo path* below. CTS Eventim: overview → 27 Mar impact card (−21.7 % vs peers, priced from 09:03, closing auction €25.6m, #3 of 215 unusual MDAX days) → summary EN → DE → Zalando: #1 of 36 DAX half-year results → report → PDF. **Backup:** the Streamlit app (`streamlit run app/Home.py`) and the recorded video. |
| How it works | 30 s | OHLC + Flow Dynamics (who traded) + XLM (trading cost) + every single Xetra trade → deterministic engine → the LLM only writes from the computed JSON, so no number is invented. |
| Impact + business | 30 s | 160 DAX/MDAX/SDAX issuers today and 400+ listed in Frankfurt. Fits into the free Issuer Services Hub as "Stock Report 2.0": from monthly PDF to on demand and event-driven. It makes listing in Frankfurt more valuable (listing = structural growth driver on DB's own slide). |
| Team + next step | 15 s | Pilot with 3 SDAX IR teams via the Issuer Services Hub. Next modules: index early warning, Designated Sponsor monitor. |

## Demo path (the UI on `main`, checked click by click on 12 Nov)

Showcase: one share per index (`config.HERO_TICKERS`): Zalando (DAX), CTS Eventim (MDAX), Heidelberger Druck (SDAX).

| # | Click | What to say (every figure is on the screen) |
|---|---|---|
| 1 | **Shares** (top right), type `eventim`, Enter | "An IR manager types the company name. No terminal, no analyst." |
| 2 | **Overview** | Year to date −16.6 % against −4.2 % for the MDAX peers; €13.1m turnover a day; a €25k order costs 20.3 bps; liquidity category A, no Designated Sponsor needed. Peers by index, sector and size. |
| 3 | *Unusual days* → **27 Mar** (or *Open impact card*) | "Full-year results, published 26 Mar at 17:45, after the close. The date and time are checked against the source." |
| 4 | Impact card, **At a glance** | −23.2 % on the day, MDAX peers −1.5 %, so −21.7 % was stock-specific. Closing auction €25.6m, 3.6× normal. #3 of 215 unusual MDAX days. |
| 5 | The summary under the big figure, then **DE** (top right) | "Written by the model from the card. Every figure is checked against the card; a text that fails is replaced by a template." It shows "All 15 figures match the card" and "Saved answer". |
| 6 | **The day** | "The opening auction was only −2.3 %. The market started pricing the news at 09:03." The low came at 16:44. |
| 7 | **Evidence** | "It was the overall market": contradicted. "Funds or short sellers sold": not testable with exchange data, and the card says so. |
| 8 | **Shares**, type `zalando`, Enter → *Open impact card* (4 Aug) | "Same-type comparison, as the brief asks: half-year results, published 07:00. −13.6 % stock-specific on 6.0× turnover, reaction at 09:02: the biggest of 36 DAX half-year results." Skip this step if time is short. |
| 9 | **Report** → *Save as PDF* (or *Export IR report (PDF)* on the Eventim card) | "One page for the board, in English or German." |

Rules for the live demo:

- **Use the suggested questions** in the analyst panel (**Ask**): they are saved answers and appear at once. A typed question goes to the model and takes about 30 seconds.
- **Do not press *Ask the model again*** on a card: it calls the model live.
- On the Eventim card, the suggested question *How does this rank against similar events?* says "8.5x" while the card says "8.6×" (the ratio is 8.545; the card rounds 8.55 up). Use the other two questions.
- Zalando: the web card shows the opening auction as 15.9×, the PDF as 15.8× (the ratio is 15.85). Export the PDF from the Eventim card.
- Heidelberger Druck is the liquidity story if a juror asks about small caps: category B, a Designated Sponsor is needed (4-month daily average 86 bps, €788k a day).
- The linked release for 27 Mar gives no prior-year dividend and no reason for the fall. Say "full-year results and outlook", not "dividend cut" or "disappointing targets".

## Relevance: lines that tie the tool to Deutsche Börse (from the Being Public Guide, Oct 2026)

- **"Stock Report 2.0."** DB already sends issuers a monthly *Stock Report* (guide p. 16): turnover by venue, a peer group, index comparison and XLM by order size. We make it on demand and event-driven, and our "trading cost by order size" chart is the live version of its XLM table.
- **A module for the Issuer Services Hub, not a competitor.** The Hub already has a price chart, KPI comparison and calendar notifications (guide p. 18). We add what it lacks: the impact of each announcement, auctions, who traded, the minute the news was priced, and an explanation in plain DE/EN.
- **"The event data is already yours."** Listed companies must send DB their *Corporate Calendar* via ERS (guide pp. 4–5). We researched 82 events by hand for the demo; in production they come straight from ERS.
- **Liquidity and Designated Sponsors.** XLM ≤ 100 bps and ≥ €2.5m a day decide whether a company needs a Designated Sponsor (guide p. 32). The dashboard estimates the category and shows what a large order really costs. Example: in Heidelberger Druck a €500k round trip (XLM) costs 13.8 % against 4.7 % for the median SDAX stock, and the book absorbs nothing larger on most days.

## Jury scorecard: what we show for each criterion

| Criterion (scorecard question) | Our answer in the pitch |
|---|---|
| **Idea**: different approach? | Event-driven, not a static dashboard. **When** did the market price the news (onset minute)? **Was it us or the market?** (peer-adjusted move plus market context: index days, expiries). **How big was it?** (rank among events of the same type). |
| **Execution**: "more than a good-looking dashboard?" | Built on every single Xetra trade (3.8M one-minute bars), with validations we can show: flow totals = turnover **1.000**; bars = turnover **1.000** for all 44 stocks; auctions from trades = **97.6–99.7 %** of flow auction turnover; Heidelberger Druck ad hoc at 12:00:53 → onset detected **12:02**; 225 automated tests. |
| **Relevance**: solves the challenge, no gimmicks? | All brief points I–VIII are in the app (see `docs/SUBMISSION.md`). Only DB's own data plus public announcements. It builds on what DB already has: the Stock Report, the Issuer Services Hub and the ERS corporate calendar. |
| **Pitch**: problem, idea, value, USP clear? | One flow end to end, driven by the CFO's question. USP in one line: *from announcement to an explained impact card in one click, on Deutsche Börse's own trade data.* Backup video ready. |

## Demo checklist

- [ ] Demo laptop (Oğuzhan's: the key and the caches are local): `git pull`, `python ingest/build_events.py`, `pytest` green, `python web/warm_cache.py` after the last merge that touches a prompt, a card or the engine (about 11 minutes), then `python web/server.py`. Open the page early (the first load takes 8–10 s) and walk the demo path once
- [ ] Backup screen recording of the **web** demo path ready by 12 Nov 12:00 (demo submission 13:30); Streamlit (`streamlit run app/Home.py`) open in a second tab as the live fallback
- [ ] One person talks, one person clicks
- [ ] Browser zoom up, notifications off, other tabs closed

## Q&A: one-sentence answers

- **Hallucinations?** Every number is computed in code, and the model sees only that JSON. A numbers check then compares every figure in the model's text with the JSON, and a meaning check makes sure "the share fell X %" is the share's own move; if either fails, the model's text is thrown away and a template is shown. The analyst panel follows the same rule. The card says which of the two you are reading. The model is an open model on European infrastructure (JAIF), and it can be swapped in one line.
- **Which data?** Only Deutsche Börse exchange data plus public corporate calendars. No personal data.
- **Is this investment advice / MAR?** No. It explains past trading, never predicts or recommends.
- **Who buys it, what does it cost?** DB offers it in the Issuer Services Hub (free for Prime/General Standard, Scale); premium tier for deeper analytics.
- **What exists already, and why is this better?** The monthly Stock Report (PDF/Excel) and terminals. One lags, the other needs licences and analysts. We are on demand, event-driven and explained.
- **Where do the reasons come from?** Never from the model. Each event in `events.csv` has a source link, which is shown on the card and in the PDF. For the showcase shares we re-checked every date and time against its link on 12 Nov, and the titles say only what the linked page says. Days without company news say so, and the market-context column shows index days and expiries.
- **How do you know the onset minute is right?** For all 7 releases published during trading hours, the detected onset comes after the release (e.g. 12:00:53 → 12:02). Of the 63 events with a published time, 39 show a clear onset; for 33 of those 39 the timing inferred from trading matches the release time.
- **Can a company add its own calendar (brief VI)?** The demo shows the researched calendar (82 events). The API already matches a company's own dates to trading days (`POST /api/calendar`); in production the dates come from the ERS corporate calendar, so nobody types them twice.
- **The card says 8.6×, but €113.6m / €13.3m is 8.5?** The ratio is 8.545; the card stores 8.55 and shows one decimal. It is rounding, and the euro amounts beside it are exact.
- **Why not market cap for "size"?** It is not in the data excerpt. We use the 10 stocks closest in turnover as a size proxy and say so on screen.
