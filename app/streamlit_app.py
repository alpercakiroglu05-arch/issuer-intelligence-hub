"""Streamlit demo UI. Run from the repo root:  streamlit run app/streamlit_app.py"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # make core/ importable

import streamlit as st  # noqa: E402

from core.audit import read_events  # noqa: E402
from core.documents import extract_text, list_scenarios  # noqa: E402
from core.llm import model, provider  # noqa: E402
from core.pipeline import analyze, record_decision  # noqa: E402

APP_NAME = "Project Name"  # TODO: rename once the idea is fixed
TAGLINE = "AI copilot that turns hours of manual review into minutes, with a human in control."

RISK_BADGE = {"low": "🟢 Low", "medium": "🟠 Medium", "high": "🔴 High"}

st.set_page_config(page_title=APP_NAME, page_icon="🏦", layout="wide")
st.title(APP_NAME)
st.caption(TAGLINE)

with st.sidebar:
    st.subheader("Input")
    scenarios = list_scenarios()
    source = st.radio("Source", ["Demo scenario", "Upload file", "Paste text"], index=0)
    document, source_name = "", ""
    if source == "Demo scenario" and scenarios:
        source_name = st.selectbox("Scenario", list(scenarios))
        document = scenarios[source_name]
    elif source == "Upload file":
        upload = st.file_uploader("PDF or TXT", type=["pdf", "txt"])
        if upload:
            source_name, document = upload.name, extract_text(upload.name, upload.read())
    else:
        source_name = "pasted text"
        document = st.text_area("Document text", height=250)
    reviewer = st.text_input("Reviewer", value="Analyst")
    st.divider()
    st.caption(f"Model: `{provider()}:{model()}`")

left, right = st.columns([2, 3])

with left:
    st.subheader("Document")
    st.text_area("Content", document, height=420, disabled=True, label_visibility="collapsed")
    if st.button("Analyze", type="primary", disabled=not document.strip(), width="stretch"):
        with st.spinner("Analyzing..."):
            st.session_state["result"] = analyze(document, source_name)

with right:
    st.subheader("AI assessment")
    result = st.session_state.get("result")
    if not result:
        st.info("Pick a scenario and press **Analyze**.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Risk", RISK_BADGE.get(result.risk_level, result.risk_level))
        c2.metric("Findings", len(result.findings))
        c3.metric("Human review", "Required" if result.needs_human_review else "Optional")
        st.write(result.summary)

        for f in result.findings:
            with st.expander(f"{RISK_BADGE.get(f.severity, f.severity)} — {f.issue}"):
                st.markdown(f"> {f.evidence}")
        if result.missing_information:
            st.warning("Missing: " + "; ".join(result.missing_information))
        st.markdown(f"**Recommended action:** {result.recommended_action}")

        st.divider()
        st.markdown("**Your decision** (the AI never decides on its own)")
        comment = st.text_input("Comment", key=f"comment_{result.case_id}")
        b1, b2, b3 = st.columns(3)
        for col, label in ((b1, "approve"), (b2, "escalate"), (b3, "reject")):
            if col.button(label.title(), width="stretch", key=f"{label}_{result.case_id}"):
                record_decision(result.case_id, label, reviewer, comment)
                st.success(f"Decision '{label}' recorded for case {result.case_id}.")

        with st.expander("Audit trail for this case"):
            st.dataframe(
                [
                    {"time": e["timestamp"], "event": e["event_type"], "actor": e["actor"]}
                    for e in read_events(result.case_id)
                ],
                width="stretch",
            )
