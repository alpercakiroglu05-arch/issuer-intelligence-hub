"""
Impact card -> short IR text in German or English.  OWNER: C4 (AI).  STATUS: v1 works.

Rule: the LLM only sees the impact_card JSON. Every number in the text must come from it.

TODO C4:
  - tune the prompt with the IR expert (tone: factual, no advice, no speculation)
  - add a numbers check: every number in the output must appear in the JSON (else fall back)
"""
import json

from ai import llm

SYSTEM = """You are an investor-relations analyst writing for the IR team of a listed company.
You receive ONE JSON object with pre-computed trading statistics for one event day.
Write 4-5 short sentences in {language}:
1) what happened to the share price vs. index peers (abnormal return),
2) how unusual the trading activity was (volume vs. normal),
3) liquidity / spread and the opening/closing auctions (volume vs normal, auction price vs previous close / last trade),
4) who traded (agent = client/institutional orders, prop, market makers), only if notable,
5) if intraday.onset.time is set: when the market started pricing the news (that clock time).
Rules: use ONLY numbers that appear in the JSON (rounded); never invent causes or numbers;
no investment advice; no predictions; plain factual tone. Ratios: 'x times normal'."""

LANG = {"en": "English", "de": "German"}


def narrate(card: dict, lang: str = "en") -> str:
    try:
        msg = llm.chat([
            {"role": "system", "content": SYSTEM.format(language=LANG.get(lang, "English"))},
            {"role": "user", "content": json.dumps(card, default=str)},
        ])
        return msg.content.strip()
    except Exception:  # LLMUnavailable, network, quota ... -> deterministic text
        return template_narrative(card, lang)


def _p(x):
    return "n/a" if x is None else f"{x * 100:+.1f}%"


def template_narrative(card: dict, lang: str = "en") -> str:
    p, v, l, a = card["price"], card["volume"], card["liquidity"], card["participants"]
    o = (card.get("intraday") or {}).get("onset") or {}
    au = card.get("auctions") or {}
    if lang == "de":
        t = (f"{card['name']} veränderte sich am {card['event']['reaction_day']} um {_p(p['ret'])}, "
             f"die {card['index']}-Vergleichswerte um {_p(p['peer_ret'])} (unternehmensspezifisch: {_p(p['abn_ret'])}). "
             f"Der Umsatz lag beim {(v['ratio'] or 0):.1f}-fachen des Normalniveaus. ")
        if l["ratio"]:
            t += f"Die Liquiditätskosten (XLM 25k) lagen bei {l['xlm_25k_bps']:.0f} bps ({l['ratio']:.1f}x normal). "
        if a["agent_aggr_imbalance"] is not None:
            side = "Verkaufs" if a["agent_aggr_imbalance"] < 0 else "Kauf"
            t += f"Agentenorders zeigten einen {side}überhang von {abs(a['agent_aggr_imbalance']) * 100:.0f}%."
        if o.get("time"):
            t += f" Der Markt begann die Nachricht um {o['time']} Uhr einzupreisen ({_p(o['ret_at_onset'])})."
        if au.get("close_auction_ratio") is not None:
            t += (f" Die Schlussauktion war {au['close_auction_ratio']:.1f}-mal so groß wie normal und "
                  f"bewegte den Kurs um {_p(au['close_auction_move'])} gegenüber dem letzten Handel.")
        return t
    t = (f"{card['name']} moved {_p(p['ret'])} on {card['event']['reaction_day']} while its {card['index']} peers "
         f"moved {_p(p['peer_ret'])} (stock-specific: {_p(p['abn_ret'])}). "
         f"Turnover was {(v['ratio'] or 0):.1f}x its normal level. ")
    if l["ratio"]:
        t += f"Trading cost (XLM 25k) was {l['xlm_25k_bps']:.0f} bps ({l['ratio']:.1f}x normal). "
    if a["agent_aggr_imbalance"] is not None:
        side = "selling" if a["agent_aggr_imbalance"] < 0 else "buying"
        t += f"Agent (client) orders were net {side}: imbalance {abs(a['agent_aggr_imbalance']) * 100:.0f}%."
    if o.get("time"):
        t += f" The market started pricing the news at {o['time']} ({_p(o['ret_at_onset'])} vs. previous close)."
    if au.get("close_auction_ratio") is not None:
        t += (f" The closing auction was {au['close_auction_ratio']:.1f}x its normal size and moved the price "
              f"{_p(au['close_auction_move'])} vs. the last trade.")
    return t
