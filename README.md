# Project Name

> One sentence: **[Name] helps [user] at [bank] do [task] in [minutes] instead of [hours], with a human in control.**

Built in 32 hours at **Futury Build Days #4 — Banking & Finance** (Frankfurt, 11–12 Nov 2026).
Challenge: _TBD (Deutsche Bank / Deutsche Börse Group / Helaba)_

## Problem

_Who is the user, what do they do today, what does it cost? One concrete number._

## Solution

_What the prototype does, in 3 bullets._

- Reads [input] and extracts [what]
- Flags [issues] with the exact evidence it is based on
- A human approves, escalates or rejects; every step lands in an audit trail

## Quick start

```bash
git clone <REPO_URL> && cd <REPO>
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env

streamlit run app/streamlit_app.py # demo UI  -> http://localhost:8501
uvicorn api.main:app --reload      # REST API -> http://127.0.0.1:8000/docs
pytest                             # smoke tests (mock mode, no API key needed)
```

`LLM_PROVIDER=mock` works without any API key, so everyone can run the app from minute one.
Switch to `anthropic` or `openai` in `.env` when a key is in place. `openai` also covers any
OpenAI-compatible endpoint via `OPENAI_BASE_URL` (Mistral, a local model, an organiser endpoint).

## How it works

```text
input (PDF / text) -> core/documents.py   extract text
                   -> core/pipeline.py    LLM returns structured JSON with quoted evidence
                   -> app/ or api/        human decision: approve / escalate / reject
                   -> core/audit.py       every AI output and decision logged (.cache/audit_log.jsonl)
```

| Folder | What lives there |
| --- | --- |
| `app/` | Streamlit demo UI |
| `api/` | FastAPI endpoints (for a React/Next.js frontend) |
| `core/` | LLM client, pipeline and prompts, document parsing, audit log |
| `data/scenarios/` | 3 fictional demo cases: clean, red flags, edge case |
| `docs/` | Scope, API contract, pitch |
| `tests/` | Smoke tests |

## Data

Only synthetic or public data. No real customer or employer data, ever.

## Team

| Name | Role |
| --- | --- |
| | Captain — product & pitch |
| | Tech lead — backend & AI |
| | Frontend & demo |
| | Data & research |
