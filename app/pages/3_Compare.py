"""Compare events of the same type.  OWNER: C3 (frontend) once C2 delivers engine/compare.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: E402,F401
import streamlit as st  # noqa: E402

from components import setup  # noqa: E402
from engine import compare  # noqa: E402

isin = setup("Compare")
st.title("📐 Compare events of the same type")
etype = st.selectbox("Event type", ["NOTABLE_DAY", "Q1", "H1", "Q3", "FY", "DIVIDEND_EX", "ADHOC", "GUIDANCE"])
index = st.selectbox("Universe", ["DAX", "MDAX", "SDAX", "all"])
with st.spinner("Building comparison table (first load per universe takes a few seconds)…"):
    table = compare.same_type_events(etype, None if index == "all" else index)
if table.empty:
    st.info("No events to compare for this selection.")
else:
    if etype != compare.NOTABLE and (table["source"] == "notable_day").all():
        st.caption(f"Fewer than {compare.MIN_EVENTS} verified {etype} events in events.csv, "
                   "so this shows the notable trading days of the universe instead.")
    st.dataframe(table, width="stretch", hide_index=True)
    # TODO C3: scatter abn_ret vs vol_ratio, highlight the selected stock
