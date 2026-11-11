"""Pre-warm the answer caches for the demo, so the live demo needs no network and no waiting.

Two caches, both in data/ (local, never committed):
- data/llm_cache.json: card summaries. The key is the exact prompt, so a change to a prompt or to the impact-card
  JSON makes old entries useless (they are simply not hit any more).
- data/agent_cache.json: assistant answers. The key is the question, page context and language, NOT the engine
  output, so after an engine change old answers can show old numbers. This script always asks these again.

Run it after a prompt, card or engine change and before recording the demo:

    python web/warm_cache.py              # hero stocks (config.HERO_TICKERS)
    python web/warm_cache.py EVD GXI      # chosen tickers

It goes through the web server's own functions (narrate, agent) with the same arguments the web UI sends, so
the keys are exactly what the demo asks for:
- the summary of every calendar event and of the 5 most unusual days, in EN and DE;
- the assistant dock's suggested questions on the dashboard, and on the card of the stock's most unusual day.
Needs the JAIF key in .env. Summaries that fail the numbers check are reported (the demo shows the template there).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import server

from ai import agent as ag
from config import HERO_TICKERS
from engine import baseline, data

DOCK = {  # the chips of the assistant dock (web/app.js, dockSugg); the page is sent as context (dockCtx)
    "dashboard": {"en": ["Has our liquidity improved?", "How do our spreads compare with our sector?",
                         "What were our biggest moves this year?", "How large an order can the book absorb?"],
                  "de": ["Hat sich unsere Liquidität verbessert?", "Wie sind unsere Spreads im Sektorvergleich?",
                         "Was waren unsere größten Bewegungen dieses Jahr?", "Wie große Orders nimmt das Orderbuch auf?"]},
    "card": {"en": ["Explain this card in two sentences", "How does this rank against similar events?"],
             "de": ["Erklären Sie diese Karte in zwei Sätzen",
                    "Wie ordnet sich das gegenüber ähnlichen Ereignissen ein?"]},
}


def cards_for(isin: str) -> list[tuple[str, str | None]]:
    """(day, event_id) for every calendar event and the 5 most unusual days, as the web opens them."""
    ev = data.events()
    ev = ev[ev["isin"] == isin]
    out = [(str(pd.Timestamp(d).date()), e) for d, e in zip(ev["reaction_day"], ev["event_id"], strict=True)]
    by_day = dict(out)
    ep = baseline.anomaly_episodes(isin).sort_values("severity", ascending=False).head(5)
    for d in ep["peak_date"]:
        day = str(pd.Timestamp(d).date())
        if day not in by_day:
            out.append((day, None))
    return out


def top_card(isin: str) -> tuple[str, str] | None:
    """The most unusual day with its calendar event (the demo card), or None if it has no event."""
    ep = baseline.anomaly_episodes(isin)
    if ep.empty:
        return None
    day = str(pd.Timestamp(ep.sort_values("severity", ascending=False)["peak_date"].iloc[0]).date())
    event_id = dict(cards_for(isin)).get(day)
    return (day, event_id) if event_id else None


def main(tickers: list[str]) -> int:
    if not server.llm_available():
        print("No language model configured (LLM_PROVIDER / LLM_API_KEY in .env): nothing to warm.")
        return 1
    read = ag._cache
    ag._cache = lambda key, value=None: None if value is None else read(key, value)  # always ask again, then store
    n = llm = 0
    rejected, flagged = [], []
    t0 = time.time()
    for t in tickers:
        isin = data.isin_of(t)
        for day, event_id in cards_for(isin):
            for lang in ("en", "de"):
                m = server.narrate({"isin": isin, "day": day, "event_id": event_id, "lang": lang})
                n += 1
                llm += m["source"] == "llm"
                if m["source"] != "llm":
                    rejected.append(f"{t} {day} {lang}: {m['rejected']}")
                print(f"{t} {day} {lang} summary: {m['source']}", flush=True)
        asks = [({"page": "dashboard"}, DOCK["dashboard"])]
        card = top_card(isin)
        if card:
            asks.append(({"page": "card", "day": card[0], "event_id": card[1]}, DOCK["card"]))
        for ctx, qs in asks:
            for lang, questions in qs.items():
                for q in questions:
                    out = server.agent({"isin": isin, "question": q, "history": [], "context": ctx, "lang": lang})
                    n += 1
                    bad = out.get("rejected") or (out.get("check") or {}).get("unsupported") or []
                    if bad:
                        flagged.append(f"{t} {ctx['page']} {lang} '{q}': {bad}")
                    print(f"{t} {ctx['page']} {lang} ask: {out['source']}{' FLAGGED ' + str(bad) if bad else ''}", flush=True)
    print(f"\n{n} texts warmed in {time.time() - t0:.0f} s; summaries from the model: {llm}, template: {len(rejected)}; "
          f"assistant answers that fall back (figures not found): {len(flagged)}")
    for r in rejected:
        print("  summary shows the template:", r)
    for f in flagged:
        print("  assistant shows the deterministic answer:", f)
    return 0


if __name__ == "__main__":
    sys.exit(main([a.upper() for a in sys.argv[1:]] or list(HERO_TICKERS)))
