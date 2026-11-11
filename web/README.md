# Web front end (C3)

The demo UI: Deutsche Börse family look, ISIN entry, dashboard, impact card, compare, assistant, report and ideas.
Every number comes from the engine (`engine/`) through a small JSON API. Words come from `ai/` (LLM or template fallback).
The page map and the challenge items each page covers are listed in [`docs/REQUIREMENTS.md`](../docs/REQUIREMENTS.md).

## Run

```bash
pip install -r requirements.txt
python web/server.py            # → http://127.0.0.1:8600
```

The server needs the processed files in `data/` (from OneDrive, or rebuilt with the ingest scripts in the main README).
It uses only the standard library on top of the existing requirements, so nothing new has to be installed.

To switch on the language model, add `LLM_PROVIDER` and `LLM_API_KEY` to `.env`. The key stays on the server; the browser never sees it.
Without a key, the AI summary and the assistant use deterministic templates, and the header shows "AI: template mode".

## Files

| File | What |
|---|---|
| `server.py` | static files + `/api/universe`, `/api/issuer`, `/api/card`, `/api/compare`, `POST /api/narrate`, `POST /api/ask`, `/api/status` |
| `index.html` | shell: ISIN entry (gate) and the company workspace |
| `app.css` | DB tokens (navy `#000099`, sky `#0099ff`, News Gothic → Archivo), layout, transitions |
| `app.js` | pages, charts (hand-written SVG), AI numbers check, report builder |

## Demo path

1. Type `eventim` or `DE0005470306` → the ISIN boxes fill and the check digit turns blue → Enter.
2. Dashboard → *Unusual days* → 27 Mar → **Impact card** (one click).
3. The AI summary writes itself. Switch to DE. "All 14 figures match the impact card".
4. "See all of them" → **Compare** (871 unusual days, CTS Eventim ranks #10).
5. **Report** → choose sections → Download PDF.

URLs are shareable: `#/<ISIN>/<page>[/<day>/<event_id>]`, e.g. `#/DE0005470306/card/2026-03-27/EVD_FY_20260326`.
