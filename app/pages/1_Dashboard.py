"""Part A - the normal state.  OWNER: C3 (frontend).

TODO C3:
  - date range filter; peer selection (index / sector) once sectors.csv is filled
  - "Export IR snapshot (Part A)" button (with C4)
  - nicer anomaly markers (hover: reason, abnormal return, volume ratio)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: E402,F401
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402
from plotly.subplots import make_subplots  # noqa: E402

import pandas as pd  # noqa: E402

from components import bps, eur, pct, pct0, setup  # noqa: E402
from engine import baseline, compare, data  # noqa: E402

isin = setup("Dashboard")


@st.cache_data
def load(isin):
    return (baseline.profile(isin), baseline.anomalies(isin), baseline.kpis(isin),
            baseline.liquidity_trend(isin), baseline.anomaly_episodes(isin))


prof, anom, k, trend, episodes = load(isin)


@st.cache_data
def peer_median(isin: str, by: str, col: str) -> pd.Series:
    """Daily median of `col` across the stock's peer group (index, sector or turnover cohort)."""
    if by == "index":
        return baseline.index_benchmark(k["index"], col)
    isins = compare.peer_group(isin, by)["isins"]
    d = data.daily()
    return d[d["isin"].isin(isins)].groupby("date")[col].median()
st.title(f"{k['name'].title()} · how the share trades")

# Peer benchmarking by index, sector or size (brief point II; engine.compare.peer_group, C2)
PEERS = {"Index": "index", "Sector": "sector", "Size": "size"}
choice = st.segmented_control("Compare with", list(PEERS), default="Index") or "Index"
by = PEERS[choice]
key = f"{by}_median"
g = k["peer_groups"][by]
peer = g["name"] if by != "size" else f"{g['name']} cohort"
st.caption(f"{k['period']} · compared with the median stock of **{g['label']}** ({g['n']} peers)"
           + (" · sector unknown, showing the index" if g["fallback"] else "")
           + (" · size = turnover cohort (market cap is not in the data)" if by == "size" else ""))
if g["n"] < 3:
    st.warning("Small peer group: these medians rest on fewer than 3 other stocks.")

c = st.columns(5)
c[0].metric("Median daily turnover", eur(k["median_turnover_eur"]["stock"]),
            f"{peer} {eur(k['median_turnover_eur'][key])}", delta_color="off")
c[1].metric("Trading cost XLM 25k", bps(k["median_xlm_25k_bps"]["stock"]),
            f"{peer} {bps(k['median_xlm_25k_bps'][key])}", delta_color="off")
c[2].metric("Auction share", pct0(k["median_auction_share"]["stock"]),
            f"{peer} {pct0(k['median_auction_share'][key])}", delta_color="off")
c[3].metric("Agent (client) share", pct0(k["median_agent_share"]["stock"]),
            f"{peer} {pct0(k['median_agent_share'][key])}", delta_color="off")
lc = k["liquidity_check"]
c[4].metric("Liquidity category (est.)", lc["category_estimate"],
            f"4m: {eur(lc['avg_turnover_eur_4m'])}/day · {bps(lc['median_xlm_25k_bps_4m'])}", delta_color="off")

# "Has our liquidity improved?" (engine.baseline.liquidity_trend, C2)
st.markdown(f"**Has our liquidity improved?** · {trend['period']}")
s, ds = trend["stock"], trend["ds_category"] or {}
lt = st.columns(4)
lt[0].metric("Liquidity trend", trend["verdict"].capitalize() if trend["verdict"] else "n/a",
             {"stock-specific": "stock-specific", "market-wide": "market-wide"}.get(trend["vs_index"], ""),
             delta_color="off", help=trend["help"])
lt[1].metric("Trading cost XLM 25k", bps(s["xlm_25k_bps"]["now"]),
             None if trend["xlm_25k_change_pct"] is None else pct(trend["xlm_25k_change_pct"]),
             delta_color="inverse", help="Lower is better. Median of the last 60 trading days vs the 60 before.")
lt[2].metric("Median daily turnover", eur(s["turnover_eur"]["now"]),
             None if trend["turnover_change_pct"] is None else pct(trend["turnover_change_pct"]),
             help="Higher is better. Median of the last 60 trading days vs the 60 before.")
lt[3].metric("Designated Sponsor category (est.)", ds.get("now") or "n/a",
             "unchanged" if ds.get("now") and ds.get("now") == ds.get("before")
             else (f"was {ds['before']}" if ds.get("before") else ""), delta_color="off")
st.caption(trend["summary"])

# Price + turnover with anomaly markers
fig = make_subplots(specs=[[{"secondary_y": True}]])
fig.add_bar(x=prof["date"], y=prof["turnover_eur"], name="Turnover (EUR)", opacity=0.35, secondary_y=True)
fig.add_scatter(x=prof["date"], y=prof["price"], name="Price (closing auction)", mode="lines", secondary_y=False)
a = prof.merge(anom[["date", "reason"]], on="date")
fig.add_scatter(x=a["date"], y=a["price"], mode="markers", name="Unusual day", text=a["reason"],
                marker=dict(size=10, symbol="circle-open", line=dict(width=2)), secondary_y=False)
fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h"))
st.plotly_chart(fig, width="stretch")

left, right = st.columns(2)
with left:
    st.markdown(f"**Trading cost (XLM, EUR 25k order) vs {peer} median**")
    bench = peer_median(isin, by, "xlm_25k")
    f2 = go.Figure()
    f2.add_scatter(x=prof["date"], y=prof["xlm_25k"], name=k["ticker"], mode="lines")
    f2.add_scatter(x=bench.index, y=bench.values, name=f"{peer} median", mode="lines", line=dict(dash="dot"))
    f2.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="bps", legend=dict(orientation="h"))
    st.plotly_chart(f2, width="stretch")
with right:
    st.markdown("**Who trades (share of turnover, 10-day average)**")
    f3 = go.Figure()
    for col, name in [("agent_share", "Agent (clients)"), ("prop_share", "Proprietary"), ("mm_share", "Market makers")]:
        f3.add_scatter(x=prof["date"], y=prof[col].rolling(10, min_periods=3).mean(), name=name, mode="lines")
    f3.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), yaxis_tickformat=".0%",
                     legend=dict(orientation="h"))
    st.plotly_chart(f3, width="stretch")

st.markdown("### Unusual days")
st.caption("Consecutive unusual days are merged into one episode. The announcement column links each episode to "
           "a sourced event from events/events.csv (empty = no company news found).")
ev = data.events()
ev = ev[ev["isin"] == isin]
ev_day = pd.to_datetime(ev["reaction_day"])


def linked_event(start, end) -> str:
    hit = ev[(ev_day >= start) & (ev_day <= end)]
    return " · ".join(hit["title"])  # titles already name the event type ("FY 2025 results", "Ad hoc: ...")


show = episodes.copy()
show["event"] = [linked_event(a, b) for a, b in zip(show["start"], show["end"], strict=False)]
for col in ("start", "end", "peak_date"):
    show[col] = pd.to_datetime(show[col]).dt.date
st.dataframe(show[["start", "end", "days", "event", "reason", "peak_abn_ret", "total_abn_ret", "max_vol_ratio"]].style.format(
    {"peak_abn_ret": "{:+.1%}", "total_abn_ret": "{:+.1%}", "max_vol_ratio": "{:.1f}x"}, na_rep="–"),
    width="stretch", hide_index=True,
    column_config={"event": "announcement", "peak_abn_ret": "stock-specific move (peak day)",
                   "total_abn_ret": "stock-specific move (episode)", "max_vol_ratio": "turnover vs normal (max)"})
if len(show):
    opts = list(show.itertuples())
    pick = st.selectbox("Open an impact card for", range(len(opts)),
                        format_func=lambda i: f"{opts[i].peak_date} · {opts[i].event or opts[i].reason}"[:110])
    if st.button("⚡ Generate impact card", type="primary"):
        st.session_state["impact_day"] = str(opts[pick].peak_date)
        st.switch_page("pages/2_Impact_Card.py")
