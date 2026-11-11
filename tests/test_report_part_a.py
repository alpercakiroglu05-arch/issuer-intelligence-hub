"""Tests for the Part A report (report.export.part_a_html): DE/EN HTML, PDF bytes, numbers equal to the engine.

Edge cases: HAG (no unusual days), GXI (no XLM after leaving the SDAX), old QIA ISIN (4 trading days),
KCO (no sector). Data tests are skipped when data/daily_features.parquet is missing.
"""
import pytest

from config import DATA_DIR

HAS_DATA = (DATA_DIR / "daily_features.parquet").exists()
needs_data = pytest.mark.skipif(not HAS_DATA, reason="data/daily_features.parquet missing")

OLD_QIA = "NL0015002CX3"  # QIAGEN before the share consolidation, 4 trading days in Jan
STOCKS = ["EVD", "HDD", "HAG", "GXI", "KCO", OLD_QIA]


def _isin(t):
    from engine.data import isin_of
    return t if t.startswith("NL") else isin_of(t)


@needs_data
@pytest.mark.parametrize("ticker", STOCKS)
@pytest.mark.parametrize("lang", ["en", "de"])
def test_part_a_html_builds(ticker, lang):
    from report.export import LABELS_A, part_a_html
    h = part_a_html(_isin(ticker), lang)
    L = LABELS_A[lang]
    for heading in ("kpi_h", "trend_h", "curve_h", "ep_h"):
        assert L[heading] in h.replace("&amp;", "&")
    assert L["foot"][:40] in h


@needs_data
@pytest.mark.parametrize("ticker", STOCKS)
def test_part_a_pdf_bytes(ticker):
    from report.export import part_a_html, to_pdf
    pdf = to_pdf(part_a_html(_isin(ticker), "de"))
    assert pdf is not None and pdf[:4] == b"%PDF"


@needs_data
@pytest.mark.parametrize("ticker, by", [("EVD", "index"), ("HDD", "size"), ("HAG", "sector")])
def test_part_a_numbers_match_engine(ticker, by):
    from engine import baseline, xlm
    from report.export import _fmt, part_a_html
    f = _fmt()
    isin = _isin(ticker)
    k, t = baseline.kpis(isin), baseline.liquidity_trend(isin)
    cs = xlm.curve_summary(xlm.cost_curve(isin, by))
    h = part_a_html(isin, "en", peer_by=by)
    for key, fmt in (("median_turnover_eur", f["eur"]), ("median_xlm_25k_bps", f["bps"]),
                     ("median_auction_share", f["pct0"]), ("median_agent_share", f["pct0"])):
        for col in ("stock", "index_median", "sector_median", "size_median"):
            assert fmt(k[key][col]) in h, (key, col)
    assert f["eur"](k["liquidity_check"]["avg_turnover_eur_4m"]) in h
    assert f"Liquidity category (estimate): {k['liquidity_check']['category_estimate']}" in h
    assert t["summary"] in h
    assert f["pct"](t["xlm_25k_change_pct"]) in h and f["pct"](t["turnover_change_pct"]) in h
    assert f["bps"](cs["cost_100k_bps"]) in h and f["bps"](cs["peer_cost_100k_bps"]) in h


@needs_data
def test_part_a_de_summary_uses_engine_numbers():
    from engine import baseline
    from report.export import _fmt, part_a_html
    isin = _isin("HDD")
    t = baseline.liquidity_trend(isin)
    sp = _fmt("de")["spct0"]
    h = part_a_html(isin, "de")
    assert f"Handelskosten {sp(t['xlm_25k_change_pct'])}" in h       # e.g. "Handelskosten −33 %"
    assert f"Umsatz {sp(t['turnover_change_pct'])}" in h


@needs_data
def test_part_a_states_peer_group():
    from report.export import part_a_html
    h = part_a_html(_isin("HDD"), "en", peer_by="size")
    assert "compared with Turnover cohort (size proxy)" in h


@needs_data
def test_part_a_missing_data_notes():
    from report.export import LABELS_A, part_a_html
    assert LABELS_A["en"]["no_ep"] in part_a_html(_isin("HAG"), "en")          # no unusual days
    assert LABELS_A["de"]["no_ep"] in part_a_html(_isin("HAG"), "de")
    assert LABELS_A["en"]["no_xlm"] in part_a_html(_isin("GXI"), "en")          # left the SDAX -> no XLM
    assert LABELS_A["en"]["no_xlm"] in part_a_html(OLD_QIA, "en")               # 4 trading days only
    assert LABELS_A["en"]["sector_unknown"] in part_a_html(_isin("KCO"), "en")  # sector blank in sectors.csv


@needs_data
def test_part_a_impact_card_template_still_renders():
    """The Part B snapshot must keep working next to the new report."""
    from engine.impact import impact_card
    from report.export import to_html
    card = impact_card(_isin("EVD"), "2026-03-27")
    assert "-21.7%" in to_html(card, "text", "en")
    de = to_html(card, "text", "de")
    assert "−21,7 %" in de and "27.03.2026" in de and "-21.7%" not in de
    assert "auffälligen Handelstagen, MDAX, Jan.–Okt. 2026" in de


@needs_data
@pytest.mark.parametrize("ticker, by", [("EVD", "index"), ("HDD", "size"), ("HAG", "sector")])
def test_part_a_de_numbers_match_engine(ticker, by):
    """DE report: the same engine numbers in German style, and no EN-style number from the engine left."""
    import re

    from engine import baseline
    from report.export import _fmt, part_a_html
    f = _fmt("de")
    isin = _isin(ticker)
    k, t = baseline.kpis(isin), baseline.liquidity_trend(isin)
    h = part_a_html(isin, "de", peer_by=by)
    for key, fmt in (("median_turnover_eur", f["eur"]), ("median_xlm_25k_bps", f["bps"]),
                     ("median_auction_share", f["pct0"]), ("median_agent_share", f["pct0"])):
        for col in ("stock", "index_median", "sector_median", "size_median"):
            assert fmt(k[key][col]) in h, (key, col)
    assert f["pct"](t["xlm_25k_change_pct"]) in h and f["pct"](t["turnover_change_pct"]) in h
    assert "02.01.2026" in h and "2026-01-02" not in h
    body = re.sub(r"<td>[^<]*(Ad hoc|results|report|MSCI|Q\d|FY)[^<]*</td>", "", h)  # event titles are source text
    assert not re.search(r"EUR \d|\d\.\d%|\d\.\dx\b", body)


@needs_data
def test_snapshot_shows_rank_incl_this_day():
    from engine.impact import impact_card
    from report.export import to_html
    card = impact_card(_isin("EVD"), "2026-03-27")
    c = card["comparison"]
    assert f"rank {c['rank_abs_abn_ret']} of {c['rank_of']} (incl. this day)" in to_html(card, "text", "en")
    assert f"Rang {c['rank_abs_abn_ret']} von {c['rank_of']} (inkl. dieses Tages)" in to_html(card, "text", "de")
