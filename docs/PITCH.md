# Pitch (target: fit the official time limit with 20 seconds to spare)

| Part | Time | Content |
| --- | --- | --- |
| Hook + problem | 30 s | 27 March: CTS Eventim falls 23 %. The CFO asks IR: *was it us or the market, and who sold?* Today the answer takes days and a paid broker report. Most MDAX/SDAX IR teams have no terminal and no analyst. |
| Solution | 15 s | **Issuer Intelligence Hub**: one click from any announcement to an impact card. Deutsche Börse's own Xetra data, explained in plain German or English. |
| Live demo | 90–120 s | CTS Eventim: dashboard (normal state) → unusual day 27 Mar → impact card → German summary → PDF IR snapshot. |
| How it works | 30 s | OHLC + Flow Dynamics (who traded) + XLM (trading cost) + every single Xetra trade → deterministic engine → the LLM only writes from the computed JSON, so no number is invented. |
| Impact + business | 30 s | 160 DAX/MDAX/SDAX issuers today and 400+ listed in Frankfurt. Fits into the free Issuer Services Hub as "Stock Report 2.0": from monthly PDF to on demand and event-driven. It makes listing in Frankfurt more valuable (listing = structural growth driver on DB's own slide). |
| Team + next step | 15 s | Pilot with 3 SDAX IR teams via the Issuer Services Hub. Next modules: index early warning, Designated Sponsor monitor. |

## Demo checklist

- [ ] Demo data preloaded, answers cached (`LLM_CACHE=true`, run each scenario once beforehand)
- [ ] Backup screen recording ready by 12 Nov 12:00 (demo submission 13:30) (in `docs/`)
- [ ] One person talks, one person clicks
- [ ] Browser zoom up, notifications off, other tabs closed

## Q&A: one-sentence answers

- **Hallucinations?** Every number is computed in code; the LLM sees only that JSON, and a numbers check rejects any figure not in it.
- **Which data?** Only Deutsche Börse exchange data plus public corporate calendars. No personal data.
- **Is this investment advice / MAR?** No. It explains past trading, never predicts or recommends.
- **Who buys it, what does it cost?** DB offers it in the Issuer Services Hub (free for Prime/General Standard, Scale); premium tier for deeper analytics.
- **What exists already, and why is this better?** The monthly Stock Report (PDF/Excel) and terminals. One lags, the other needs licences and analysts. We are on demand, event-driven and explained.
