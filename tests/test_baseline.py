"""Regression tests for engine/baseline.py (from Kaan's PR #8).

Data tests are skipped when data/daily_features.parquet is missing (same rule as test_smoke.py).
"""
import pytest

from config import DATA_DIR

HAS_DATA = (DATA_DIR / "daily_features.parquet").exists()
needs_data = pytest.mark.skipif(not HAS_DATA, reason="data/daily_features.parquet missing")


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
def test_anomalies_runs_for_every_stock():
    """QIA, HAG and TKCC have no unusual day in 2026 and used to crash the dashboard and impact card pages."""
    from engine.baseline import anomalies
    from engine.data import universe
    for isin in universe()["isin"]:
        anomalies(isin)
