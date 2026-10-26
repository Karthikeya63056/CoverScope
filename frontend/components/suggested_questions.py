"""Suggested policy questions component for CoverScope."""
from __future__ import annotations

from typing import Callable, Sequence

import streamlit as st

from frontend.messages import SUGGESTED_QUESTIONS
from frontend.state import use_suggestion


def render_suggested_questions(
    suggestions: Sequence[str] = SUGGESTED_QUESTIONS,
    on_select: Callable[[str], None] = use_suggestion,
) -> None:
    """Render one-click sample policy questions in a responsive grid.

    Parameters
    ----------
    suggestions : Sequence[str]
        The list of suggested questions to display.
    on_select : Callable[[str], None]
        Callback invoked when a suggestion button is clicked.
    """
    st.caption("Suggested questions")
    suggestion_columns = st.columns(2)

    for index, suggestion in enumerate(suggestions):
        suggestion_columns[index % 2].button(
            suggestion,
            key=f"suggestion_{index}",
            on_click=on_select,
            args=(suggestion,),
            use_container_width=True,
        )
