# Web front end (C3)

The demo UI: Deutsche Börse family look, ISIN entry, dashboard, impact card, compare, IR snapshot and ideas, plus the IR analyst (AI agent) on every page.
Every number comes from the engine (`engine/`) through a small JSON API. Words come from `ai/` (LLM or template fallback).
The page map and the challenge items each page covers are listed in [`docs/REQUIREMENTS.md`](../docs/REQUIREMENTS.md).

## Run

```bash
pip install -r requirements.txt
python web/server.py            # → http://127.0.0.1:8600  (macOS: python3 or .venv/bin/python)
```

The server needs the processed files in `data/` (from OneDrive, or rebuilt with the ingest scripts in the main README).
It uses only the standard library on top of the existing requirements, so nothing new has to be installed.

To switch on the language model, put the JAIF / hessian.AI gateway in `.env` (the key stays on the server; the browser never sees it):

```
LLM_PROVIDER=openai
LLM_BASE_URL=https://hip-gw.hessian.ai/v1
LLM_API_KEY=<team key from the model handbook>
LLM_MODEL=<a model from the model handbook that supports tool calling>
```

Without a key, the AI summary and the analyst use deterministic templates over the same engine tools, and the header shows "AI: template mode".

### The IR analyst (agent)

`ai/agent.py` gives the model ten tools over the engine (`company_overview`, `peer_benchmark`, `trading_cost_curve`,
`unusual_days`, `event_calendar`, `impact_card`, `compare_events`, `check_explanation`, `find_company`, `show`). The model picks the tools, reads
their JSON and answers; `show` becomes a one-click button in the UI (open card, compare, report). Every number in the answer is
checked against the tool outputs (`ai/checks.py`); an answer with an unverified figure is replaced by the deterministic
answer from the same tools (the dock then says "fixed rules"). Causes come only from the event calendar.
Answers are cached in `data/agent_cache.json` for the live demo (`LLM_CACHE`); a replayed answer is labelled
"saved answer", never presented as a fresh analysis. Each model call times out after 45 s (`LLM_TIMEOUT`) and the
whole tool loop after 75 s; then the deterministic answer is shown, so the demo never hangs.

### Signature: evidence brief + "Test an explanation"

Every impact card opens with an **evidence brief** (`engine/evidence.py`, `GET /api/evidence`): what changed, what the
broader market did, what was distinctive about trading, how unusual it was, what the data cannot tell, and what to check
next. Below it, IR can **test an explanation** before telling the board ("it was the market", "thin trading",
"funds sold", "an overreaction", "trading before the news"). Each is checked against the card's figures with fixed rules
and gets a verdict (supported / contradicted / partly / not testable with this data) plus a more defensible wording.
No language model is involved, so it also works offline; the assistant uses the same check (`check_explanation`).

### Own calendar import

CSV (quoted fields, `;` `,` or tab, EN/DE headers, `YYYY-MM-DD` or `DD.MM.YYYY`) or ICS (UTC, `TZID` converted to
Berlin time, floating times read as Berlin time). The import shows a **preview** first: every row with its status
(matched → reaction day and the rule used; before / after the data; skipped with the reason). Nothing is saved until the
user confirms; if browser storage is blocked the events are kept for the session and the message says so.

## Offline copy to share

```bash
python web/snapshot.py          # -> ~/Desktop/Issuer-Intelligence-Hub.html (EVD, EVT, HDD; ~2.5 MB)
```

One HTML file that opens with a double click, without Python or `data/`. It contains the answers for the showcase shares
(dashboards, every impact card with its evidence brief, comparisons, AI summaries, the analyst's suggested questions).
The page marks itself as an offline copy; typed questions and the calendar import are disabled with an explanation,
the explanation check works. `--llm` writes the AI texts
with the model in `.env`. It contains processed Deutsche Börse data: share it inside the team only, never commit it.

## Files

| File | What |
|---|---|
| `server.py` | static files + `/api/universe`, `/api/issuer`, `/api/card`, `/api/evidence`, `/api/compare`, `/api/status`, `POST /api/calendar`, `POST /api/narrate`, `POST /api/agent`, `POST /api/ask` |
| `index.html` | shell: ISIN entry (gate) and the company workspace |
| `app.css` | DB tokens (navy `#000099`, sky `#0099ff`, News Gothic → Archivo), layout, transitions |
| `app.js` | pages, charts (hand-written SVG), AI numbers check, report builder, analyst dock |
| `snapshot.py` | builds the offline single-file copy |

## Demo path (90 seconds)

1. The app opens on the dashboard. Type `eventim` in the picker (or click the MDAX example) and choose **All**.
2. Four tiles, then *You vs market* (price, turnover and trading cost against the MDAX, each with its rank) and
   *Big market days* (how the share moved on the strongest index days).
3. *Events & unusual days* -> row **26 Mar · 17:45 · Full-year results** -> the impact card opens in under a second.
4. Card: stock-specific move -21.7 %, turnover 8.6x, rank 3 of 215; the minute chart marks **reaction in trading
   from 09:03**; auctions and who traded; the AI summary loads after the numbers.
5. **Test an explanation** -> "It was the overall market." -> "Not supported by the data", with wording the data supports.
6. **Export PDF**, then switch to DE and export again. Optional: *see all* on the rank tile -> Compare.

Simple UI (12 Nov): one page per job, every number from `/api/dashboard`, `/api/card`, `/api/evidence` and
`/api/compare`; `app.js` only formats and draws. The earlier UI is at the git tag `pre-ui`.
