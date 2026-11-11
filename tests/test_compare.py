"""Tests for engine/compare.py and the baseline.anomalies() empty-result fix.

Data tests are skipped when data/daily_features.parquet is missing (same rule as test_smoke.py).
"""
import pandas as pd
import pytest

from config import DATA_DIR

HAS_DATA = (DATA_DIR / "daily_features.parquet").exists()
needs_data = pytest.mark.skipif(not HAS_DATA, reason="data/daily_features.parquet missing")


def _card(isin="X1", day="2026-03-27", abn=-0.20, vol=8.0, xlm=1.5):
    return {"isin": isin, "event": {"type": "NOTABLE_DAY", "reaction_day": day},
            "price": {"abn_ret": abn}, "volume": {"ratio": vol}, "liquidity": {"ratio": xlm}}


def _table():
    return pd.DataFrame({
        "isin": ["A", "B", "C", "D", "X1"],
        "index": ["MDAX"] * 5,
        "reaction_day": ["2026-01-02"] * 4 + ["2026-03-27"],
        "abn_ret": [0.01, -0.05, 0.10, None, -0.20],
        "vol_ratio": [2.0, 3.0, 10.0, 4.0, 8.0],
        "xlm_25k_ratio": [1.0, 2.0, None, 1.2, 1.5],
        "source": ["notable_day"] * 5,
    })


def test_percentile_excludes_own_row_and_handles_nulls():
    from engine.compare import percentile
    c = percentile(_card(), _table())
    assert c["n"] == 4                                  # own row (X1, 2026-03-27) excluded
    assert c["pctile"]["abn_ret"] == 0.0                # most negative of the 3 non-null
    assert c["pctile"]["abs_abn_ret"] == 1.0            # 0.20 > 0.01, 0.05, 0.10
    assert c["pctile"]["vol_ratio"] == 0.75             # 8 > 2, 3, 4 but < 10
    assert c["pctile"]["xlm_25k_ratio"] == pytest.approx(2 / 3, abs=1e-3)
    assert c["median"]["vol_ratio"] == 3.5
    assert c["source"] == "notable_day" and c["index"] == "MDAX"
    assert "4 notable days in the MDAX" in c["summary"]


def test_percentile_missing_card_value_gives_none():
    from engine.compare import percentile
    c = percentile(_card(abn=None, xlm=None), _table())
    assert c["pctile"]["abn_ret"] is None and c["pctile"]["xlm_25k_ratio"] is None
    assert c["pctile"]["vol_ratio"] == 0.75


def test_summary_never_rounds_up_to_100_percent():
    from engine.compare import percentile
    t = pd.DataFrame({"isin": [f"S{i}" for i in range(200)], "index": "MDAX", "reaction_day": "2026-01-02",
                      "abn_ret": [0.001] * 199 + [0.5], "vol_ratio": 1.0, "xlm_25k_ratio": 1.0,
                      "source": "notable_day"})
    c = percentile(_card(abn=-0.3, vol=1.0), t)        # larger than 199 of 200 = 99.5 %
    assert "99%" in c["summary"] and "100%" not in c["summary"]


@needs_data
def test_anomalies_empty_for_quiet_stock():
    """Regression: anomalies() used to raise ValueError when no day was unusual."""
    from config import HERO_TICKERS
    from engine.baseline import anomalies
    from engine.data import isin_of
    a = anomalies(isin_of(HERO_TICKERS[0]), z=1e9)     # threshold nothing can reach
    assert a.empty
    assert list(a.columns) == ["date", "ret", "abn_ret", "vol_ratio", "vol_z", "abn_ret_z",
                               "xlm_25k_ratio", "reason", "severity"]


@needs_data
def test_same_type_events_notable_days_mdax():
    from engine.compare import COLUMNS, same_type_events
    t = same_type_events("NOTABLE_DAY", "MDAX")
    assert list(t.columns) == COLUMNS
    assert (t["source"] == "notable_day").all() and (t["index"] == "MDAX").all()
    assert ((t["ticker"] == "EVD") & (t["reaction_day"] == "2026-03-27")).any()


@needs_data
def test_same_type_events_falls_back_when_few_events():
    from engine.compare import same_type_events
    t = same_type_events("Q1", "MDAX")                 # events.csv has no Q1 rows yet
    assert len(t) > 0 and (t["source"] == "notable_day").all()


@needs_data
def test_add_comparison_evd():
    """CTS Eventim, 27 Mar 2026: one of the largest moves and volume spikes in the MDAX."""
    from engine.compare import add_comparison
    from engine.data import isin_of
    from engine.impact import impact_card
    c = add_comparison(impact_card(isin_of("EVD"), "2026-03-27"))["comparison"]
    assert c["n"] > 100
    assert c["pctile"]["abs_abn_ret"] > 0.95
    assert c["pctile"]["vol_ratio"] > 0.9
    assert isinstance(c["summary"], str) and c["summary"]


@needs_data
def test_sector_peers():
    from engine.compare import sector_peers
    from engine.data import daily, isin_of
    assert sector_peers(isin_of("GXI")) == [isin_of("EVT")]      # both Healthcare in sectors.csv
    sap = isin_of("SAP")                                          # not in sectors.csv -> index members
    peers = sector_peers(sap)
    d = daily()
    assert sap not in peers and len(peers) > 30
    assert set(d.loc[d["isin"].isin(peers), "idx_latest"]) == {"DAX"}
