"""Main page layout wrapper for CoverScope."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import streamlit as st

from frontend.design_system.theme import apply_theme
from frontend.layout.footer import render_footer
from frontend.layout.header import PAGE_TITLE, render_brand_header, render_sidebar
from frontend.state import init_state


def setup_page() -> None:
    """Configure Streamlit page parameters, apply theme styles, and init state."""
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_theme()
    init_state()


@contextmanager
def page_container() -> Iterator[None]:
    """Provide a consistent structural container with header, content slot, and footer."""
    render_sidebar()
    render_brand_header()
    yield
    render_footer()
