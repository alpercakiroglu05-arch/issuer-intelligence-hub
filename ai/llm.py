"""
Thin LLM wrapper.  OWNER: C4 (AI).  STATUS: v1 works.

Providers (set in .env, see .env.example):
    openai     any OpenAI-compatible endpoint (OpenAI, JAIF, Mistral, local) via LLM_BASE_URL
    azure      Azure OpenAI
    anthropic  Claude
    none       no LLM -> LLMUnavailable -> callers use deterministic template texts

The demo never breaks: without a key every AI feature falls back to templates.

Answer cache (LLM_CACHE, default on): every answer is stored in data/llm_cache.json, keyed by model + messages.
The same question is answered from the cache, so the live demo survives Wi-Fi or API outages and is fast.
Run each demo scenario once beforehand to fill it. Set LLM_CACHE=false to always ask the model.
"""
import hashlib
import json
import os
from types import SimpleNamespace


class LLMUnavailable(RuntimeError):
    pass


import config  # noqa: E402,F401  (loads .env into os.environ)


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


def model_name() -> str:
    p = _provider()
    return os.getenv("LLM_MODEL") or {"anthropic": "claude-sonnet-5-5"}.get(p, "gpt-4o-mini")


def _cache_path():
    return config.DATA_DIR / "llm_cache.json"


def _cache_key(messages, temperature) -> str:
    raw = json.dumps([_provider(), model_name(), temperature, messages], sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_on() -> bool:
    return os.getenv("LLM_CACHE", "true").lower() not in ("0", "false", "no")


def _cache_get(k: str):
    try:
        return json.loads(_cache_path().read_text(encoding="utf-8")).get(k)
    except (OSError, ValueError):
        return None


def _cache_put(k: str, content: str) -> None:
    try:
        p = _cache_path()
        d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        d[k] = content
        p.write_text(json.dumps(d, ensure_ascii=False, indent=0), encoding="utf-8")
    except (OSError, ValueError):
        pass


def chat(messages: list[dict], temperature: float = 0.2, **kwargs):
    """Returns an object with .content (str) and .tool_calls (OpenAI providers only).
    Plain answers (no tools) are cached when LLM_CACHE is on."""
    key, provider = _key(), _provider()
    model = os.getenv("LLM_MODEL")
    ck = _cache_key(messages, temperature) if _cache_on() and not kwargs else None
    if ck and (hit := _cache_get(ck)) is not None:
        return SimpleNamespace(content=hit, tool_calls=None)
    msg = _call(provider, key, model, messages, temperature, **kwargs)
    if ck and getattr(msg, "content", None):
        _cache_put(ck, msg.content)
    return msg


def _call(provider, key, model, messages, temperature, **kwargs):

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
