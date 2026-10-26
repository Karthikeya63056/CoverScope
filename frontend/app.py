"""Temporary Phase 1 UI entry point. Full Q&A workflow comes in later phases."""
import streamlit as st

st.set_page_config(page_title="CoverScope", page_icon="🛡️", layout="wide")
st.title("CoverScope")
st.caption("Your policy. Made clear.")
st.info(
    "Phase 1 is focused on validating PDF extraction. The question-answering "
    "workflow will be added after sample documents and extraction quality are verified."
)
uploaded = st.file_uploader("Upload a text-based health insurance policy PDF", type=["pdf"])
if uploaded is not None:
    st.write(f"Selected file: **{uploaded.name}** ({uploaded.size:,} bytes)")
    st.warning(
        "Do not upload sensitive personal documents to an unsecured demo. "
        "Extraction validation is not yet wired into this temporary interface."
    )
