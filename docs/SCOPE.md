# Scope

**Challenge:** Deutsche Börse: *Issuer Intelligence Hub and corporate event impact tracker*
**Problem in one sentence:** Mid- and small-cap IR teams cannot see how their own share trades or how the market reacted to their announcements. They have no terminal and no analyst, and broker reports arrive days later and cost extra.
**User:** Head of Investor Relations at an MDAX/SDAX company. After every announcement, the CFO asks: *"Was it us or the market? Who sold? Did liquidity suffer?"*
**Demo story:** The IR manager of CTS Eventim (MDAX) opens the dashboard and sees the normal state: turnover, trading cost vs the MDAX, and more than half of turnover in the closing auction. They click 27 Mar 2026 (FY results and 2026 targets, released the evening before at 17:45) and get the impact card: −21.7 % vs peers, 8.6× normal turnover, agent orders net selling, the market started pricing the news at 09:03, and the closing auction was 3.6× normal and set the price 1.5 % below the last trade. It is the 3rd-largest stock-specific move of 215 unusual MDAX days in 2026. Then the German summary, then the PDF IR snapshot.

## Must (the demo does not work without it)

- [x] Part A dashboard on real data: turnover, XLM vs index, who trades, unusual days
- [x] Part B impact card in one click, from an event or a notable day
- [x] DE/EN summary (template now, LLM once the key is in `.env`) + HTML/PDF IR snapshot
- [x] `events/events.csv` for the hero stocks, sourced, **with time of day** (80 events incl. the DAX H1 season)
- [x] Intraday chart and news onset for every event stock (`ingest/build_intraday.py`, 44 stocks)
- [ ] LLM connected (JAIF endpoint) with numbers check (C4; until then template texts)

## Should (only after every Must is done)

- [x] Compare events of the same type (all DAX H1 results 2026) with percentile on the card
- [ ] Assistant v2 with tool calling
- [ ] Sector and size peers in addition to index peers (brief point II; proposed: C2)
- [x] ~~Eurex single-stock derivatives positioning~~ checked and skipped: participant split censored for >90 % of small-cap series

## Won't (good ideas, not in these 32 hours: pitch slide "what's next")

- Index membership early warning (Gerresheimer: −31 % on 11 Feb, out of the SDAX on 9 Apr)
- Designated Sponsor performance monitor (quote quality, spread vs. DS rating)
- Pre-announcement unusual-activity monitor for compliance
- Surprise vs. analyst consensus (needs consensus data)
- Shareholder ID / investor targeting (needs register data)

## Open questions for the challenge owner / mentors

- XLM is only delivered for index members (no data for Gerresheimer after it left the SDAX). Is that intended?
- Flows show more than 50 % of DAX/MDAX turnover in auctions (checked against the trade file). Is that the expected picture for 2026?
- Which XLM order size would IR teams care about most: EUR 25k (Xetra liquidity category) or larger?
- Would DB see this as a module of the Issuer Services Hub ("Stock Report 2.0")?
