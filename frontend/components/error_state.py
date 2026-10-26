"""Sanitized error presentation components for CoverScope."""
from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from frontend.messages import describe_llm_error


def render_document_error(error: Mapping[str, Any] | None) -> None:
    """Render safe user error feedback if the selected PDF failed preparation.

    Parameters
    ----------
    error : Mapping[str, Any], optional
        Dictionary containing 'message', 'errors', and 'warnings' tuples.
    """
    if not error:
        return

    message = error.get("message", "This PDF could not be processed.")
    st.error(message, title="This PDF could not be used")

    detail_errors = error.get("errors")
    if detail_errors:
        st.markdown("**What to check**")
        for item in detail_errors:
            st.markdown(f"- {item}")

    st.caption(
        "The document was rejected, not truncated. Try a text-based PDF within the "
        "size and extracted-text limits."
    )


def render_answer_error(
    error_message: str | None,
    *,
    cooldown_seconds: int = 0,
) -> None:
    """Render sanitized error notice if the Q&A workflow failed.

    Parameters
    ----------
    error_message : str, optional
        Safe user-facing error copy (from frontend.messages.describe_llm_error).
    cooldown_seconds : int
        Remaining rate limit cooldown seconds, if applicable.
    """
    if not error_message:
        return

    st.error(error_message, title="Could not answer")

    if cooldown_seconds > 0:
        st.info(
            f"The AI provider rate limit was reached. Try again in about "
            f"{cooldown_seconds} seconds; CoverScope will not retry automatically.",
            icon="⏳",
        )


def render_empty_question_warning() -> None:
    """Alert user that a question is required before submission."""
    st.warning("Enter a question first.")


def render_cooldown_warning() -> None:
    """Alert user that provider rate limit is currently active."""
    st.warning("Please wait for the rate-limit cooldown before asking again.")
