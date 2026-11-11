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

`ai/agent.py` gives the model nine tools over the engine (`company_overview`, `peer_benchmark`, `trading_cost_curve`,
`unusual_days`, `event_calendar`, `impact_card`, `compare_events`, `find_company`, `show`). The model picks the tools, reads
their JSON and answers; `show` becomes a one-click button in the UI (open card, compare, report). Every number in the answer is
checked against the tool outputs (`ai/checks.py`); an answer with an unverified figure is replaced by the deterministic
answer from the same tools (the dock then says "template"). Causes come only from the event calendar.
Answers are cached in `data/agent_cache.json` for the live demo (`LLM_CACHE`).

## Files

| File | What |
|---|---|
| `server.py` | static files + `/api/universe`, `/api/issuer`, `/api/card`, `/api/compare`, `/api/status`, `POST /api/calendar`, `POST /api/narrate`, `POST /api/agent`, `POST /api/ask` |
| `index.html` | shell: ISIN entry (gate) and the company workspace |
| `app.css` | DB tokens (navy `#000099`, sky `#0099ff`, News Gothic → Archivo), layout, transitions |
| `app.js` | pages, charts (hand-written SVG), AI numbers check, report builder |

## Demo path

1. Type `eventim` or `DE0005470306` → the ISIN boxes fill and the check digit turns blue → Enter.
2. Dashboard → *Unusual days* → 27 Mar → **Impact card** (one click).
   On the card, **Export IR report (PDF)** downloads the one-page IR snapshot (DE/EN follows the language switch).
3. The AI summary writes itself. Switch to DE. "All 14 figures match the impact card".
4. "See all of them" → **Compare** (871 unusual days, CTS Eventim ranks #10).
5. Press **A** → IR analyst: "What were our biggest moves this year?" → the answer cites the engine and offers "Open impact card".
6. Impact card → **Add event** → a date of your own → the card is built for it.
7. **IR snapshot** → choose sections → Download PDF.

URLs are shareable: `#/<ISIN>/<page>[/<day>/<event_id>]`, e.g. `#/DE0005470306/card/2026-03-27/EVD_FY_20260326`.
