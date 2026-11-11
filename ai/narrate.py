"""
Impact card -> short IR text in German or English.  OWNER: C4 (AI).  STATUS: v1 works.

Rule: the LLM only sees the impact_card JSON. Every number in the text must come from it.

Numbers check (ai/checks.py): an LLM text with a number that is not in the card JSON is rejected and the
template text is used instead. narrate_with_meta() says which one the user sees.

TODO C4: tune the prompt with the IR expert (tone: factual, no advice, no speculation)
"""
import json

from ai import llm
from ai.checks import unsupported_numbers
from report.fmt import formatters, group_label

SYSTEM = """You are an investor-relations analyst writing for the IR team of a listed company.
You receive ONE JSON object with pre-computed trading statistics for one event day.
Write 4-5 short sentences in {language}:
1) what happened to the share price vs. index peers (abnormal return),
2) how unusual the trading activity was (volume vs. normal),
3) liquidity / spread and the opening/closing auctions (volume vs normal, auction price vs previous close / last trade),
4) who traded (agent = client/institutional orders, prop, market makers), only if notable,
5) if intraday.onset.time is set: when the market started pricing the news (that clock time),
6) if comparison is set: how this event ranks among comparable events (percentiles, group size).
Rules: use ONLY numbers that appear in the JSON (rounded); never invent causes or numbers;
no investment advice; no predictions; plain factual tone. Ratios: 'x times normal'."""

LANG = {"en": "English", "de": "German"}


def narrate_with_meta(card: dict, lang: str = "en") -> dict:
    """{"text", "source": "llm" | "template", "model", "rejected": [numbers not in the JSON]}.
    The LLM text is used only if every number in it can be found in the card JSON (ai/checks.py)."""
    meta = {"source": "template", "model": None, "rejected": []}
    try:
        msg = llm.chat([
            {"role": "system", "content": SYSTEM.format(language=LANG.get(lang, "English"))},
            {"role": "user", "content": json.dumps(card, default=str)},
        ])
        text = (msg.content or "").strip()
        bad = unsupported_numbers(text, card)
        if text and not bad:
            return {"text": text, "source": "llm", "model": llm.model_name(), "rejected": []}
        meta["rejected"] = bad
    except Exception:  # noqa: BLE001  LLMUnavailable, network, quota ... -> deterministic text
        pass
    return {"text": template_narrative(card, lang), **meta}


def narrate(card: dict, lang: str = "en") -> str:
    return narrate_with_meta(card, lang)["text"]


def template_narrative(card: dict, lang: str = "en") -> str:
    p, v, l, a = card["price"], card["volume"], card["liquidity"], card["participants"]
    o = (card.get("intraday") or {}).get("onset") or {}
    au = card.get("auctions") or {}
    cmp = card.get("comparison") or {}
    f = formatters(lang)
    _p, _pctile = f["pct"], f["pctile"]
    if lang == "de":
        t = (f"{card['name']} veränderte sich am {f['date'](card['event']['reaction_day'])} um {_p(p['ret'])}, "
             f"die {card['index']}-Vergleichswerte um {_p(p['peer_ret'])} (unternehmensspezifisch: {_p(p['abn_ret'])}). "
             f"Der Umsatz lag beim {f['x'](v['ratio'] or 0)}en des Normalniveaus. ")
        if l["ratio"]:
            t += (f"Die Liquiditätskosten (XLM 25k) lagen bei {f['bps'](l['xlm_25k_bps'])} "
                  f"(das {f['x'](l['ratio'])}e des Normalwerts). ")
        if a["agent_aggr_imbalance"] is not None:
            side = "Verkaufs" if a["agent_aggr_imbalance"] < 0 else "Kauf"
            t += f"Agentenorders zeigten einen {side}überhang von {f['pct0'](abs(a['agent_aggr_imbalance']))}."
        if o.get("time"):
            t += f" Der Markt begann die Nachricht um {o['time']} Uhr einzupreisen ({_p(o['ret_at_onset'])})."
        if au.get("close_auction_ratio") is not None:
            t += (f" Die Schlussauktion war {f['x'](au['close_auction_ratio'])} so groß wie normal und "
                  f"bewegte den Kurs um {_p(au['close_auction_move'])} gegenüber dem letzten Handel.")
        if cmp and cmp.get("abs_abn_ret_pctile") is not None:
            t += (f" Im Vergleich mit {cmp['n']} {group_label(cmp, 'de')}, war die unternehmensspezifische "
                  f"Bewegung {'die größte von allen' if cmp['abs_abn_ret_pctile'] == 1.0 else 'größer als bei ' + _pctile(cmp['abs_abn_ret_pctile']) + ' von ihnen'}.")
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
    if cmp and cmp.get("abs_abn_ret_pctile") is not None:
        move = ("the biggest of them" if cmp["abs_abn_ret_pctile"] == 1.0
                else f"bigger than {_pctile(cmp['abs_abn_ret_pctile'])} of them")
        t += f" Compared with {cmp['n']} {cmp['group']}, the stock-specific move was {move}."
    return t
