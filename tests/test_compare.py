"""Tests for engine/compare.py percentiles and their display (never "100%").

Data tests are skipped when data/daily_features.parquet is missing (same rule as test_smoke.py).
"""
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

os.environ["LLM_PROVIDER"] = "none"  # tests never call a real LLM

from config import DATA_DIR  # noqa: E402

HAS_DATA = (DATA_DIR / "daily_features.parquet").exists()
needs_data = pytest.mark.skipif(not HAS_DATA, reason="data/daily_features.parquet missing")


def _card(isin="X1", day="2026-03-27", abn=-0.20, vol=8.0, xlm=1.5):
    return {"isin": isin, "event": {"type": "NOTABLE_DAY", "reaction_day": day},
            "price": {"abn_ret": abn}, "volume": {"ratio": vol}, "liquidity": {"ratio": xlm}}


def _table():
    """Like same_type_events(): reaction_day is a datetime column, the card holds a 'YYYY-MM-DD' string."""
    abn = [0.01, -0.05, 0.10, None, -0.20]
    return pd.DataFrame({
        "isin": ["A", "B", "C", "D", "X1"],
        "reaction_day": pd.to_datetime(["2026-01-02"] * 4 + ["2026-03-27"]),
        "abs_abn_ret": [None if a is None else abs(a) for a in abn],
        "vol_ratio": [2.0, 3.0, 10.0, 4.0, 8.0],
        "xlm_ratio": [1.0, 2.0, None, 1.2, 1.5],
    })


def test_percentile_excludes_own_row_and_handles_nulls():
    from engine.compare import percentile
    c = percentile(_card(), _table())
    assert c["n"] == 4                                   # own row (X1, 2026-03-27) excluded
    assert c["abs_abn_ret_pctile"] == 1.0                # 0.20 > 0.01, 0.05, 0.10 (D is null)
    assert c["rank_abs_abn_ret"] == 1
    assert c["vol_ratio_pctile"] == 0.75                 # 8 > 2, 3, 4 but < 10
    assert c["xlm_ratio_pctile"] == pytest.approx(2 / 3, abs=1e-3)
    assert c["vol_ratio_median"] == 3.5
    assert c["abs_abn_ret_median"] == 0.05


def test_percentile_same_isin_other_day_is_kept():
    from engine.compare import percentile
    t = _table()
    t.loc[0, "isin"] = "X1"                              # same stock, different day -> still compared
    assert percentile(_card(), t)["n"] == 4


def test_percentile_missing_card_value_gives_none():
    from engine.compare import percentile
    c = percentile(_card(abn=None, xlm=None), _table())
    assert c["abs_abn_ret_pctile"] is None and c["rank_abs_abn_ret"] is None
    assert c["xlm_ratio_pctile"] is None
    assert c["vol_ratio_pctile"] == 0.75


@pytest.mark.parametrize("p, text", [(0.995, "99%"), (0.29, "29%"), (1.0, "100%"), (0.0, "0%")])
def test_percentile_text_rounds_down(p, text):
    from engine.compare import _share
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
    from components import pctile0
    from ai.narrate import _pctile
    assert _share(p) == pctile0(p) == _pctile(p) == text


def test_narrative_comparison_never_says_100_percent():
    from ai.narrate import narrate
    card = {
        "name": "TEST AG", "index": "MDAX", "event": {"reaction_day": "2026-03-27"},
        "price": {"ret": -0.23, "peer_ret": -0.015, "abn_ret": -0.217},
        "volume": {"ratio": 8.6}, "liquidity": {"xlm_25k_bps": 20.0, "ratio": 1.4},
        "participants": {"agent_aggr_imbalance": -0.36},
        "comparison": {"group_type": "NOTABLE_DAY", "group_index": "MDAX", "n": 214,
                       "group": "unusual trading days, MDAX, Jan – Oct 2026", "abs_abn_ret_pctile": 0.995},
    }
    for lang in ("en", "de"):
        t = narrate(card, lang)
        assert "99%" in t and "100%" not in t


@needs_data
def test_comparison_summary_evd():
    """CTS Eventim, 27 Mar 2026: summary is filled from the card and never claims 100%."""
    from engine.data import isin_of
    from engine.impact import impact_card
    c = impact_card(isin_of("EVD"), "2026-03-27")["comparison"]
    s = c["summary"]
    assert s.startswith(f"Compared with {c['n']} {c['group']}")
    assert "-21.7%" in s and "8.6x normal" in s and "100%" not in s


def test_top_percentile_says_biggest():
    """Percentile 1.0 (the biggest move in the group) reads "the biggest of them", not "bigger than 100%"."""
    from ai.narrate import narrate
    from engine.compare import _summary
    card = {
        "name": "TEST AG", "index": "SDAX", "event": {"reaction_day": "2026-02-11"},
        "price": {"ret": -0.314, "peer_ret": -0.009, "abn_ret": -0.305},
        "volume": {"ratio": 20.1}, "liquidity": {"xlm_25k_bps": 48.0, "ratio": 1.0},
        "participants": {"agent_aggr_imbalance": -0.44},
        "comparison": {"group_type": "NOTABLE_DAY", "group_index": "SDAX", "n": 444,
                       "group": "unusual trading days, SDAX, Jan – Oct 2026", "abs_abn_ret_pctile": 1.0},
    }
    s = _summary(card, card["comparison"]["group"], {"n": 444, "abs_abn_ret_pctile": 1.0, "vol_ratio_pctile": 0.95})
    assert "the stock-specific move (-30.5%) was the biggest of them" in s and "100%" not in s
    assert "the biggest of them" in narrate(card, "en") and "100%" not in narrate(card, "en")
    assert "die größte von allen" in narrate(card, "de") and "100%" not in narrate(card, "de")


@needs_data
def test_comparison_summary_gxi_is_biggest():
    """Gerresheimer, 11 Feb 2026: the biggest stock-specific move among SDAX unusual days."""
    from engine.data import isin_of
    from engine.impact import impact_card
    c = impact_card(isin_of("GXI"), "2026-02-11")["comparison"]
    assert c["abs_abn_ret_pctile"] == 1.0 and c["rank_abs_abn_ret"] == 1
    assert "was the biggest of them" in c["summary"] and "100%" not in c["summary"]


# ---------- peer groups: sector (events/sectors.csv) and turnover cohort (size proxy) ----------
def test_sectors_csv_shape():
    """events/sectors.csv: one row per universe ISIN, 11 groups, every filled row has a source."""
    from config import SECTORS_CSV
    sec = pd.read_csv(SECTORS_CSV, dtype=str)
    assert list(sec.columns) == ["ticker", "isin", "name", "sector", "source_url"]
    assert sec["isin"].is_unique
    assert sec["sector"].dropna().nunique() == 11
    assert sec.loc[sec["sector"].notna(), "source_url"].notna().all()
    assert sec.loc[sec["sector"].isna(), "source_url"].isna().all()
    # ISIN changes in 2026: both ISINs of a company carry the same sector
    for t in ("FRE", "QIA"):
        assert sec.loc[sec["ticker"] == t, "sector"].nunique() == 1 and (sec["ticker"] == t).sum() == 2


@needs_data
def test_sectors_csv_covers_universe():
    from config import SECTORS_CSV
    from engine.data import universe
    sec = pd.read_csv(SECTORS_CSV, dtype=str)
    assert set(sec["isin"]) == set(universe()["isin"])


@needs_data
def test_sector_peers_evd():
    from engine.compare import _sectors, peer_group, sector_peers
    from engine.data import isin_of
    evd = isin_of("EVD")
    assert _sectors()[evd] == "Media & Telecom"
    peers = sector_peers(evd)
    assert evd not in peers and len(peers) >= 3
    assert all(_sectors()[p] == "Media & Telecom" for p in peers)
    assert peer_group(evd, "sector")["fallback"] is None


@needs_data
def test_sector_peers_exclude_other_isin_of_same_company():
    from engine.compare import sector_peers
    from engine.data import universe
    u = universe()
    fre = u.loc[u["ticker"] == "FRE", "isin"].tolist()
    for i in fre:
        assert not set(fre) & set(sector_peers(i))


@needs_data
def test_size_cohorts_are_terciles():
    from config import SIZE_COHORT_LABELS
    from engine.compare import size_cohorts
    counts = size_cohorts().value_counts()
    assert set(counts.index) == set(SIZE_COHORT_LABELS) and counts.sum() == 174
    assert counts.max() - counts.min() <= 1                     # 58 / 58 / 58


@needs_data
def test_size_peers_same_cohort():
    from engine.compare import peer_group, size_cohort, size_peers
    from engine.data import isin_of
    sap = isin_of("SAP")
    assert size_cohort(sap) == "large"
    assert sap not in size_peers(sap)
    assert {size_cohort(p) for p in size_peers(sap)} == {"large"}
    assert peer_group(sap, "size")["label"] == "Turnover cohort (size proxy): large"


@needs_data
def test_missing_sector_falls_back_to_index(tmp_path, monkeypatch):
    """A stock with a blank sector (here EVD, blanked in a temp copy) gets its index members."""
    import engine.compare as compare
    from config import SECTORS_CSV
    from engine.data import isin_of
    evd = isin_of("EVD")
    sec = pd.read_csv(SECTORS_CSV, dtype=str)
    sec.loc[sec["isin"] == evd, "sector"] = None
    tmp = tmp_path / "sectors.csv"
    sec.to_csv(tmp, index=False)
    monkeypatch.setattr(compare, "SECTORS_CSV", tmp)
    compare._sectors.cache_clear()
    try:
        g = compare.peer_group(evd, "sector")
        assert g["fallback"] == "index" and g["by"] == "index"
        assert g["isins"] == compare.peer_group(evd, "index")["isins"]
    finally:
        compare._sectors.cache_clear()


@needs_data
def test_peer_group_rejects_unknown_by():
    from engine.compare import peer_group
    from engine.data import isin_of
    with pytest.raises(ValueError):
        peer_group(isin_of("EVD"), "market_cap")
