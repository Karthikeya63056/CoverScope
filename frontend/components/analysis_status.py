"""Honest analysis status and error messaging component for CoverScope."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import streamlit as st

from frontend.components.icons import icon_alert_triangle, icon_info

ANALYSIS_SPINNER_MESSAGE = (
    "Retrieving policy evidence and checking every citation against the text…"
)


@contextmanager
def analysis_spinner(
    message: str = ANALYSIS_SPINNER_MESSAGE,
) -> Iterator[None]:
    """Provide honest analysis progress feedback during workflow execution.

    CoverScope uses a single atomic backend workflow (retrieval -> LLM structured
    generation -> Python citation verification). We do not invent fake intermediate
    percentage increments or simulated multi-step progress bars.
    """
    with st.spinner(message):
        yield


def render_cooldown_notice(remaining_seconds: int) -> None:
    """Render rate-limit cooldown notice with clear non-retrying guidance."""
    if remaining_seconds <= 0:
        return

    st.info(
        f"The AI provider rate limit was reached. Try again in about "
        f"{remaining_seconds} seconds; CoverScope will not retry automatically.",
        icon="⏳",
    )


def render_provider_error(error_message: str | None) -> None:
    """Render a sanitized error notice if the Q&A workflow failed."""
    if not error_message:
        return

    st.error(error_message, title="Could not answer")
