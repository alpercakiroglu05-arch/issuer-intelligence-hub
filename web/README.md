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
checked against the tool outputs (`ai/checks.py`) and the result is shown under the answer. Causes come only from the event calendar.
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

1. (0:00) Click **EVD CTS Eventim** → dashboard: €11.8m a day, 21.1 bps for €25k, liquidity stable, category A.
2. (0:15) "Most unusual day this year: 27 March" → **Open its impact card**: −23.2 %, peers −1.5 %, stock-specific −21.7 %,
   8.6× turnover, closing auction €25.6m (3.6×), reaction detected in trading at 09:03.
3. (0:35) **Evidence brief** → type "The whole market sold off that day" → **Contradicted by the data**, with the
   wording to use instead. Click "Funds / short sellers sold" → **Not testable with this data** (Xetra does not identify investors).
4. (0:55) "See all of them" → **Compare**: rank 3 of 215 unusual MDAX days.
5. (1:05) Press **A** → "Was this the market, or company-specific?" → the analyst runs the same check and cites the figures.
6. (1:20) **IR snapshot** → main finding, limits, next step, explanations checked → Print / save as PDF.

URLs are shareable: `#/<ISIN>/<page>[/<day>/<event_id>]`, e.g. `#/DE0005470306/card/2026-03-27/EVD_FY_20260326`.
