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
etype = st.selectbox("Event type", ["Q1", "H1", "Q3", "FY", "DIVIDEND_EX", "ADHOC", "GUIDANCE"])
index = st.selectbox("Universe", ["DAX", "MDAX", "SDAX", "all"])
try:
    table = compare.same_type_events(etype, None if index == "all" else index)
    st.dataframe(table, width="stretch", hide_index=True)
    # TODO C3: scatter abn_ret vs vol_ratio, highlight the selected stock
except NotImplementedError as e:
    st.info(f"Coming soon – {e}")
