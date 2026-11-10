# API contract

Agree on this in the first hour; then frontend and backend work in parallel
(frontend against mock mode, backend on the real logic). Change it only together.

Live docs when the API runs: http://127.0.0.1:8000/docs

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| GET | `/health` | – | `{status, provider, model}` |
| GET | `/scenarios` | – | `{name: text}` |
| POST | `/analyze` | `{text, source_name}` | `AnalysisResult` |
| POST | `/analyze/file` | multipart `file` (PDF/TXT) | `AnalysisResult` |
| POST | `/decision` | `{case_id, decision, reviewer, comment}` | audit event |
| GET | `/audit?case_id=` | – | audit events, newest first |

```jsonc
// AnalysisResult (example pipeline: replace fields once the challenge is chosen)
{
  "case_id": "a1b2c3d4",
  "summary": "2-3 sentences",
  "risk_level": "low | medium | high",
  "findings": [{"issue": "...", "severity": "low | medium | high", "evidence": "exact quote"}],
  "missing_information": ["..."],
  "recommended_action": "...",
  "needs_human_review": true,
  "model": "anthropic:claude-sonnet-5-5"
}
```
