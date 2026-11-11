"""
IR assistant (Q&A).  OWNER: C4 (AI).  STATUS: v1 = single call with context; v2 = tool calling.

v1: puts the liquidity trend, KPIs, the sourced announcements and the unusual episodes (with linked
    announcement and market context) into the prompt. The answer must pass the numbers check
    (ai/checks.py) against that context, else a deterministic answer is returned.
v2 (TODO C4): OpenAI tool calling with the TOOLS below so the model can fetch exactly
    what it needs (e.g. "has our liquidity improved since we joined MDAX?").
"""
import json

from ai import llm
from engine import baseline, impact

SYSTEM = """You are the IR assistant of the Issuer Intelligence Hub (Deutsche Boerse Xetra data, 2026).
Answer the question of an investor-relations manager about their own share using ONLY the JSON context.
How to read it:
- "Has liquidity improved?" -> use liquidity_trend: its verdict and summary (last 60 vs previous 60 trading
  days, stock vs index). Never compare a 60-day median with a 4-month average.
- A specific day or event -> use announcements (the sourced corporate events: date, time, type, title) and
  unusual_episodes (with the linked announcement and market context). If an announcement exists for that day,
  name it; never say there is no context when there is one. Never guess causes beyond the announcement title.
- Numbers: use only numbers from the JSON (rounded; shares as %, EUR in millions). Never compute new ones.
- Do not mention internal fields such as severity, z-scores or field names.
3-5 sentences of plain text (no markdown: no ** and no bullet lists), factual, no investment advice.
Answer in the language of the question."""

# Tool definitions for v2 (OpenAI function-calling format). Implementations = engine functions.
TOOLS = [
    {"type": "function", "function": {"name": "kpis", "description": "Headline liquidity KPIs vs index",
                                      "parameters": {"type": "object", "properties": {"isin": {"type": "string"}, "days": {"type": "integer"}}, "required": ["isin"]}}},
    {"type": "function", "function": {"name": "anomalies", "description": "Unusual trading days",
                                      "parameters": {"type": "object", "properties": {"isin": {"type": "string"}}, "required": ["isin"]}}},
    {"type": "function", "function": {"name": "impact_card", "description": "Impact statistics for one day",
                                      "parameters": {"type": "object", "properties": {"isin": {"type": "string"}, "day": {"type": "string"}}, "required": ["isin", "day"]}}},
]
IMPL = {"kpis": baseline.kpis,
        "anomalies": lambda isin: baseline.anomalies(isin).head(15).to_dict("records"),
        "impact_card": impact.impact_card}


def _context(isin: str) -> dict:
    from engine.data import events
    k = baseline.kpis(isin)
    trend = baseline.liquidity_trend(isin)
    ev = events()
    ev = ev[ev["isin"] == isin].sort_values("reaction_day")
    ann = [{"date": str(r.date.date()), "time": r.time_local or None, "type": r.type, "title": r.title,
            "reaction_day": str(r.reaction_day.date())} for r in ev.itertuples()]
    epi = baseline.anomaly_episodes(isin).head(10)
    episodes = []
    for e in epi.itertuples():
        linked = [a["title"] for a in ann if str(e.start.date()) <= a["reaction_day"] <= str(e.end.date())]
        episodes.append({"start": str(e.start.date()), "end": str(e.end.date()), "reason": e.reason,
                         "stock_specific_move_vs_peers_on_peak_day": round(float(e.peak_abn_ret), 4),
                         "turnover_vs_normal_max": round(float(e.max_vol_ratio), 2),
                         "announcement": linked or None, "market_context": getattr(e, "context", "") or None})
    from engine.data import display_name
    return {"company": display_name(isin), "index": k.get("index"),
            "liquidity_trend": {x: trend.get(x) for x in ("period", "verdict", "vs_index", "summary", "ds_category",
                                                         "xlm_25k_change_pct", "turnover_change_pct")},
            "kpis_last_60_days": {x: k.get(x) for x in ("median_turnover_eur", "median_xlm_25k_bps",
                                                         "median_auction_share", "median_agent_share")},
            "announcements": ann, "unusual_episodes": episodes}


def _fallback(isin: str, ctx: dict) -> str:
    """Deterministic answer when there is no model or its answer failed the numbers check."""
    lines = [ctx["liquidity_trend"]["summary"]]
    for e in ctx["unusual_episodes"][:3]:
        what = "; ".join(e["announcement"]) if e["announcement"] else "no company announcement found"
        lines.append(f"{e['start']}: {e['reason']} ({what}).")
    return " ".join(lines)


def ask(question: str, isin: str) -> str:
    from ai.checks import unsupported_numbers
    ctx = _context(isin)
    try:
        msg = llm.chat([
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Context JSON:\n{json.dumps(ctx, default=str)}\n\nQuestion: {question}"},
        ])
        text = (msg.content or "").strip()
        if text and not unsupported_numbers(text, ctx):
            return text
    except llm.LLMUnavailable:
        return ("The assistant needs a language model (JAIF key in `.env`). Until then, the dashboard and the "
                f"impact cards answer most questions. In short: {_fallback(isin, ctx)}")
    except Exception:  # noqa: BLE001  network, quota ...
        pass
    return _fallback(isin, ctx)
