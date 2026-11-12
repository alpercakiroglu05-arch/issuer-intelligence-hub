"""Numbers check (ai/checks.py) and the narrate fallback. No LLM and no data needed."""
from types import SimpleNamespace

CARD = {
    "name": "TEST AG", "index": "MDAX", "event": {"reaction_day": "2026-03-27"},
    "price": {"ret": -0.232025, "peer_ret": -0.015491, "abn_ret": -0.216534},
    "volume": {"ratio": 8.55, "turnover_eur": 113648900.0, "baseline_eur": 13296000.0},
    "liquidity": {"xlm_25k_bps": 24.12, "ratio": 1.28},
    "participants": {"agent_aggr_imbalance": -0.3615},
    "intraday": {"onset": {"time": "09:03", "ret_at_onset": -0.0455}},
    "comparison": {"n": 214, "rank_abs_abn_ret": 3, "abs_abn_ret_pctile": 0.991},
}


def test_numbers_check_accepts_numbers_from_the_json():
    from ai.checks import unsupported_numbers
    text = ("TEST AG fell 23.2% on 27.03.2026 (peers −1,5 %, stock-specific -21.7%). Turnover was 8.6x normal "
            "(€113.6m vs €13.3m), XLM 24 bps. Priced from 09:03. #3 of 215 MDAX days, bigger than 99% of them.")
    assert unsupported_numbers(text, CARD) == []


def test_numbers_check_rejects_invented_numbers():
    from ai.checks import unsupported_numbers
    assert unsupported_numbers("TEST AG fell 31.0% and 47.5% traded in the auction.", CARD) == ["31.0", "47.5"]


def test_llm_text_with_invented_number_falls_back_to_template(monkeypatch):
    from ai import llm, narrate
    monkeypatch.setattr(llm, "chat", lambda *a, **k: SimpleNamespace(content="TEST AG fell 31.4% today.", tool_calls=None))
    out = narrate.narrate_with_meta({**CARD, "auctions": {}, "comparison": None}, "en")
    assert out["source"] == "template" and out["rejected"] == ["31.4"]


def test_llm_text_with_only_known_numbers_is_used(monkeypatch):
    from ai import llm, narrate
    monkeypatch.setattr(llm, "chat", lambda *a, **k: SimpleNamespace(content="TEST AG fell 23.2%, 8.6x normal.", tool_calls=None))
    monkeypatch.setattr(llm, "model_name", lambda: "kolibri-1")
    out = narrate.narrate_with_meta(CARD, "en")
    assert out["source"] == "llm" and out["text"].startswith("TEST AG fell 23.2%")


def test_template_narrative_de_uses_german_number_and_date_format():
    from ai.checks import unsupported_numbers
    from ai.narrate import template_narrative
    card = {**CARD, "auctions": {"close_auction_ratio": 3.6, "close_auction_move": -0.0152},
            "comparison": {**CARD["comparison"], "group_type": "NOTABLE_DAY", "group_index": "MDAX",
                           "group": "unusual trading days, MDAX, Jan – Oct 2026",
                           "period_start": "2026-01-02", "period_end": "2026-10-30"}}
    de = template_narrative(card, "de")
    assert "−21,7 %" in de and "27.03.2026" in de and "8,6-fachen" in de
    assert "-21.7%" not in de and "2026-03-27" not in de
    assert "auffälligen Handelstagen, MDAX, Jan.–Okt. 2026" in de and "unusual" not in de
    assert unsupported_numbers(de, card) == []      # the numbers check understands the German style
    en = template_narrative(card, "en")
    assert "−21.7%" in en and "8.6×" in en and "2026-03-27" in en and "unusual trading days, MDAX, Jan – Oct 2026" in en


def test_numbers_check_understands_german_units():
    from ai.checks import unsupported_numbers
    text = "Umsatz 113,6 Mio. EUR statt 13,3 Mio. EUR (8,6-fach), Agenten −36 %, Rendite −23,2 % am 27.03.2026."
    assert unsupported_numbers(text, CARD) == []
    assert unsupported_numbers("Umsatz 47,5 Mio. EUR, 9,9-fach.", CARD) == ["47,5", "9,9"]


def test_numbers_check_accepts_percentiles_rounded_down():
    """The UI never rounds a percentile up (0.939 -> 'bigger than 93 %'), so the check must accept it."""
    from ai.checks import unsupported_numbers
    card = {"comparison": {"n": 214, "vol_ratio_pctile": 0.939}}
    assert unsupported_numbers("Turnover was bigger than 93% of 214 days.", card) == []


def test_numbers_check_rejects_complements():
    """'top 6 %' from a 0.939 percentile is a computed number, not one from the JSON."""
    from ai.checks import unsupported_numbers
    card = {"comparison": {"n": 214, "vol_ratio_pctile": 0.939}}
    assert unsupported_numbers("Turnover was in the top 6.1% of days.", card) == ["6.1"]


def test_assistant_answer_with_invented_number_falls_back(monkeypatch):
    """The assistant's answer must pass the numbers check against its context, else a safe answer is used."""
    import os
    from config import DATA_DIR
    if not (DATA_DIR / "daily_features.parquet").exists():
        import pytest
        pytest.skip("data missing")
    from ai import agent, llm
    from engine.data import isin_of
    calls = []
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "model_name", lambda: "test-model")
    monkeypatch.setattr(llm, "chat", lambda *a, **k: calls.append(1) or SimpleNamespace(
        content="Liquidity improved by 47.3%.", tool_calls=None))
    assert os.environ["LLM_CACHE"] == "false"      # conftest: no cached answer can stand in for the model
    out = agent.ask("Has our liquidity improved?", isin_of("EVD"))
    assert len(calls) == 2                         # the model was asked, and once more to repair the figure
    assert "47.3" not in out and "Stable" in out   # deterministic answer = liquidity_trend summary


def test_prompt_asks_for_german_number_style_in_de_only():
    from ai.narrate import LANG, SYSTEM, system_prompt
    assert system_prompt("en") == SYSTEM.format(language=LANG["en"])   # EN prompt (and its cache) unchanged
    de = system_prompt("de")
    assert "German" in de and "−23,2 %" in de and "27.03.2026" in de and "8,6-fach" in de and "Mio. EUR" in de


def test_meaning_check_share_move_must_be_the_own_return():
    """EVD 27.03: ret −23.2 %, abnormal −21.7 %. 'The share fell 21.7 %' mixes them up."""
    from ai.checks import meaning_errors
    assert meaning_errors("The share price fell 21.7% vs. the MDAX.", CARD)
    assert meaning_errors("The share moved −23.2%, its peers −1.5%, so the stock-specific move was −21.7%.", CARD) == []
    assert meaning_errors("Die Aktie verlor 21,7 % gegenüber dem MDAX.", CARD)
    assert meaning_errors("Die Aktie verlor 23,2 % gegenüber dem MDAX.", CARD) == []
    assert meaning_errors("The stock fell 23.2% while its peers fell 1.5%.", CARD) == []   # only the first % counts
    assert meaning_errors("Turnover rose to 8.6x normal. The share fell 23.2%.", CARD) == []  # other sentences untouched


def test_llm_text_with_wrong_share_move_falls_back(monkeypatch):
    from ai import llm, narrate
    monkeypatch.setattr(llm, "chat", lambda *a, **k: SimpleNamespace(content="The share price fell 21.7% vs. the MDAX.", tool_calls=None))
    out = narrate.narrate_with_meta({**CARD, "auctions": {}, "comparison": None}, "en")
    assert out["source"] == "template" and out["rejected"] and "21.7%" in out["rejected"][0]


def test_rank_text_is_the_same_everywhere():
    from ai.narrate import template_narrative
    from report.fmt import formatters
    assert formatters("en")["rank"](3, 215) == "rank 3 of 215 (incl. this day)"
    assert formatters("de")["rank"](3, 215) == "Rang 3 von 215 (inkl. dieses Tages)"
    card = {**CARD, "auctions": {}, "comparison": {**CARD["comparison"], "rank_of": 215, "group": "unusual trading days",
                                                   "group_type": "NOTABLE_DAY", "group_index": "MDAX"}}
    assert "rank 3 of 215 (incl. this day)" in template_narrative(card, "en")
    assert "Rang 3 von 215 (inkl. dieses Tages)" in template_narrative(card, "de")


def test_numbers_check_understands_german_short_dates():
    """'am 29.05.' is a date when the data has 2026-05-29; '14.7' stays a number when no such day exists."""
    from ai.checks import unsupported_numbers
    payload = {"episodes": [{"peak_date": "2026-05-29", "abn_ret": 0.104}, {"peak_date": "2026-07-14"}]}
    assert unsupported_numbers("+10.4% am 29.05. und am 14.7.: Ad-hoc.", payload) == []
    assert unsupported_numbers("Am 03.08. fiel die Aktie.", payload) == ["03.08"]   # no 3 Aug in the data
    assert unsupported_numbers("Der Umsatz stieg um 14.7%.", {"x": 0.104}) == ["14.7"]  # a percentage, not a date


def test_numbers_check_reads_english_thousands_in_titles():
    """The event title says 'EUR 1,628m'; '1,628 Mrd. EUR' (German) is the same number."""
    from ai.checks import unsupported_numbers
    payload = {"title": "incoming orders down to EUR 1,628m"}
    assert unsupported_numbers("Auftragseingang 1,628 Mrd. EUR.", payload) == []
    assert unsupported_numbers("Auftragseingang 1,734 Mrd. EUR.", payload) == ["1,734"]


def test_english_number_style_and_model_text_normaliser():
    """EN: "−23.2%", "€25k", "€4.6m", "8.6×" from report.fmt; model text is brought into that style, numbers unchanged."""
    from ai.checks import unsupported_numbers
    from report.fmt import formatters, normalize_en
    f = formatters("en")
    assert (f["pct"](-0.232), f["eur"](25000), f["eur"](4.6e6), f["x"](8.6)) == ("−23.2%", "€25k", "€4.6m", "8.6×")
    raw = "The share moved -23.2 %, peers -1.5 %. Turnover 8.6x normal, closing auction EUR 25.6 million, a EUR 25 k order, 2026-03-27, t-65."
    out = normalize_en(raw)
    assert out == ("The share moved −23.2%, peers −1.5%. Turnover 8.6× normal, closing auction €25.6m, a €25k order, "
                   "2026-03-27, t-65.")
    payload = {"price": {"ret": -0.232, "peer_ret": -0.015}, "volume": {"ratio": 8.6}, "auction_eur": 25600000,
               "notional": 25000, "day": "2026-03-27", "window": "t-65"}
    assert unsupported_numbers(out, payload) == unsupported_numbers(raw, payload) == []
