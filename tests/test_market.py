"""engine/market.py: "You vs market" and "Big market days", checked against the raw daily rows."""
import pandas as pd
import pytest

from config import DATA_DIR

pytestmark = pytest.mark.skipif(not (DATA_DIR / "daily_features.parquet").exists(), reason="data missing")


@pytest.mark.parametrize("ticker, n_members", [("EVD", 50), ("HDD", 70), ("ZAL", 40)])
def test_versus_market_matches_raw_rows(ticker, n_members):
    from engine import data, market
    isin = data.isin_of(ticker)
    vm = market.versus_market(isin, "3m")
    w = market.window("3m")
    me = data.daily()
    me = me[(me["isin"] == isin) & me["date"].isin(w)].sort_values("date")
    assert len(w) == 63 and vm["price"]["of"] == n_members                    # current index members only
    assert vm["price"]["stock"] == pytest.approx(me["price"].iloc[-1] / me["prev_price"].iloc[0] - 1, abs=1e-6)
    assert vm["turnover_eur"]["stock"] == pytest.approx(me["turnover_eur"].median(), abs=1)
    assert vm["xlm_25k"]["stock"] == pytest.approx(me["xlm_25k"].median(), abs=0.01)
    assert vm["price"]["index"] == pytest.approx((1 + me["peer_ret"]).prod() - 1, abs=1e-6)
    assert "not the official index level" in vm["index_note"] and "index" not in vm["groups"]


def test_market_days_are_the_strongest_index_days():
    from engine import data, market
    isin = data.isin_of("EVD")
    rows = market.market_days(isin, "all")
    s = data.stock(isin).set_index("date")
    assert len(rows) == 10 and [r["date"] for r in rows] == sorted((r["date"] for r in rows), reverse=True)
    moves = [r for r in rows if r["why"] == "index_move"]
    cut = min(abs(r["index_ret"]) for r in moves)
    others = s.drop([pd.Timestamp(r["date"]) for r in rows])["peer_ret"].abs()
    assert others.max() <= cut + 1e-9                                         # no stronger index day left out
    for r in rows:                                                            # share - index = stock-specific move
        assert r["ret"] - r["index_ret"] == pytest.approx(r["abn_ret"], abs=1e-5)
        if r["why"] == "market_wide_volume":
            assert "market_wide_volume" in r["context"]


def test_event_list_shows_publication_date_and_card_figures():
    from engine import data, impact, market
    isin = data.isin_of("EVD")
    rows = market.event_list(isin, "all")
    assert [r["day"] for r in rows] == sorted((r["day"] for r in rows), reverse=True)
    fy = next(r for r in rows if r["event_id"] == "EVD_FY_20260326")
    card = impact.impact_card(isin, "2026-03-27")
    assert (fy["published"], fy["day"]) == ("2026-03-26", "2026-03-27")
    assert fy["vol_ratio"] == card["volume"]["ratio"] and fy["abn_ret"] == pytest.approx(card["price"]["abn_ret"], abs=1e-6)
    assert sum(r["type"] == "UNUSUAL_DAY" for r in rows) == 2                 # 5 Mar and 27 Feb have no calendar entry
