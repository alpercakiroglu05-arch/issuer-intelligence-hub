# Issuer Intelligence Hub

**Decode your share price: Xetra trading insights and event impact cards for investor relations.**
Futury Build Days #4 (Frankfurt, 11–12 November 2026) · Deutsche Börse challenge "Issuer Intelligence Hub and corporate event impact tracker"

The IR team of a DAX, MDAX or SDAX company, above all the smaller ones, has no terminal and no analyst. It cannot
easily see how its own share trades or how the market reacted to an announcement. This tool answers that in one click.

- **Part A, overview: "How does our share normally trade?"** Return against the index peers (1 month, 3 months, year
  to date), turnover, trading cost (XLM, also by order size), auctions, who trades, peers by index, sector and size,
  the Xetra liquidity category, and the unusual days of the year.
- **Part B, impact card: "What happened when we announced X?"** The move against the peers, turnover and trading cost
  against normal, opening and closing auction, who traded, the minute the market started pricing the news, the rank
  among events of the same type, and a checked summary in English or German. One click exports it as a PDF.
- **Why the market reacted.** For the three showcase shares, cited public reporting (publisher and date) is shown
  next to the trading figures. The text says "consistent with", never "caused by".

> **Design rule: numbers come from code, words come from the language model.**
> The engine computes every figure deterministically. The model sees only those figures and writes the text. A numbers
> check and a meaning check compare each text with the figures; a text that fails is replaced by a template, and the
> screen says which one is shown. Without a model key the tool runs on templates.

## What is in this repository

```
config.py      paths, windows and thresholds (one place)
ingest/        raw Deutsche Börse files -> processed tables (daily features, one-minute bars, events)
engine/        deterministic calculations: normal state, impact card, news onset, auctions, comparison, trading cost
ai/            language model access, summary text, numbers and meaning checks, IR analyst, cited explanations
web/           the demo front end: a small JSON server and the page (overview, impact cards, compare, report, ideas)
app/           a second front end (Streamlit), used as the backup view
report/        the IR snapshot (HTML and PDF)
events/        82 corporate events researched from public sources, each with its link; sectors; the research packs
tests/         235 automated tests: engine, data checks, the web API, PDF export, the checks on AI texts
docs/          SUBMISSION.md (data, model and logic) · REQUIREMENTS.md (each point of the brief and where it is in
               the app) · API_CONTRACT.md (the data shapes between the layers)
```

## What is not in this repository

- **The Deutsche Börse data excerpt** and every file computed from it. The data was provided for the challenge and is
  not ours to pass on, so the app cannot be started from the repository alone. The demo video shows it running.
- **The key for the language model.** `.env.example` lists the settings.

## Running it with the data excerpt

```bash
pip install -r requirements.txt
python ingest/build_daily.py "<path to the data excerpt>" data    # about 25 s
python ingest/build_events.py
python ingest/build_intraday.py                                   # about 3 min
python web/server.py                                              # http://127.0.0.1:8600
pytest                                                            # 235 tests
```

## How it fits together

```
raw Deutsche Börse files          events/events.csv (public announcements)
  OHLC · Flow Dynamics · XLM ·              |
  index constituents · on-book trades       |
          |  ingest/                        |
          v                                 v
  daily features (174 shares x 213 days) · one-minute bars (44 shares) · events with reaction day
                          |
                          v
  engine/   deterministic: every figure on the screen
                          |  JSON
                          v
  ai/       the model writes from the JSON; checks compare the text with it
                          |
                          v
  web/ · app/ · report/   overview, impact card, comparison, PDF
```

## Checked against the data

| Check | Result |
|---|---|
| "Who traded" totals against the official Xetra turnover | 1.000 (median of all share-days) |
| One-minute bars against the daily turnover | 1.000 for each of the 44 shares |
| Auction volume from single trades against the flow data | 97.6–99.7 % |
| Announcements published during trading hours | in 7 of 7 the detected start comes after the release |

Showcase shares: Zalando (DAX), CTS Eventim (MDAX), Heidelberger Druck (SDAX).

## What the data cannot tell

The exchange data shows what happened, not why, and it shows participant types, not investor names. Reasons on the
screen come only from linked public sources. Details and limits: `docs/SUBMISSION.md`.
