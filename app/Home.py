"""Entry point:  streamlit run app/Home.py      OWNER: C3 (frontend)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # noqa: E402,F401
import streamlit as st  # noqa: E402

from components import eur, setup  # noqa: E402
from engine.baseline import kpis  # noqa: E402

isin = setup("Home")
k = kpis(isin)

st.title("Issuer Intelligence Hub")
st.markdown("**Decode your share price** – how your stock trades on Xetra, and how the market "
            "reacted to your announcements. One click, no terminal, no analyst.")

c = st.columns(4)
c[0].metric("Stock", f"{k['ticker']} ({k['index']})")
c[1].metric("Median daily turnover (60d)", eur(k["median_turnover_eur"]["stock"]),
            f"index median {eur(k['median_turnover_eur']['index_median'])}", delta_color="off")
c[2].metric("Liquidity category (est.)", k["liquidity_check"]["category_estimate"] or "n/a")
c[3].metric("Unusual days (60d)", k["anomaly_days_last_period"])

st.divider()
cols = st.columns(4)
cols[0].page_link("pages/1_Dashboard.py", label="Dashboard – the normal state", icon="📊")
cols[1].page_link("pages/2_Impact_Card.py", label="Impact card – one event", icon="⚡")
cols[2].page_link("pages/3_Compare.py", label="Compare events", icon="📐")
cols[3].page_link("pages/4_Assistant.py", label="Ask the IR assistant", icon="💬")
