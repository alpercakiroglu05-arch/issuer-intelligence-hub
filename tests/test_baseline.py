"""Tests for engine/baseline.py: anomalies() regressions (PR #8/#10), liquidity_trend(), anomaly_episodes().

Data tests are skipped when data/daily_features.parquet is missing (same rule as test_smoke.py).
"""
import pandas as pd
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
                               "xlm_25k_ratio", "reason", "severity", "context"]


@needs_data
def test_anomalies_runs_for_every_stock():
    """QIA, HAG and TKCC have no unusual day in 2026 and used to crash the dashboard and impact card pages."""
    from engine.baseline import anomalies
    from engine.data import universe
    for isin in universe()["isin"]:
        anomalies(isin)


QIA_OLD_ISIN = "NL0015002CX3"  # Qiagen's previous ISIN: only 4 trading days in the data
TREND_KEYS = {"isin", "ticker", "index", "window", "period", "stock", "index_median", "xlm_25k_change_pct",
              "turnover_change_pct", "index_xlm_25k_change_pct", "index_turnover_change_pct", "verdict",
              "vs_index", "help", "ds_category", "monthly", "summary", "flags",
              "sector", "sector_median", "sector_xlm_25k_change_pct", "sector_turnover_change_pct", "vs_sector"}


@pytest.mark.parametrize("xlm, to, verdict", [
    (-0.33, -0.50, "mixed"),      # cheaper to trade, but much less turnover (HDD)
    (-0.10, 0.0, "improved"),     # exactly at the threshold counts
    (0.0, 0.10, "improved"),
    (0.05, -0.41, "worsened"),
    (0.099, -0.099, "stable"),
    (None, -0.04, "stable"),      # no XLM (stock left the index): turnover alone decides
    (None, 0.25, "improved"),
    (None, None, "stable"),
])
def test_verdict_rule(xlm, to, verdict):
    from engine.baseline import _verdict
    assert _verdict(xlm, to) == verdict


def test_every_verdict_has_help_text():
    from engine.baseline import TREND_HELP
    for v in ("improved", "worsened", "mixed", "stable", None):
        assert isinstance(TREND_HELP[v], str) and len(TREND_HELP[v]) > 20


@needs_data
def test_liquidity_trend_hdd_mixed():
    """Heidelberger Druck: XLM 108 -> 72 bps (cheaper) but turnover halved -> mixed, not 'improved'."""
    from engine.baseline import TREND_HELP, liquidity_trend
    from engine.data import isin_of
    t = liquidity_trend(isin_of("HDD"))
    assert set(t) == TREND_KEYS
    assert t["verdict"] == "mixed" and t["vs_index"] == "stock-specific"
    assert t["xlm_25k_change_pct"] == pytest.approx(-0.33, abs=0.01)
    assert t["turnover_change_pct"] == pytest.approx(-0.50, abs=0.01)
    assert t["summary"].startswith("Mixed: trading cost -33% (better), turnover -50% (worse)")
    assert t["help"] == TREND_HELP["mixed"]
    assert t["ds_category"] == {"now": "B", "before": "B"}
    assert t["flags"] == []


@needs_data
def test_liquidity_trend_evd_stable_and_monthly():
    from engine.baseline import liquidity_trend
    from engine.data import isin_of
    t = liquidity_trend(isin_of("EVD"))
    assert t["verdict"] == "stable" and t["vs_index"] is None
    assert t["ds_category"]["now"] == "A"
    assert "MDAX median" in t["summary"]
    months = [m["month"] for m in t["monthly"]]
    assert months[0] == "2026-01" and months[-1] == "2026-10" and len(months) == 10
    assert set(t["monthly"][0]) == {"month", "xlm_25k_bps", "turnover_eur", "index_xlm_25k_bps", "index_turnover_eur"}


@needs_data
def test_liquidity_trend_short_history_does_not_crash():
    from engine.baseline import TREND_HELP, liquidity_trend
    t = liquidity_trend(QIA_OLD_ISIN)
    assert t["verdict"] is None and "short_history" in t["flags"]
    assert t["help"] == TREND_HELP[None]
    assert t["summary"].startswith("Not enough trading history")


@needs_data
def test_episodes_merge_consecutive_days():
    """EVD 27 Mar (Fri) + 30 Mar (Mon) are one episode; HDD 14-16 Apr is one 3-day episode."""
    from engine.baseline import EPISODE_COLS, anomalies, anomaly_episodes
    from engine.data import isin_of
    evd = anomaly_episodes(isin_of("EVD"))
    assert list(evd.columns) == EPISODE_COLS
    e = evd[evd["start"] == pd.Timestamp("2026-03-27")].iloc[0]
    assert e["end"] == pd.Timestamp("2026-03-30") and e["days"] == 2
    assert e["peak_date"] == pd.Timestamp("2026-03-27")
    assert e["peak_abn_ret"] == pytest.approx(-0.2165, abs=0.001)

    hdd_isin = isin_of("HDD")
    hdd, days = anomaly_episodes(hdd_isin), anomalies(hdd_isin)
    h = hdd[hdd["start"] == pd.Timestamp("2026-04-14")].iloc[0]
    assert h["end"] == pd.Timestamp("2026-04-16") and h["days"] == 3
    in_ep = days[(days["date"] >= h["start"]) & (days["date"] <= h["end"])]
    assert h["total_abn_ret"] == pytest.approx(in_ep["abn_ret"].sum())
    assert h["max_vol_ratio"] == pytest.approx(in_ep["vol_ratio"].max())
    assert hdd["days"].sum() == len(days)              # every unusual day lands in exactly one episode
    assert hdd["start"].is_monotonic_decreasing


@needs_data
@pytest.mark.parametrize("isin_or_ticker", ["HAG", QIA_OLD_ISIN])
def test_episodes_empty_for_stock_without_unusual_days(isin_or_ticker):
    from engine.baseline import EPISODE_COLS, anomaly_episodes
    from engine.data import isin_of
    isin = isin_or_ticker if len(isin_or_ticker) == 12 else isin_of(isin_or_ticker)
    e = anomaly_episodes(isin)
    assert e.empty and list(e.columns) == EPISODE_COLS


@needs_data
def test_liquidity_trend_hag_full_history():
    """HAG has no unusual day but a full history: the trend is computed normally."""
    from engine.baseline import liquidity_trend
    from engine.data import isin_of
    t = liquidity_trend(isin_of("HAG"))
    assert t["verdict"] in ("improved", "worsened", "mixed", "stable") and t["flags"] == []


@needs_data
def test_kpis_keeps_index_keys_and_adds_sector_and_size():
    from engine.baseline import kpis
    from engine.data import isin_of
    k = kpis(isin_of("EVD"))
    for key in ("median_turnover_eur", "median_xlm_25k_bps", "median_auction_share", "median_agent_share"):
        assert {"stock", "index_median", "sector_median", "size_median"} <= set(k[key])
        assert k[key]["index_median"] is not None and k[key]["sector_median"] is not None
    assert k["peer_groups"]["sector"]["name"] == "Media & Telecom"
    assert k["peer_groups"]["size"]["label"] == "Similar size: 10 closest by turnover"
    assert k["liquidity_check"]["category_estimate"] in ("A", "B") and k["flags"] == []


@needs_data
def test_kpis_small_peer_group_flag():
    """Utilities has only E.ON and RWE in the universe -> 1 sector peer -> flagged."""
    from engine.baseline import kpis
    from engine.data import isin_of
    k = kpis(isin_of("RWE"))
    assert k["peer_groups"]["sector"]["n"] == 1 and "small_peer_group" in k["flags"]


@needs_data
def test_kpis_and_trend_without_sector_fall_back_to_index():
    """Kloeckner (KCO) is not in the Deutsche Boerse list -> blank sector -> index group."""
    from engine.baseline import kpis, liquidity_trend
    from engine.data import isin_of
    k = kpis(isin_of("KCO"))
    assert k["peer_groups"]["sector"]["fallback"] == "index" and "no_sector" in k["flags"]
    assert k["median_xlm_25k_bps"]["sector_median"] == k["median_xlm_25k_bps"]["index_median"]
    t = liquidity_trend(isin_of("KCO"))
    assert t["vs_sector"] is None and t["sector"] is None and "no_sector" in t["flags"]


@needs_data
def test_liquidity_trend_vs_sector_hdd():
    from engine.baseline import liquidity_trend
    from engine.data import isin_of
    t = liquidity_trend(isin_of("HDD"))
    assert t["sector"] == "Industrials" and t["vs_sector"] == "stock-specific"
    assert t["sector_xlm_25k_change_pct"] is not None and t["sector_turnover_change_pct"] is not None


# ---------- market context: index days, expiries, review dates, market-wide days ----------
@needs_data
def test_context_evd_msci_deletion_day():
    """EVD 31 Aug 2026: MSCI Germany deletion (events.csv type INDEX), volume 19x, price only -1.8%."""
    from engine.baseline import market_context
    from engine.data import isin_of
    c = market_context(isin_of("EVD"), "2026-08-31")
    assert c[0] == "index_event"                                   # most reliable source first
    assert "month_end_review" in c                                  # last trading day of August


@needs_data
@pytest.mark.parametrize("day", ["2026-03-20", "2026-06-19", "2026-09-18"])
def test_context_quarterly_expiry(day):
    from engine.baseline import market_context
    from engine.data import isin_of
    c = market_context(isin_of("EVD"), day)
    assert "quarterly_expiry" in c and "monthly_expiry" not in c
    assert "market_wide_volume" in c                                # these were the busiest days of 2026


@needs_data
def test_context_monthly_expiry_and_plain_days():
    from engine.baseline import market_context
    from engine.data import isin_of
    evd = isin_of("EVD")
    assert market_context(evd, "2026-04-17") == ["monthly_expiry"]
    assert market_context(evd, "2026-04-16") == []


@needs_data
def test_context_real_news_day_has_no_calendar_flag():
    """EVD 27 Mar 2026 (real company news, -23%): no index, calendar or market-wide flag."""
    from engine.baseline import market_context
    from engine.data import isin_of
    assert market_context(isin_of("EVD"), "2026-03-27") == []


@needs_data
def test_context_index_change_gxi():
    """Gerresheimer left the SDAX after 9 Apr: the daily index lists change on 10 Apr."""
    from engine.baseline import market_context
    from engine.data import isin_of
    gxi = isin_of("GXI")
    assert "index_change" in market_context(gxi, "2026-04-10")
    assert "index_event" in market_context(gxi, "2026-04-08")      # STOXX announcement in events.csv


@needs_data
def test_anomalies_and_episodes_have_context_column():
    from engine.baseline import CONTEXT_FLAGS, anomalies, anomaly_episodes
    from engine.data import isin_of
    evd = isin_of("EVD")
    a = anomalies(evd)
    assert list(a.columns)[-1] == "context" and list(a.columns)[-3:-1] == ["reason", "severity"]
    day = a.set_index("date").loc[pd.Timestamp("2026-08-31")]
    assert day["reason"] == "volume spike" and day["context"].startswith("index_event")
    assert a.set_index("date").loc[pd.Timestamp("2026-03-27"), "context"] == ""
    e = anomaly_episodes(evd)
    assert list(e.columns)[-1] == "context"
    flags = {f for c in e["context"] for f in c.split(", ") if f}
    assert flags <= set(CONTEXT_FLAGS)


def test_context_help_covers_every_flag():
    from engine.baseline import CONTEXT_FLAGS, CONTEXT_HELP
    assert set(CONTEXT_HELP) == set(CONTEXT_FLAGS)
    assert "possible" in CONTEXT_HELP["month_end_review"]
    assert all(len(v) > 30 for v in CONTEXT_HELP.values())


def test_expiry_moves_to_previous_trading_day_on_holiday(monkeypatch):
    """Synthetic calendar: if the third Friday is not a trading day, the expiry flag goes to the day before."""
    import engine.baseline as b
    days = pd.bdate_range("2027-03-01", "2027-04-30").drop(pd.Timestamp("2027-03-19"))  # 3rd Friday of March off
    fake = pd.DataFrame({"date": days, "isin": "X", "vol_ratio": 1.0})
    monkeypatch.setattr(b, "daily", lambda: fake)
    b._calendar_context.cache_clear()
    try:
        cal = b._calendar_context()
        assert cal[pd.Timestamp("2027-03-18")] == ["quarterly_expiry"]
        assert cal[pd.Timestamp("2027-04-16")] == ["monthly_expiry"]
        assert not any("month_end_review" in f for f in cal.values())   # no Feb/May/Aug/Nov in range
    finally:
        b._calendar_context.cache_clear()
