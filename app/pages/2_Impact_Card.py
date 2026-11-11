"""Part B - the impact card.  OWNER: C3 (frontend) + C4 (text, export).

TODO C3: intraday chart polish (event time marker, auctions highlighted), layout per designer sketch
TODO C4: PDF layout, numbers check on the AI text
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: E402,F401
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from ai.narrate import narrate_with_meta  # noqa: E402
from components import render_card, setup  # noqa: E402
from engine import baseline, data  # noqa: E402
from engine.impact import impact_card  # noqa: E402
from report.export import to_html, to_pdf  # noqa: E402

isin = setup("Impact card")
st.title("⚡ Event impact card")

# Options: announced events of this stock + automatically detected unusual days
ev = data.events()
ev = ev[ev["isin"] == isin]
options = {}
for r in ev.sort_values("reaction_day", ascending=False).itertuples():
    options[f"{pd.Timestamp(r.reaction_day).date()} · {r.type} · {r.title[:60]}"] = (str(pd.Timestamp(r.reaction_day).date()), r._asdict())
for r in baseline.anomalies(isin).itertuples():
    options.setdefault(f"{r.date.date()} · notable day · {r.reason}", (str(r.date.date()), None))
if not options:
    st.info("No events or unusual days for this stock yet.")
    st.stop()

keys = list(options)
wanted = st.session_state.get("impact_day")
default = next((i for i, k in enumerate(keys) if wanted and k.startswith(wanted)), 0)
choice = st.selectbox("Event or notable day", keys, index=default)
day, event = options[choice]
lang = st.radio("Report language", ["en", "de"], horizontal=True, format_func=str.upper)

card = impact_card(isin, day, event)
render_card(card)


@st.cache_data(show_spinner="Writing summary…")
def text(card_json: str, lang: str) -> dict:
    return narrate_with_meta(json.loads(card_json), lang)


note = text(json.dumps(card, default=str), lang)
summary = note["text"]
st.info(summary)
if note["source"] == "llm":
    st.caption(f"✍️ Written by {note['model']} (open model via JAIF) · every number checked against the data above")
elif note["rejected"]:
    st.caption("Template text: the model's draft contained numbers that are not in the data "
               f"({', '.join(note['rejected'][:5])}), so it was not shown.")
else:
    st.caption("Template text (no language model connected)")

# Intraday chart (appears once C1 has built data/intraday_bars.parquet)
bars = data.intraday(isin)
if bars is not None:
    b = bars[bars["ts_local"].dt.date == pd.Timestamp(day).date()]
    b = b[b["ts_local"].dt.strftime("%H:%M").between("08:00", "17:45")]  # hide thin after-close trading
    if len(b):
        f = go.Figure()
        f.add_scatter(x=b["ts_local"], y=b["close"], mode="lines", name="Price")
        f.add_bar(x=b["ts_local"], y=b["volume_eur"], name="Turnover", yaxis="y2", opacity=0.35)
        o = (card.get("intraday") or {}).get("onset") or {}
        if o.get("time"):
            t_on = pd.Timestamp(f"{day} {o['time']}").tz_localize(b["ts_local"].dt.tz)
            f.add_shape(type="line", x0=t_on, x1=t_on, y0=0, y1=1, yref="paper", line=dict(color="red", dash="dash"))
            f.add_annotation(x=t_on, y=1, yref="paper", text=f"news priced from {o['time']}", showarrow=False,
                             xanchor="left", font=dict(color="red"))
        f.update_layout(height=320, yaxis2=dict(overlaying="y", side="right", showgrid=False),
                        margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h"))
        st.plotly_chart(f, width="stretch")
else:
    st.caption("Intraday chart appears once data/intraday_bars.parquet exists (C1).")

html = to_html(card, summary, lang)
c = st.columns(3)
c[0].download_button("⬇ IR snapshot (HTML)", html, file_name=f"IR_snapshot_{card['ticker']}_{day}.html", mime="text/html")
pdf = to_pdf(html)
if pdf:
    c[1].download_button("⬇ IR snapshot (PDF)", pdf, file_name=f"IR_snapshot_{card['ticker']}_{day}.pdf",
                         mime="application/pdf")
with st.expander("Raw numbers (JSON) – the AI only sees this"):
    st.json(card)
