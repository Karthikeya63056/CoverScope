"""Answer summary component for CoverScope."""
from __future__ import annotations

import streamlit as st

from frontend.messages import NOT_STATED_MESSAGE
from frontend.utils.formatters import escape_md


def render_answer_summary(
    answer_text: str,
    *,
    question: str | None = None,
    is_not_stated: bool = False,
) -> None:
    """Render the detailed model answer narrative and relevant guidance.

    Parameters
    ----------
    answer_text : str
        The generated answer text explaining the verdict and policy findings.
    question : str, optional
        The user question that was answered.
    is_not_stated : bool
        Whether the verdict is 'not_stated', requiring explicit clarification.
    """
    if question:
        st.caption(f"Question: {question}")

    st.markdown("#### Answer")
    if answer_text and answer_text.strip():
        st.markdown(answer_text)
    else:
        st.caption("No answer explanation was provided.")

    if is_not_stated:
        st.info(NOT_STATED_MESSAGE)
