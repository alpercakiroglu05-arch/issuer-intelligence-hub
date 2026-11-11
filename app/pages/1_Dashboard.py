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

from components import bps, eur, pct0, setup  # noqa: E402
from engine import baseline  # noqa: E402

isin = setup("Dashboard")


@st.cache_data
def load(isin):
    return baseline.profile(isin), baseline.anomalies(isin), baseline.kpis(isin)


prof, anom, k = load(isin)
st.title(f"{k['name'].title()} · how the share trades")
st.caption(f"{k['index']} · {k['period']} · compared with the median {k['index']} stock")

c = st.columns(5)
c[0].metric("Median daily turnover", eur(k["median_turnover_eur"]["stock"]),
            f"index {eur(k['median_turnover_eur']['index_median'])}", delta_color="off")
c[1].metric("Trading cost XLM 25k", bps(k["median_xlm_25k_bps"]["stock"]),
            f"index {bps(k['median_xlm_25k_bps']['index_median'])}", delta_color="off")
c[2].metric("Auction share", pct0(k["median_auction_share"]["stock"]),
            f"index {pct0(k['median_auction_share']['index_median'])}", delta_color="off")
c[3].metric("Agent (client) share", pct0(k["median_agent_share"]["stock"]),
            f"index {pct0(k['median_agent_share']['index_median'])}", delta_color="off")
lc = k["liquidity_check"]
c[4].metric("Liquidity category (est.)", lc["category_estimate"],
            f"4m: {eur(lc['avg_turnover_eur_4m'])}/day · {bps(lc['median_xlm_25k_bps_4m'])}", delta_color="off")

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
    st.markdown("**Trading cost (XLM, EUR 25k order) vs index median**")
    bench = baseline.index_benchmark(k["index"], "xlm_25k")
    f2 = go.Figure()
    f2.add_scatter(x=prof["date"], y=prof["xlm_25k"], name=k["ticker"], mode="lines")
    f2.add_scatter(x=bench.index, y=bench.values, name=f"{k['index']} median", mode="lines", line=dict(dash="dot"))
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
show = anom.copy()
show["date"] = show["date"].dt.date
st.dataframe(show[["date", "reason", "ret", "abn_ret", "vol_ratio", "xlm_25k_ratio"]].style.format(
    {"ret": "{:+.1%}", "abn_ret": "{:+.1%}", "vol_ratio": "{:.1f}x", "xlm_25k_ratio": "{:.1f}x"}, na_rep="–"),
    width="stretch", hide_index=True)
if len(show):
    day = st.selectbox("Open an impact card for", show["date"].tolist())
    if st.button("⚡ Generate impact card", type="primary"):
        st.session_state["impact_day"] = str(day)
        st.switch_page("pages/2_Impact_Card.py")
