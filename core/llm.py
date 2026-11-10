"""Provider-agnostic LLM helper: JSON output, disk cache, offline mock mode.

Switch providers with LLM_PROVIDER in .env:
  mock       -> no API key needed, deterministic fake answers (walking skeleton / offline demo)
  anthropic  -> Anthropic API (ANTHROPIC_API_KEY)
  openai     -> OpenAI API or ANY OpenAI-compatible endpoint (OPENAI_API_KEY + optional OPENAI_BASE_URL,
                e.g. Mistral, a local model, or an endpoint the organisers provide)

The cache makes the live demo resilient: once a prompt has been answered, the same prompt is
served from .cache/llm even if the API or Wi-Fi goes down.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
from typing import Callable

from dotenv import load_dotenv

load_dotenv()

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / ".cache" / "llm"

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5-5",
    "openai": "gpt-4o-mini",
}


def provider() -> str:
    return os.getenv("LLM_PROVIDER", "mock").strip().lower()


def model() -> str:
    return os.getenv("LLM_MODEL", "").strip() or DEFAULT_MODELS.get(provider(), "mock")


def _cache_enabled() -> bool:
    return os.getenv("LLM_CACHE", "true").strip().lower() == "true"


def _cache_path(system: str, user: str) -> pathlib.Path:
    digest = hashlib.sha256(f"{provider()}|{model()}|{system}|{user}".encode()).hexdigest()[:24]
    return CACHE_DIR / f"{digest}.json"


def _extract_json(text: str) -> dict:
    """Parse JSON even if the model wrapped it in ```json fences or added prose around it."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise ValueError(f"Model did not return JSON: {text[:300]}")


def _call_anthropic(system: str, user: str) -> str:
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    resp = client.messages.create(
        model=model(),
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")


def _call_openai(system: str, user: str) -> str:
    from openai import OpenAI

    client = OpenAI(base_url=os.getenv("OPENAI_BASE_URL") or None)  # reads OPENAI_API_KEY
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    try:
        resp = client.chat.completions.create(
            model=model(), messages=messages, response_format={"type": "json_object"}
        )
    except Exception:
        # Some OpenAI-compatible endpoints don't support response_format -> retry without it.
        resp = client.chat.completions.create(model=model(), messages=messages)
    return resp.choices[0].message.content or ""


def complete_json(system: str, user: str, mock: Callable[[str], dict] | None = None) -> dict:
    """Send a prompt, get a dict back. `mock` builds the answer when LLM_PROVIDER=mock."""
    path = _cache_path(system, user)
    if _cache_enabled() and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    p = provider()
    if p == "anthropic":
        result = _extract_json(_call_anthropic(system, user))
    elif p == "openai":
        result = _extract_json(_call_openai(system, user))
    elif p == "mock":
        result = mock(user) if mock else {"answer": "mock response", "input_chars": len(user)}
    else:
        raise ValueError(f"Unknown LLM_PROVIDER '{p}'. Use mock, anthropic or openai.")

    if _cache_enabled() and p != "mock":
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
