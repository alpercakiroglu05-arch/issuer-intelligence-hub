"""
Thin LLM wrapper.  OWNER: C4 (AI).  STATUS: v1 works.

Providers (set in .env, see .env.example):
    openai     any OpenAI-compatible endpoint (OpenAI, JAIF, Mistral, local) via LLM_BASE_URL
    azure      Azure OpenAI
    anthropic  Claude
    none       no LLM -> LLMUnavailable -> callers use deterministic template texts

The demo never breaks: without a key every AI feature falls back to templates.

TODO C4: disk cache for answers (LLM_CACHE) so the live demo survives Wi-Fi/API outages.
"""
import os
from pathlib import Path
from types import SimpleNamespace


class LLMUnavailable(RuntimeError):
    pass


def _load_dotenv() -> None:
    env = Path(__file__).resolve().parents[1] / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()


def _provider() -> str:
    return os.getenv("LLM_PROVIDER", "none").lower()


def _key() -> str:
    p = _provider()
    fallback = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "azure": "OPENAI_API_KEY"}.get(p, "")
    key = os.getenv("LLM_API_KEY") or (os.getenv(fallback) if fallback else "")
    if p == "none" or not key:
        raise LLMUnavailable("LLM not configured (set LLM_PROVIDER and LLM_API_KEY in .env)")
    return key


def available() -> bool:
    try:
        _key()
        return True
    except LLMUnavailable:
        return False


def chat(messages: list[dict], temperature: float = 0.2, **kwargs):
    """Returns an object with .content (str) and .tool_calls (OpenAI providers only)."""
    key, provider = _key(), _provider()
    model = os.getenv("LLM_MODEL")

    if provider == "anthropic":
        import anthropic
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        rest = [m for m in messages if m["role"] != "system"]
        r = anthropic.Anthropic(api_key=key).messages.create(
            model=model or "claude-sonnet-5-5", max_tokens=1000, system=system,
            messages=rest, temperature=temperature)
        return SimpleNamespace(content="".join(b.text for b in r.content if b.type == "text"), tool_calls=None)

    if provider == "azure":
        from openai import AzureOpenAI
        client = AzureOpenAI(api_key=key, azure_endpoint=os.getenv("LLM_BASE_URL"),
                             api_version=os.getenv("AZURE_API_VERSION", "2024-06-01"))
    else:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or None)
    resp = client.chat.completions.create(model=model or "gpt-4o-mini", messages=messages,
                                          temperature=temperature, **kwargs)
    return resp.choices[0].message
