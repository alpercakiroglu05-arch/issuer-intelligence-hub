# Web front end (C3)

The Issuer Intelligence Hub UI (`web/index.html`, `app.css`, `app.js`, served at `/`). It opens straight on the dashboard
of the last company (CTS Eventim the first time): Overview with the periods 1M / 3M / YTD (price, turnover, trading cost
and auction share over time, who trades, trading cost by order size, peers, unusual days), Events, the impact card (at a
glance, the day minute by minute, who traded, evidence), Compare, Report and Ideas, plus the IR analyst drawer and a share
search (⌘K). Light theme by default, dark on request (remembered). The earlier UI was replaced by this one.
Every number comes from the engine (`engine/`) through a small JSON API. Words come from `ai/` (LLM or template fallback).
The page map and the challenge items each page covers are listed in [`docs/REQUIREMENTS.md`](../docs/REQUIREMENTS.md).

## Run

```bash
pip install -r requirements.txt
python web/server.py            # → http://127.0.0.1:8600  (macOS: python3 or .venv/bin/python)
```

**Without a terminal:** double-click `start.command` (macOS) or `start.bat` (Windows) in the repo folder. It checks for
`data/`, installs the packages on the first start, starts the server and opens the browser. On another laptop in the same
Wi-Fi the demo can be opened with `start.command --host 0.0.0.0` and then `http://<this laptop's IP>:8600` (the data is then
reachable for everyone in that network, so only on a trusted network).

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

`ai/agent.py` gives the model eleven tools over the engine (`company_overview`, `share_performance`, `peer_benchmark`, `trading_cost_curve`,
`unusual_days`, `event_calendar`, `impact_card`, `compare_events`, `check_explanation`, `find_company`, `show`). The model picks the tools, reads
their JSON and answers; `show` becomes a one-click button in the UI (open card, compare, report). Every number in the answer is
checked against the tool outputs (`ai/checks.py`); an answer with an unverified figure is replaced by the deterministic
answer from the same tools (the dock then says "fixed rules"). Causes come only from the event calendar.
Answers are cached in `data/agent_cache.json` for the live demo (`LLM_CACHE`); a replayed answer is labelled
"saved answer", never presented as a fresh analysis. Each model call times out after 45 s (`LLM_TIMEOUT`) and the
whole tool loop after 75 s; then the deterministic answer is shown, so the demo never hangs.
The UI sends the selected period (`period`, `from`, `to`) with every question, so "how did we do?" uses the period on screen;
`share_performance` returns an error for a period the data does not cover (1Y), and the analyst says so.

### Periods

1M = last 21 trading days, 3M = 63, YTD = this calendar year (engine.market, `GET /api/dashboard?period=`); 1Y (252)
exists in the engine but is not offered, because the data starts on 2 Jan 2026.
The return runs from the close of the trading day before the window to the last close (closing-auction prices, not adjusted
for dividends; ex-dividend days in the window are listed). The excerpt starts on 2 Jan 2026, so YTD starts at the 2 Jan close
(the 31 Dec 2025 close is not in the data, the page says so) and 1Y is disabled with the reason. "Index" = the equal-weighted
move of the other index members (`peer_ret`), the same index as the impact card's stock-specific move.

### Signature: evidence brief + "Test an explanation"

Every impact card opens with an **evidence brief** (`engine/evidence.py`, `GET /api/evidence`): what changed, what the
broader market did, what was distinctive about trading, how unusual it was, what the data cannot tell, and what to check
next. Below it, IR can **test an explanation** before telling the board ("it was the market", "thin trading",
"funds sold", "an overreaction", "trading before the news"). Each is checked against the card's figures with fixed rules
and gets a verdict (supported / contradicted / partly / not testable with this data) plus a more defensible wording.
No language model is involved, so it also works offline; the assistant uses the same check (`check_explanation`).

### Impact cards (Events page)

Every calendar event (`events/events.csv`, researched with sources, matched to the reaction day) and every unusual day
without an entry is listed with its impact card, and "Create an impact card for any day" builds one for any trading day of
the data (a weekend or holiday opens the next trading day). `POST /api/calendar` (match your own dates to trading days)
stays in the API; the UI no longer offers a calendar upload.

## Offline copy to share

```bash
python web/snapshot.py          # -> ~/Desktop/Issuer-Intelligence-Hub.html (ZAL, EVD, HDD; ~3.5 MB)
```

One HTML file that opens with a double click, without Python or `data/`. It contains the answers for the showcase shares
(dashboards, every impact card with its evidence brief, comparisons, AI summaries, the analyst's suggested questions).
The page marks itself as an offline copy; typed questions are disabled with an explanation,
the explanation check works. `--llm` writes the AI texts
with the model in `.env`. It contains processed Deutsche Börse data: share it inside the team only, never commit it.

## Files

| File | What |
|---|---|
| `server.py` | static files + `/api/universe`, `/api/issuer`, `/api/card`, `/api/evidence`, `/api/compare`, `/api/status`, `POST /api/calendar`, `POST /api/narrate`, `POST /api/agent`, `POST /api/ask` |
| `index.html` | shell: top bar, page, analyst drawer, search; sets the theme before the first paint |
| `app.css` | theme tokens (light by default, `:root[data-theme=dark]`), layout, transitions |
| `app.js` | pages, charts (hand-written SVG), periods, AI numbers check, evidence statuses, report builder, analyst |
| `snapshot.py` | builds the offline single-file copy |

## Demo path (90 seconds)

1. (0:00) The page opens on **CTS Eventim** (YTD): price vs MDAX peers, turnover, trading cost, category A.
2. (0:15) "Most unusual day · YTD: 27 March" → **Open impact card**: −23.2 %, peers −1.5 %, stock-specific −21.7 %,
   8.6× turnover, closing auction €25.6m (3.6×), reaction detected in trading at 09:03.
3. (0:35) Tab **Evidence** → type "The whole market sold off that day" → **Contradicted by the data**, with the
   wording to use instead. Click "Funds / short sellers sold" → **Not testable with this data** (Xetra does not identify investors).
4. (0:55) **Compare with similar days** → rank 3 of 215 unusual MDAX days.
5. (1:05) Press **A** → "Was this the market, or company-specific?" → the analyst runs the same check and cites the figures.
6. (1:20) **Add to report** → choose the sections (checkboxes) → Save as PDF. (Each card also has **Export IR report (PDF)**, one click.)

URLs are shareable: `#/<ISIN>/<page>[/<day>/<event_id>]`, e.g. `#/DE0005470306/event/2026-03-27/EVD_FY_20260326`.
