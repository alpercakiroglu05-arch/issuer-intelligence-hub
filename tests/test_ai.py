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
    monkeypatch.setattr(llm, "chat", lambda *a, **k: SimpleNamespace(content="Liquidity improved by 47.3%.", tool_calls=None))
    out = agent.ask("Has our liquidity improved?", isin_of("EVD"))
    assert "47.3" not in out and "Stable" in out   # deterministic answer = liquidity_trend summary
    assert os.environ["LLM_PROVIDER"] == "none"
