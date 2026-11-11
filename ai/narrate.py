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
What the main fields mean (do not mix them up):
- price.ret = the share's own move that day; price.peer_ret = the average move of its index peers;
  price.abn_ret = the stock-specific move (ret minus peer_ret). These are three DIFFERENT numbers.
- price.gap_open = opening auction vs previous close; intraday.onset.ret_at_onset = move vs previous close
  at the onset minute (onset.time is a clock time during or before trading, read onset.session).
- volume.ratio = turnover / normal turnover; liquidity.xlm_25k_bps = trading cost of a EUR 25k order.
- liquidity.ratio > 1 means trading got MORE EXPENSIVE (liquidity got worse), < 1 cheaper.
- comparison.*_pctile = share of comparable days with a smaller value ("bigger than X % of them");
  a pctile of 1.0 means "the biggest of them" (never write "bigger than 100 %").
Write 4-5 short sentences in {language}:
1) start with: the share moved <price.ret>, its index peers <price.peer_ret>, so the stock-specific
   move was <price.abn_ret> (use these three numbers exactly in this meaning),
2) how unusual the trading activity was (volume vs. normal),
3) liquidity / spread and the opening/closing auctions (volume vs normal, auction price vs previous close / last trade),
4) who traded (agent = client/institutional orders, prop, market makers), only if notable,
5) if intraday.onset.time is set: when the market started pricing the news (that clock time),
6) if comparison is set: how this event ranks among comparable events (percentiles, group size).
Rules: use ONLY numbers that appear in the JSON. You may round them, write a share as a percent
(0.939 -> 93.9 %) and EUR amounts in millions (14521000 -> EUR 14.5m). NEVER compute a new number:
no differences, sums or averages, and no complements such as 'top 6 %' from a 0.939 percentile;
write 'bigger than 93 % of them' instead. Never invent causes; no investment advice; no predictions;
plain factual tone. Ratios: 'x times normal'."""

LANG = {"en": "English", "de": "German"}

# German number style (same as report/fmt.py); added to the DE prompt only, so the EN prompt and its cache stay as they are
SYSTEM_DE_STYLE = """
German number and date style (also in the first sentence): decimal comma, a space before %, the minus sign −,
e.g. 'um −23,2 %, die MDAX-Vergleichswerte um −1,5 % (unternehmensspezifisch: −21,7 %)';
dates as 27.03.2026; ratios as '8,6-fach'; amounts as '2,5 Mio. EUR' or '561 Tsd. EUR'; spreads in bps."""


def system_prompt(lang: str = "en") -> str:
    return SYSTEM.format(language=LANG.get(lang, "English")) + (SYSTEM_DE_STYLE if lang == "de" else "")


def narrate_with_meta(card: dict, lang: str = "en") -> dict:
    """{"text", "source": "llm" | "template", "model", "rejected": [numbers not in the JSON]}.
    The LLM text is used only if every number in it can be found in the card JSON (ai/checks.py)."""
    meta = {"source": "template", "model": None, "rejected": []}
    try:
        msg = llm.chat([
            {"role": "system", "content": system_prompt(lang)},
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
