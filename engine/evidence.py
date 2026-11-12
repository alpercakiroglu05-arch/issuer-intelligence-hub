"""
Evidence brief and explanation check for one impact card.  OWNER: C3 (web) with C2 definitions.  Deterministic.

    brief(isin, day, event=None, card=None) -> {"en": {...}, "de": {...}, "facts": {...}}
        per language: {"headline", "sections": [{"key", "title", "points": [str]}],
                       "claims": {claim_id: {"label", "verdict", "text", "better"}}}

Why: an IR manager has to explain a move to the board. The brief answers, in this order: what changed, what
the broader market did, what was distinctive about trading, how unusual it was, what the data cannot tell,
and what to check next. The claims check takes the explanations IR typically hears ("it was the market",
"it was thin trading", "funds sold") and tests each one against the same card figures:

    supported      the data is consistent with it (association, never proof of a cause)
    contradicted   the data speaks against it
    partly         some of it holds
    not_testable   the data cannot answer it (e.g. investor identities are not in Xetra data)

Every figure comes from the impact card (engine/impact.py), engine.compare.day_ratios (the same baseline
as the card) or engine.baseline.market_context. Nothing is estimated here and no cause is invented:
an announcement is named only when the calendar lists it.
"""
import math
import re

import pandas as pd

from engine import baseline, compare, data, impact
from report.fmt import formatters

PRE_DAYS = 5            # trading days before the reaction day checked for unusual activity
PRE_VOL_FLAG = 2.0      # x normal turnover before the news worth asking about
VERDICTS = ("supported", "contradicted", "partly", "not_testable")
CLAIMS = ("market", "announcement", "thin", "technical", "investors", "overreaction", "leak")
CLAIM_LABEL = {
    "market": ("“It was the overall market.”", "„Das lag am Gesamtmarkt.“"),
    "announcement": ("“It was the reaction to our announcement.”", "„Das war die Reaktion auf unsere Meldung.“"),
    "thin": ("“Thin trading exaggerated the move.”", "„Dünner Handel hat die Bewegung übertrieben.“"),
    "technical": ("“Index trades or option expiry drove it.”", "„Indextrades oder Verfall haben das ausgelöst.“"),
    "investors": ("“Funds / short sellers sold.”", "„Fonds bzw. Leerverkäufer haben verkauft.“"),
    "overreaction": ("“It was an overreaction that has reversed.”", "„Das war eine Übertreibung, die sich umgekehrt hat.“"),
    "leak": ("“There was unusual trading before the news.”", "„Vor der Meldung wurde auffällig gehandelt.“"),
}
CTX_WORDS = {
    "index_event": ("an index inclusion or deletion (index funds trade at the close)",
                    "eine Indexaufnahme oder -streichung (Indexfonds handeln in der Schlussauktion)"),
    "index_change": ("a change of its DAX/MDAX/SDAX membership", "ein Wechsel der DAX/MDAX/SDAX-Zugehörigkeit"),
    "quarterly_expiry": ("a quarterly options and futures expiry", "ein großer Verfallstag"),
    "monthly_expiry": ("a monthly options expiry", "ein monatlicher Verfallstag"),
    "month_end_review": ("an index review date", "ein Index-Review-Tag"),
    "market_wide_volume": ("a market-wide high-volume day (at least a quarter of all shares traded 2x normal)",
                           "ein marktweiter Umsatztag (mindestens ein Viertel aller Aktien mit doppeltem Umsatz)"),
}
TECHNICAL = {"index_event", "index_change", "quarterly_expiry", "monthly_expiry", "month_end_review"}
_MON = {"en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "de": ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez."]}


def _ok(v) -> bool:
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def _d(day, lang):
    t = pd.Timestamp(day)
    return f"{t.day}. {_MON['de'][t.month - 1]}" if lang == "de" else f"{t.day} {_MON['en'][t.month - 1]}"


def _facts(isin: str, day: str, card: dict) -> dict:
    """The extra figures the brief needs beyond the card, all from the engine."""
    d = pd.Timestamp(day)
    canon = compare.day_ratios(isin)
    dates = list(canon.index)
    i = dates.index(d) if d in dates else None
    pre = canon.iloc[max(0, i - PRE_DAYS): i] if i is not None else canon.iloc[0:0]
    # a busy day the market explains (option expiry, index change or review, market-wide volume) is no hint of
    # early news: EVD 20 Mar 2026 (quarterly expiry) had 2.0x normal turnover a week before the FY results
    # ... and neither is a day with the company's own earlier announcement (HDD 15 Apr 2026: 17.1x after the
    # report of 14 Apr and before the guidance cut published that evening)
    ev = data.events()
    ev = ev[ev["isin"] == isin]
    known = {pd.Timestamp(x).normalize() for col in ("date", "reaction_day") for x in ev[col].dropna()}
    own = pre[[not baseline.market_context(isin, str(t.date())) and t.normalize() not in known
               for t in pre.index]] if len(pre) else pre
    pk = own["vol_ratio"].idxmax() if len(own) and own["vol_ratio"].notna().any() else None
    post_days = len(dates) - 1 - i if i is not None else 0
    return {
        "context": baseline.market_context(isin, day),
        "pre_days": len(pre),
        "pre_max_vol_ratio": None if pk is None else float(pre.loc[pk, "vol_ratio"]),
        "pre_max_vol_day": None if pk is None else str(pk.date()),
        "pre_abn_ret_sum": float(pre["abn_ret"].sum()) if len(pre) else None,
        "post_days_available": int(post_days),
    }


def brief(isin: str, day: str, event: dict | None = None, card: dict | None = None) -> dict:
    card = card or impact.impact_card(isin, day, event)
    day = card["event"]["reaction_day"]
    fx = _facts(isin, day, card)
    return {"en": _build(card, fx, "en"), "de": _build(card, fx, "de"), "facts": fx}


def _build(c: dict, fx: dict, lang: str) -> dict:  # noqa: C901  one readable list of rules
    de = lang == "de"
    f = formatters(lang)
    T = (lambda en, d: d) if de else (lambda en, d: en)  # noqa: E731
    p, v, li, au, pa = c["price"], c["volume"], c["liquidity"], c.get("auctions") or {}, c["participants"]
    e, cm, idx = c["event"], c.get("comparison") or {}, c["index"]
    intr = c.get("intraday") or {}
    on = intr.get("onset") or {}
    name = data.display_name(c["isin"])
    day = e["reaction_day"]
    has_event = e.get("type") not in (None, "NOTABLE_DAY") and e.get("event_id")
    own = str(e.get("event_id") or "").startswith("USR_")
    ret, peer, abn, z = p.get("ret"), p.get("peer_ret"), p.get("abn_ret"), p.get("abn_ret_z")
    big_move = _ok(abn) and _ok(z) and abs(z) >= 2
    pub_time = (e.get("datetime_local") or "")[11:16] or None
    lag = on.get("lag_minutes")
    car = p.get("car_0_5")

    # ---------- headline ----------
    if _ok(ret) and _ok(abn):
        head = T(f"{name} moved {f['pct'](ret)} on {_d(day, lang)}; {f['pct'](abn)} of that was stock-specific, "
                 f"on {f['x'](v['ratio'])} normal turnover.",
                 f"{name} bewegte sich am {_d(day, lang)} um {f['pct'](ret)}; davon waren {f['pct'](abn)} "
                 f"titelspezifisch, bei {f['x'](v['ratio'])} normalem Umsatz.")
    else:
        head = T(f"{name} on {_d(day, lang)}: not enough data for a full brief.",
                 f"{name} am {_d(day, lang)}: zu wenig Daten für eine vollständige Übersicht.")

    # ---------- 1 what changed ----------
    changed = []
    if _ok(ret):
        changed.append(T(f"The share closed {f['pct'](ret)} (closing auction vs the previous close); the other {idx} "
                         f"members moved {f['pct'](peer)} (equal-weighted average). Stock-specific move: {f['pct'](abn)}"
                         + (f", {abs(z):.1f}x its normal daily stock-specific move." if _ok(z) else "."),
                         f"Die Aktie schloss {f['pct'](ret)} (Schlussauktion vs. Vortag); die übrigen {idx}-Werte "
                         f"bewegten sich um {f['pct'](peer)} (gleichgewichteter Durchschnitt). Titelspezifisch: {f['pct'](abn)}"
                         + (f", das {abs(z):.1f}-Fache der normalen Tagesbewegung.".replace(".", ",", 1) if _ok(z) else ".")))
    if _ok(v.get("ratio")):
        changed.append(T(f"Turnover {f['eur'](v['turnover_eur'])}, {f['x'](v['ratio'])} the normal "
                         f"{f['eur'](v['baseline_eur'])} (median of {c['baseline']['days_used']} trading days, t-65 to t-6).",
                         f"Umsatz {f['eur'](v['turnover_eur'])}, das {f['x'](v['ratio'])}e des normalen Werts von "
                         f"{f['eur'](v['baseline_eur'])} (Median aus {c['baseline']['days_used']} Handelstagen, t-65 bis t-6)."))
    if _ok(li.get("ratio")):
        back = (T(f" Back to normal after {li['days_to_normal']} trading day(s).",
                  f" Nach {li['days_to_normal']} Handelstag(en) wieder normal.") if _ok(li.get("days_to_normal"))
                else T(" Not back to normal within 20 trading days (or the data ends first).",
                       " Innerhalb von 20 Handelstagen nicht wieder normal (oder die Daten enden vorher)."))
        changed.append(T(f"Cost of a round trip of EUR 25k (XLM, spread plus price impact): {f['bps'](li['xlm_25k_bps'])} "
                         f"vs {f['bps'](li['xlm_25k_baseline_bps'])} normal ({f['x'](li['ratio'])}).",
                         f"Kosten für Kauf und Verkauf von 25 T€ (XLM, Spread plus Preiseinfluss): "
                         f"{f['bps'](li['xlm_25k_bps'])} vs. normal {f['bps'](li['xlm_25k_baseline_bps'])} "
                         f"({f['x'](li['ratio'])}).") + back)
    if _ok(car):
        changed.append(T(f"Day 0 to day +5, the stock-specific move added up to {f['pct'](car)}.",
                         f"Von Tag 0 bis Tag +5 summierte sich die titelspezifische Bewegung auf {f['pct'](car)}."))
    else:
        changed.append(T(f"Day +5 lies after the end of the data ({fx['post_days_available']} trading day(s) "
                         "available), so the follow-through is not measured yet.",
                         f"Tag +5 liegt nach dem Datenende ({fx['post_days_available']} Handelstag(e) vorhanden); "
                         "der weitere Verlauf ist noch nicht messbar."))

    # ---------- 2 broader market ----------
    market = []
    if _ok(ret) and _ok(peer):
        if ret != 0 and peer * ret > 0 and abs(peer) >= 0.6 * abs(ret):
            market.append(T(f"The {idx} peers moved in the same direction by a similar amount ({f['pct'](peer)}): "
                            "most of the move was market-wide.",
                            f"Die {idx}-Werte bewegten sich ähnlich stark in dieselbe Richtung ({f['pct'](peer)}): "
                            "der Großteil war marktweit."))
        else:
            market.append(T(f"The {idx} peers moved {f['pct'](peer)}, so the market explains little of the "
                            f"{f['pct'](ret)} move.",
                            f"Die {idx}-Werte bewegten sich um {f['pct'](peer)}; der Markt erklärt wenig von der "
                            f"Bewegung um {f['pct'](ret)}."))
    ctx = fx["context"]
    if ctx:
        market.append(T("Market mechanics on this day: " + "; ".join(CTX_WORDS[k][0] for k in ctx if k in CTX_WORDS)
                        + ". These move volume without company news.",
                        "Marktmechanik an diesem Tag: " + "; ".join(CTX_WORDS[k][1] for k in ctx if k in CTX_WORDS)
                        + ". Sie bewegen Umsatz ohne Unternehmensnachricht."))
    else:
        market.append(T("No index change, option expiry, index review or market-wide volume day on this date.",
                        "Kein Indexwechsel, Verfallstag, Index-Review oder marktweiter Umsatztag an diesem Datum."))

    # ---------- 3 distinctive trading ----------
    trading = []
    if _ok(au.get("open_auction_ratio")):
        trading.append(T(f"Opening auction: {f['x'](au['open_auction_ratio'])} normal turnover; it priced the share "
                         f"{f['pct'](au.get('open_auction_move'))} vs the previous close "
                         f"(typical ±{f['pct1'](au.get('open_auction_move_baseline_abs'))}).",
                         f"Eröffnungsauktion: das {f['x'](au['open_auction_ratio'])}e des normalen Umsatzes; Kurs "
                         f"{f['pct'](au.get('open_auction_move'))} vs. Vortag (üblich ±{f['pct1'](au.get('open_auction_move_baseline_abs'))})."))
    if _ok(au.get("close_auction_eur")):
        trading.append(T(f"Closing auction: {f['eur'](au['close_auction_eur'])} ({f['x'](au.get('close_auction_ratio'))} normal), "
                         f"{f['pct0'](au.get('close_auction_share'))} of the day's turnover (normal "
                         f"{f['pct0'](au.get('close_auction_share_baseline'))}); it set the price "
                         f"{f['pct'](au.get('close_auction_move'))} vs the last trade (typical ±{f['pct1'](au.get('close_auction_move_baseline_abs'))}).",
                         f"Schlussauktion: {f['eur'](au['close_auction_eur'])} ({f['x'](au.get('close_auction_ratio'))} normal), "
                         f"{f['pct0'](au.get('close_auction_share'))} des Tagesumsatzes (normal "
                         f"{f['pct0'](au.get('close_auction_share_baseline'))}); Preis {f['pct'](au.get('close_auction_move'))} "
                         f"vs. letztem Handel (üblich ±{f['pct1'](au.get('close_auction_move_baseline_abs'))})."))
    imb, ib = pa.get("agent_aggr_imbalance"), pa.get("agent_aggr_imbalance_baseline")
    if _ok(imb):
        side = T("net sellers", "per Saldo Verkäufer") if imb < 0 else T("net buyers", "per Saldo Käufer")
        trading.append(T(f"Client orders routed by brokers (AGENT) were {side}: {f['spct0'](imb)} of their aggressive "
                         f"turnover (normal {f['spct0'](ib)}), {f['eur'](abs(pa.get('agent_aggr_net_eur') or 0))} net.",
                         f"Kundenorders über Broker (AGENT) waren {side}: {f['spct0'](imb)} ihres aggressiven Umsatzes "
                         f"(normal {f['spct0'](ib)}), netto {f['eur'](abs(pa.get('agent_aggr_net_eur') or 0))}."))
    if on.get("time"):
        s = T(f"Trading reaction detected at {on['time']} (inferred from trades: price beyond 2 sigma and turnover "
              f"3x normal for the time of day).",
              f"Handelsreaktion erkannt um {on['time']} (aus den Trades abgeleitet: Kurs jenseits 2 Sigma und Umsatz "
              f"3-fach normal für die Tageszeit).")
        if pub_time and _ok(lag):
            s += T(f" That is {lag} min after the published time {pub_time}." if lag >= 0 else
                   f" That is {abs(lag)} min BEFORE the published time {pub_time}.",
                   f" Das ist {lag} Min. nach der veröffentlichten Zeit {pub_time}." if lag >= 0 else
                   f" Das ist {abs(lag)} Min. VOR der veröffentlichten Zeit {pub_time}.")
        vi = on.get("volatility_interruptions") or []
        if vi:
            s += T(f" {len(vi)} volatility interruption(s): {', '.join(vi)}.",
                   f" {len(vi)} Volatilitätsunterbrechung(en): {', '.join(vi)}.")
        trading.append(s)
    elif not intr:
        trading.append(T("No minute data for this share: the intraday path and onset are not available.",
                         "Keine Minutendaten für diese Aktie: Intraday-Verlauf und Reaktionsbeginn fehlen."))
    if "flow_censored" in (c.get("flags") or []):
        trading.append(T("Participant flows for this day are withheld by Xetra (fewer than 7 trades).",
                         "Teilnehmerflüsse für diesen Tag hält Xetra zurück (unter 7 Trades)."))

    # ---------- 4 how unusual ----------
    unusual = []
    if cm:
        grp_type = cm.get("group_type")
        lab = T("unusual trading days", "auffälligen Handelstagen") if grp_type == "NOTABLE_DAY" else T(f"{grp_type} events", f"{grp_type}-Ereignissen")
        where = T("DAX, MDAX and SDAX", "DAX, MDAX und SDAX") if cm.get("group_index") == "DAX+MDAX+SDAX" else cm.get("group_index")
        rank_of = cm.get("rank_of") or (cm["n"] + 1 if isinstance(cm.get("n"), int) else None)
        if cm.get("rank_abs_abn_ret") and rank_of:
            unusual.append(T(f"Rank {cm['rank_abs_abn_ret']} of {rank_of} {lab} in {where} (Jan–Oct 2026, this day included) "
                             f"by size of the stock-specific move; turnover higher than {f['pctile'](cm.get('vol_ratio_pctile'))} of them.",
                             f"Rang {cm['rank_abs_abn_ret']} von {rank_of} {lab} in {where} (Jan.–Okt. 2026, inkl. dieses Tages) "
                             f"nach Größe der titelspezifischen Bewegung; Umsatz höher als bei {f['pctile'](cm.get('vol_ratio_pctile'))}."))
        if has_event and grp_type != e.get("type"):
            unusual.append(T(f"Fewer than 5 comparable {e['type']} events with data, so the ranking uses unusual "
                             "trading days instead (a broader, different group).",
                             f"Weniger als 5 vergleichbare {e['type']}-Ereignisse mit Daten, daher Einordnung unter "
                             "auffälligen Handelstagen (eine breitere, andere Gruppe)."))
    else:
        unusual.append(T("No comparison group with at least 5 events.", "Keine Vergleichsgruppe mit mindestens 5 Ereignissen."))

    # ---------- 5 what remains unknown ----------
    unknown = []
    if has_event:
        status = (T("from your own calendar, not checked against a source", "aus Ihrem eigenen Kalender, nicht mit einer Quelle geprüft")
                  if own else T("date and time checked against the linked source", "Datum und Uhrzeit mit der verlinkten Quelle geprüft"))
        unknown.append(T(f"The calendar lists “{e['title']}” ({status}). The timing is consistent with it, but trading "
                         "data shows association, not cause.",
                         f"Der Kalender nennt „{e['title']}“ ({status}). Das Timing passt dazu, aber Handelsdaten "
                         "zeigen einen Zusammenhang, keine Ursache."))
    else:
        unknown.append(T("No calendar entry for this day: the cause is not in the data and is not guessed here.",
                         "Kein Kalendereintrag für diesen Tag: Die Ursache steht nicht in den Daten und wird hier nicht geraten."))
    unknown.append(T("Who the sellers and buyers were: Xetra flows only split client orders (AGENT), proprietary trading "
                     "and market makers. They do not identify funds, retail investors or short sellers.",
                     "Wer verkauft und gekauft hat: Xetra-Flows trennen nur Kundenorders (AGENT), Eigenhandel und "
                     "Market Maker. Fonds, Privatanleger oder Leerverkäufer sind nicht erkennbar."))
    unknown.append(T("Trading on other venues and off-exchange is not in the data (Xetra order book only).",
                     "Handel an anderen Plätzen und außerbörslich ist nicht in den Daten (nur Xetra-Orderbuch)."))
    if has_event and not pub_time:
        unknown.append(T("The publication time is not known, so the reaction cannot be timed against it.",
                         "Die Veröffentlichungszeit ist unbekannt; die Reaktion lässt sich nicht daran messen."))

    # ---------- 6 what to check next ----------
    nxt = []
    if not has_event:
        nxt.append(T(f"Check news wires, analyst notes and the ad hoc archive for {_d(day, lang)} and the evening before.",
                     f"Nachrichten, Analystenkommentare und Ad-hoc-Archiv für den {_d(day, lang)} und den Vorabend prüfen."))
    if _ok(lag) and lag < 0:
        nxt.append(T("Trading moved before the published time in the calendar: check that time against the source.",
                     "Der Handel reagierte vor der Zeit im Kalender: diese Zeit mit der Quelle abgleichen."))
    if _ok(fx["pre_max_vol_ratio"]) and fx["pre_max_vol_ratio"] >= PRE_VOL_FLAG:
        nxt.append(T(f"Turnover was already {f['x'](fx['pre_max_vol_ratio'])} normal on {_d(fx['pre_max_vol_day'], lang)}, "
                     "before this day: check whether earlier public news explains it.",
                     f"Der Umsatz lag schon am {_d(fx['pre_max_vol_day'], lang)} beim {f['x'](fx['pre_max_vol_ratio'])}en "
                     "des Normalwerts: prüfen, ob frühere öffentliche Nachrichten das erklären."))
    if _ok(imb) and abs(imb) >= 0.25:
        nxt.append(T("Ask your brokers and the Designated Sponsor which client groups drove the "
                     f"{'selling' if imb < 0 else 'buying'}; exchange data cannot name them.",
                     f"Broker und Designated Sponsor fragen, welche Kundengruppen {'verkauft' if imb < 0 else 'gekauft'} "
                     "haben; Börsendaten nennen sie nicht."))
    if _ok(li.get("ratio")) and li["ratio"] >= 1.5 and not (_ok(li.get("days_to_normal")) and li["days_to_normal"] <= 3):
        nxt.append(T("Trading cost stayed high: discuss quote quality with the Designated Sponsor.",
                     "Handelskosten blieben hoch: Quotierungsqualität mit dem Designated Sponsor besprechen."))
    cam, cab = au.get("close_auction_move"), au.get("close_auction_move_baseline_abs")
    if _ok(cam) and _ok(cab) and cab > 0 and abs(cam) >= 3 * cab and abs(cam) >= 0.005:
        nxt.append(T(f"The closing auction moved the price {f['pct'](cam)} vs the last trade, several times the usual "
                     "amount: look at the auction imbalance.",
                     f"Die Schlussauktion bewegte den Kurs um {f['pct'](cam)} vs. letztem Handel, ein Vielfaches des "
                     "Üblichen: Auktionsungleichgewicht prüfen."))
    if _ok(car) and _ok(abn) and car * abn > 0 and abs(car) >= 1.2 * abs(abn):
        nxt.append(T(f"The stock-specific move kept going for five days ({f['pct'](car)}): watch whether investors are still repositioning.",
                     f"Die titelspezifische Bewegung setzte sich fünf Tage fort ({f['pct'](car)}): beobachten, ob Investoren noch umschichten."))
    if not nxt:
        nxt.append(T("Compare this day with other events of the same type before drawing conclusions.",
                     "Diesen Tag vor Schlussfolgerungen mit gleichartigen Ereignissen vergleichen."))

    # ---------- explanation check ----------
    claims = {}

    def put(k, verdict, text, better=None):
        assert verdict in VERDICTS
        claims[k] = {"label": CLAIM_LABEL[k][1 if de else 0], "verdict": verdict, "text": text, "better": better}

    stock_specific = T(f"{name} moved {f['pct'](ret)} while the {idx} peers moved {f['pct'](peer)}; the "
                       f"stock-specific part was {f['pct'](abn)}",
                       f"{name} bewegte sich um {f['pct'](ret)}, die {idx}-Werte um {f['pct'](peer)}; titelspezifisch "
                       f"waren es {f['pct'](abn)}") if _ok(ret) and _ok(peer) else None
    # market
    if not _ok(ret) or not _ok(peer):
        put("market", "not_testable", T("No return data for this day.", "Keine Renditedaten für diesen Tag."))
    elif ret != 0 and peer * ret > 0 and abs(peer) >= 0.6 * abs(ret):
        put("market", "supported", T(f"Peers moved {f['pct'](peer)} against the share's {f['pct'](ret)}: most of the move was market-wide.",
                                     f"Die Vergleichswerte bewegten sich um {f['pct'](peer)} gegenüber {f['pct'](ret)} der Aktie: der Großteil war marktweit."))
    elif big_move:
        put("market", "contradicted", stock_specific + T(". The market explains little of it.", ". Der Markt erklärt davon wenig."),
            better=stock_specific + T(", well beyond its normal daily range.", ", weit außerhalb der normalen Tagesschwankung."))
    else:
        put("market", "partly", stock_specific + ".", better=stock_specific + ".")
    # announcement
    if has_event:
        if _ok(lag) and lag < 0:
            put("announcement", "partly", T(f"The calendar lists “{e['title']}”, but trading reacted {abs(lag)} min before the published time {pub_time}.",
                                            f"Der Kalender nennt „{e['title']}“, aber der Handel reagierte {abs(lag)} Min. vor der veröffentlichten Zeit {pub_time}."))
        else:
            when = (T(f", and trading reacted {lag} min after publication", f", und der Handel reagierte {lag} Min. nach der Veröffentlichung")
                    if _ok(lag) and lag >= 0 else "")
            put("announcement", "supported",
                T(f"The calendar lists “{e['title']}” for this reaction day{when}. Timing is consistent; it is an association, not proof.",
                  f"Der Kalender nennt „{e['title']}“ für diesen Reaktionstag{when}. Das Timing passt; das ist ein Zusammenhang, kein Beweis."),
                better=(stock_specific + T(f", on the trading day after “{e['title']}”." if e.get("timing") == "post_close" else f", on the day of “{e['title']}”.",
                                           f", am Handelstag nach „{e['title']}“." if e.get("timing") == "post_close" else f", am Tag von „{e['title']}“."))
                if stock_specific else None)
    else:
        put("announcement", "not_testable", T("No calendar entry for this day. Add the announcement to your calendar to test it.",
                                              "Kein Kalendereintrag für diesen Tag. Meldung im eigenen Kalender ergänzen, um das zu prüfen."))
    # thin trading
    vr, xr = v.get("ratio"), li.get("ratio")
    if not _ok(vr):
        put("thin", "not_testable", T("No turnover baseline for this day.", "Keine Umsatzbasis für diesen Tag."))
    elif vr >= 2:
        put("thin", "contradicted", T(f"Turnover was {f['x'](vr)} normal: the move happened on heavy, not thin, trading.",
                                      f"Der Umsatz lag beim {f['x'](vr)}en des Normalwerts: Die Bewegung kam bei starkem, nicht dünnem Handel."),
            better=T(f"The move came on {f['x'](vr)} normal turnover.", f"Die Bewegung kam bei {f['x'](vr)} normalem Umsatz."))
    elif vr < 1.2 and _ok(xr) and xr >= 1.5:
        put("thin", "supported", T(f"Turnover was only {f['x'](vr)} normal while trading cost was {f['x'](xr)} normal: thin conditions.",
                                   f"Umsatz nur {f['x'](vr)} normal bei {f['x'](xr)} Handelskosten: dünne Bedingungen."))
    else:
        put("thin", "partly", T(f"Turnover {f['x'](vr)} normal, trading cost {f['x'](xr)} normal: no clear sign either way.",
                                f"Umsatz {f['x'](vr)} normal, Handelskosten {f['x'](xr)} normal: kein klares Zeichen."))
    # technical
    tech = [k for k in ctx if k in TECHNICAL]
    if tech:
        put("technical", "supported", T("This day was " + "; ".join(CTX_WORDS[k][0] for k in tech) + ". That can move volume without company news.",
                                        "Dieser Tag war " + "; ".join(CTX_WORDS[k][1] for k in tech) + ". Das bewegt Umsatz ohne Unternehmensnachricht."))
    else:
        put("technical", "contradicted", T("No index change, index review or option expiry on this day.",
                                           "Kein Indexwechsel, Index-Review oder Verfallstag an diesem Tag."))
    # investors
    flow = (T(f" What the data does show: client orders (AGENT) were {'net sellers' if imb < 0 else 'net buyers'} ({f['spct0'](imb)}).",
              f" Was die Daten zeigen: Kundenorders (AGENT) waren per Saldo {'Verkäufer' if imb < 0 else 'Käufer'} ({f['spct0'](imb)}).")
            if _ok(imb) else "")
    put("investors", "not_testable", T("Xetra data does not identify funds, retail investors or short sellers." + flow,
                                       "Xetra-Daten erkennen keine Fonds, Privatanleger oder Leerverkäufer." + flow),
        better=T("Client orders via brokers were " + ("net sellers" if _ok(imb) and imb < 0 else "net buyers") + "; the investor types are not visible in exchange data.",
                 "Kundenorders über Broker waren per Saldo " + ("Verkäufer" if _ok(imb) and imb < 0 else "Käufer") + "; Investorentypen sind in Börsendaten nicht sichtbar.") if _ok(imb) else None)
    # overreaction
    if not _ok(car) or not _ok(abn) or abn == 0:
        put("overreaction", "not_testable", T("The five days after are not all in the data yet.", "Die fünf Folgetage sind noch nicht alle in den Daten."))
    elif car * abn > 0 and abs(car) >= 0.8 * abs(abn):
        put("overreaction", "contradicted", T(f"No reversal within five days: day 0 to +5 adds up to {f['pct'](car)} vs {f['pct'](abn)} on the day.",
                                              f"Keine Umkehr binnen fünf Tagen: Tag 0 bis +5 ergibt {f['pct'](car)} vs. {f['pct'](abn)} am Tag."))
    elif abs(car) < 0.5 * abs(abn) or car * abn < 0:
        put("overreaction", "supported", T(f"Largely reversed: day 0 to +5 adds up to {f['pct'](car)} vs {f['pct'](abn)} on the day.",
                                           f"Weitgehend umgekehrt: Tag 0 bis +5 ergibt {f['pct'](car)} vs. {f['pct'](abn)} am Tag."))
    else:
        put("overreaction", "partly", T(f"Partly reversed: day 0 to +5 adds up to {f['pct'](car)} vs {f['pct'](abn)} on the day.",
                                        f"Teilweise umgekehrt: Tag 0 bis +5 ergibt {f['pct'](car)} vs. {f['pct'](abn)} am Tag."))
    # leak / pre-news trading
    pre = fx["pre_max_vol_ratio"]
    if _ok(lag) and lag < 0:
        put("leak", "supported", T(f"Trading reacted {abs(lag)} min before the time in the calendar ({pub_time}). "
                                   "Check that time against the source; the data does not show why.",
                                   f"Der Handel reagierte {abs(lag)} Min. vor der Zeit im Kalender ({pub_time}). "
                                   "Diese Zeit mit der Quelle abgleichen; die Daten zeigen nicht, warum."))
    elif _ok(pre) and pre >= PRE_VOL_FLAG:
        put("leak", "partly", T(f"Turnover reached {f['x'](pre)} normal on {_d(fx['pre_max_vol_day'], lang)}, in the {fx['pre_days']} days before, with no announcement or market event on that day. The data does not show why.",
                                f"Der Umsatz erreichte am {_d(fx['pre_max_vol_day'], lang)} das {f['x'](pre)}e des Normalwerts, in den {fx['pre_days']} Tagen davor, ohne Meldung oder Marktereignis an diesem Tag. Die Daten zeigen nicht, warum."))
    elif _ok(pre):
        put("leak", "contradicted", T(f"In the {fx['pre_days']} trading days before, turnover stayed at most {f['x'](pre)} normal"
                                      + (", and trading reacted after the published time." if _ok(lag) else "."),
                                      f"In den {fx['pre_days']} Handelstagen davor lag der Umsatz höchstens beim {f['x'](pre)}en des Normalwerts"
                                      + (", und der Handel reagierte nach der Veröffentlichung." if _ok(lag) else ".")))
    else:
        put("leak", "not_testable", T("No trading days before this one in the data.", "Keine Handelstage davor in den Daten."))

    titles = {"changed": T("What changed", "Was sich verändert hat"), "market": T("What the broader market did", "Was der Gesamtmarkt tat"),
              "trading": T("What was distinctive about trading", "Was am Handel auffiel"), "unusual": T("How unusual it was", "Wie ungewöhnlich es war"),
              "unknown": T("What the data cannot tell", "Was die Daten nicht sagen"), "next": T("What to check next", "Was als Nächstes zu prüfen ist")}
    secs = [("changed", changed), ("market", market), ("trading", trading), ("unusual", unusual), ("unknown", unknown), ("next", nxt)]
    return {"headline": head, "sections": [{"key": k, "title": titles[k], "points": pts} for k, pts in secs],
            "claims": claims}


# which checks a free-text explanation touches (EN/DE keywords). The same list is in web/app.js (CLAIM_RX).
CLAIM_RX = {
    "market": r"\b(whole|overall|broad|general|entire) market|market[- ](sell-?off|fell|fall|drop|decline|weak|was down|rout|turmoil)"
              r"|it was the market|was (this|it) (just )?the market|(just|only|simply) the market|war das (nur )?der markt|nur der markt|sector|industry|macro|interest rate|peers (fell|dropped|were down)|everyone|all stocks"
              r"|gesamtmarkt|marktschwäche|markt (fiel|brach|war schwach)|sektor|branche|konjunktur|zinsen|lag am markt",
    "announcement": r"result|earning|announc|guidance|ad.?hoc|dividend|figures|numbers|outlook|quarterly|report"
                    r"|ergebnis|zahlen|meldung|prognose|dividende|ausblick|quartal|bericht",
    "thin": r"thin|illiquid|low (volume|liquidity|turnover)|lack of liquidity|few trades|dünn|geringe[rn]? (umsatz|liquidität)"
            r"|wenig umsatz|mangelnde liquidität",
    "technical": r"rebalanc|index (inclusion|deletion|change|review|fund|trade)|expir|witching|msci|stoxx|ftse|verfall"
                 r"|indexänderung|indexaufnahme|indexstreichung|indexfonds|option|future|derivat",
    "investors": r"fund|institution|hedge|short|investor|retail|block (sale|trade)|placement|fonds|leerverk|anleger|privat"
                 r"|institutionell|platzierung",
    "overreaction": r"overreact|over-react|recover|bounce|revers|rebound|übertr|erhol|gegenbewegung|korrektur",
    "leak": r"leak|before the (news|announcement|release)|insider|front.?run|in advance|ahead of the|vorab"
            r"|vor der (meldung|nachricht|veröffentlichung)|durchgestochen",
}


def classify(text: str) -> list[str]:
    """Claim ids a free-text explanation touches, in CLAIMS order."""
    return [k for k in CLAIMS if re.search(CLAIM_RX[k], text or "", flags=re.I)]
