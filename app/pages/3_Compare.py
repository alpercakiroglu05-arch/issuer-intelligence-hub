"""Compare events of the same type.  OWNER: C3 (frontend); engine in engine/compare.py.

TODO C3: styling, maybe a box plot per type; DE labels
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: E402,F401
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from components import pct, pct0, setup, times  # noqa: E402
from engine import compare, data  # noqa: E402

isin = setup("Compare")
ticker = data.ticker_of(isin)
st.title("📐 Compare events of the same type")
st.caption("How did the market react to this kind of event across DAX, MDAX and SDAX in 2026? "
           "Same numbers as on the impact card (baseline t-65..t-6).")

LABEL = {compare.AUTO_TYPE: "Unusual trading days (detected automatically)"}
types = compare.event_types()
c = st.columns([2, 1])
etype = c[0].selectbox("Event type", types, format_func=lambda t: LABEL.get(t, t))
my_index = compare.metrics_all().query("isin == @isin")["index"].iloc[-1]
universes = ["DAX", "MDAX", "SDAX", "all"]
index = c[1].selectbox("Index", universes, index=universes.index(my_index) if my_index in universes else 3)


@st.cache_data(show_spinner="Collecting events…")
def load(etype, index):
    return compare.same_type_events(etype, None if index == "all" else index)


table = load(etype, index)
if table.empty:
    st.info(f"No **{etype}** events in {index} yet. The research team adds announcements to "
            "`events/events.csv` (type, date, time, source); they appear here automatically.")
    st.stop()

mine = table["isin"] == isin
k = st.columns(4)
k[0].metric("Events", len(table), f"{int(mine.sum())} of them {ticker}", delta_color="off")
k[1].metric("Median stock-specific move (abs.)", pct0(table["abs_abn_ret"].median()))
k[2].metric("Median turnover vs normal", times(table["vol_ratio"].median()))
k[3].metric("Median trading cost vs normal", times(table["xlm_ratio"].median()))

# Scatter: stock-specific move vs turnover, this stock highlighted
f = go.Figure()
for sel, name, size, color in [(~mine, "other stocks", 7, "rgba(140,140,160,0.45)"), (mine, ticker, 13, "#e4572e")]:
    t = table[sel]
    f.add_scatter(x=t["abn_ret"], y=t["vol_ratio"], mode="markers", name=name,
                  marker=dict(size=size, color=color, line=dict(width=1 if name == ticker else 0, color="white")),
                  text=t["ticker"] + " · " + t["reaction_day"].dt.strftime("%d %b") + "<br>" + t["title"].str[:60],
                  hovertemplate="%{text}<br>stock-specific %{x:+.1%} · turnover %{y:.1f}x<extra></extra>")
f.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h"),
                xaxis=dict(title="Stock-specific move (vs index peers)", tickformat="+.0%", zeroline=True),
                yaxis=dict(title="Turnover vs normal (log)", type="log"))
st.plotly_chart(f, width="stretch")

st.markdown("### All events")
show = table.assign(day=table["reaction_day"].dt.date).sort_values("abs_abn_ret", ascending=False)
st.dataframe(
    show[["ticker", "day", "index", "title", "ret", "abn_ret", "vol_ratio", "xlm_ratio", "auction_share_delta",
          "agent_aggr_imbalance", "car_0_5"]].style.format(
        {"ret": "{:+.1%}", "abn_ret": "{:+.1%}", "vol_ratio": "{:.1f}x", "xlm_ratio": "{:.1f}x",
         "auction_share_delta": "{:+.0%}", "agent_aggr_imbalance": "{:+.0%}", "car_0_5": "{:+.1%}"}, na_rep="–"),
    width="stretch", hide_index=True,
    column_config={"title": "event / reason", "abn_ret": "stock-specific", "vol_ratio": "turnover vs normal",
                   "xlm_ratio": "trading cost vs normal", "auction_share_delta": "auction share Δ",
                   "agent_aggr_imbalance": "agent imbalance", "car_0_5": "abn. return t0..t+5"})

st.markdown("### Open an impact card")
opts = list(show.itertuples())
pick = st.selectbox("Event", range(len(opts)), format_func=lambda i: f"{opts[i].ticker} · {opts[i].day} · "
                    f"{pct(opts[i].abn_ret)} · {opts[i].title[:50]}")
if st.button("⚡ Generate impact card", type="primary"):
    st.session_state["isin"] = opts[pick].isin
    st.session_state["impact_day"] = str(opts[pick].day)
    st.switch_page("pages/2_Impact_Card.py")
