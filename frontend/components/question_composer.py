"""Question entry and composer component for CoverScope."""
from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from frontend.components.analysis_status import render_cooldown_notice
from frontend.components.suggested_questions import render_suggested_questions
from frontend.messages import MAX_QUESTION_CHARS
from frontend.state import (
    AUTO_ASK_KEY,
    QUESTION_KEY,
    cooldown_remaining,
    run_question,
    use_suggestion,
)


def render_question_composer(
    policy: Any,
    on_submit: Callable[[Any, str], None] = run_question,
) -> None:
    """Render the policy question input composer, suggested questions, and action button.

    Parameters
    ----------
    policy : ProcessedPolicy or Any
        The active loaded policy object.
    on_submit : Callable[[Any, str], None]
        Handler invoked when the user submits a valid question.
    """
    st.markdown("## Ask about this policy")
    st.caption("What would you like to understand about coverage, waiting periods, or limits?")

    # Render 1-click suggested questions
    render_suggested_questions(on_select=use_suggestion)

    question = st.text_area(
        "Your question",
        key=QUESTION_KEY,
        height=96,
        max_chars=MAX_QUESTION_CHARS,
        placeholder="e.g. Is a pre-existing disease covered in month 20?",
        help=f"Ask a plain English coverage question. Max {MAX_QUESTION_CHARS} characters.",
    )

    cooldown = cooldown_remaining()
    if cooldown > 0:
        render_cooldown_notice(cooldown)

    ask_clicked = st.button(
        "Ask CoverScope",
        type="primary",
        key="ask_button",
    )
    auto_ask = bool(st.session_state.pop(AUTO_ASK_KEY, False))

    if ask_clicked or auto_ask:
        if cooldown > 0:
            st.warning("Please wait for the rate-limit cooldown before asking again.")
        elif not question or not question.strip():
            st.warning("Enter a question first.")
        else:
            on_submit(policy, question.strip())
