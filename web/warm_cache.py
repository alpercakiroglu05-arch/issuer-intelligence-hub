"""Pre-warm the LLM answer cache (data/llm_cache.json) for the demo, so the live demo needs no network.

The cache key is the exact prompt, so every change to a prompt or to the impact-card JSON makes old entries
useless. Run this after such a change and before recording the demo:

    python web/warm_cache.py              # hero stocks (config.HERO_TICKERS)
    python web/warm_cache.py EVD GXI      # chosen tickers

It goes through the web server's own functions (narrate, ask), so the keys are exactly what the demo asks for:
every calendar event and the 5 most unusual days of each stock, in EN and DE, plus the assistant's suggested
questions. Needs the JAIF key in .env. Texts that fail the numbers check are reported (the demo shows the
template there).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import server

from config import HERO_TICKERS
from engine import baseline, data

QUESTIONS = {  # the chips on the web Assistant page (web/app.js, pAsk)
    "en": ["Has our liquidity improved?", "How do our spreads compare with the {index}?",
           "Did trading change after results?", "What happened on {top}?"],
    "de": ["Hat sich unsere Liquidität verbessert?", "Wie sind unsere Spreads im {index}-Vergleich?",
           "Hat sich der Handel nach den Ergebnissen verändert?", "Was ist am {top} passiert?"],
}


def cards_for(isin: str) -> list[tuple[str, str | None]]:
    """(day, event_id) for every calendar event and the 5 most unusual days, as the web opens them."""
    ev = data.events()
    ev = ev[ev["isin"] == isin]
    out = [(str(pd.Timestamp(d).date()), e) for d, e in zip(ev["reaction_day"], ev["event_id"])]
    by_day = {d: e for d, e in out}
    ep = baseline.anomaly_episodes(isin).sort_values("severity", ascending=False).head(5)
    for d in ep["peak_date"]:
        day = str(pd.Timestamp(d).date())
        if day not in by_day:
            out.append((day, None))
    return out


def main(tickers: list[str]) -> int:
    if not server.llm_available():
        print("No language model configured (LLM_PROVIDER / LLM_API_KEY in .env): nothing to warm.")
        return 1
    n = llm = 0
    rejected = []
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
                print(f"{t} {day} {lang} {m['source']}", flush=True)
        eps = baseline.anomaly_episodes(isin)
        top = str(pd.Timestamp(eps.sort_values("severity", ascending=False)["peak_date"].iloc[0]).date()) if len(eps) else None
        index = baseline.kpis(isin)["index"]
        for lang, qs in QUESTIONS.items():
            for q in qs:
                if "{top}" in q and not top:
                    continue
                server.ask({"isin": isin, "question": q.format(index=index, top=top), "lang": lang})
                n += 1
                print(f"{t} ask {lang}: {q.format(index=index, top=top)}", flush=True)
    print(f"\n{n} texts warmed in {time.time() - t0:.0f} s; summaries from the model: {llm}, template instead: {len(rejected)}")
    for r in rejected:
        print("  template:", r)
    return 0


if __name__ == "__main__":
    sys.exit(main([a.upper() for a in sys.argv[1:]] or list(HERO_TICKERS)))
