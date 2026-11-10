"""Append-only audit log (JSON Lines). Banking juries care about traceability: log every AI
output and every human decision, and show the log in the demo."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / ".cache" / "audit_log.jsonl"


def log_event(event_type: str, case_id: str, payload: dict, actor: str = "system") -> dict:
    event = {
        "event_id": uuid.uuid4().hex[:12],
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "event_type": event_type,
        "case_id": case_id,
        "actor": actor,
        "payload": payload,
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def read_events(case_id: str | None = None, limit: int = 200) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    events = [json.loads(line) for line in LOG_PATH.read_text(encoding="utf-8").splitlines() if line]
    if case_id:
        events = [e for e in events if e["case_id"] == case_id]
    return list(reversed(events))[:limit]  # newest first
