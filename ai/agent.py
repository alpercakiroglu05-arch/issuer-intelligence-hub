"""
IR assistant (Q&A).  OWNER: C4 (AI).  STATUS: v1 = single call with context; v2 = tool calling.

v1: puts kpis() + recent anomalies of the selected stock into the prompt and answers.
v2 (TODO C4): OpenAI tool calling with the TOOLS below so the model can fetch exactly
    what it needs (e.g. "has our liquidity improved since we joined MDAX?").
"""
import json

from ai import llm
from engine import baseline, impact

SYSTEM = """You are the IR assistant of the Issuer Intelligence Hub (Deutsche Boerse Xetra data, 2026).
Answer the question of an investor-relations manager about their own share using ONLY the JSON
context provided. If the context does not contain the answer, say what data would be needed.
Be concise, factual, no investment advice. Answer in the language of the question."""

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


def ask(question: str, isin: str) -> str:
    context = {"kpis": baseline.kpis(isin),
               "recent_anomalies": baseline.anomalies(isin).head(10).to_dict("records")}
    try:
        msg = llm.chat([
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Context JSON:\n{json.dumps(context, default=str)}\n\nQuestion: {question}"},
        ])
        return msg.content.strip()
    except llm.LLMUnavailable:
        trend = baseline.liquidity_trend(isin)
        return ("The assistant needs a language model (JAIF key in `.env`). Until then, the dashboard and the "
                f"impact cards answer most questions. In short: {trend['summary']}")
