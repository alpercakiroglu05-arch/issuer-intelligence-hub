"""IR assistant chat.  OWNER: C4 (AI)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: E402,F401
import streamlit as st  # noqa: E402

from ai.agent import ask  # noqa: E402
from components import setup  # noqa: E402

isin = setup("Assistant")
st.title("💬 Ask the IR assistant")
st.caption("e.g. “Has our liquidity improved?” · “How do our spreads compare with the index?” · "
           "“What happened on our most unusual day?”")

hist = st.session_state.setdefault("chat", [])
for role, msg in hist:
    st.chat_message(role).write(msg)
if q := st.chat_input("Your question"):
    st.chat_message("user").write(q)
    with st.spinner("Thinking…"):
        a = ask(q, isin)
    st.chat_message("assistant").write(a)
    hist += [("user", q), ("assistant", a)]
