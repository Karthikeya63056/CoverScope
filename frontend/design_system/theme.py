"""Theme manager and CSS loader for CoverScope."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import streamlit as st

CSS_PATH = Path(__file__).resolve().parent / "global.css"


@lru_cache(maxsize=1)
def load_global_css() -> str:
    """Read the design system's CSS file once."""
    if CSS_PATH.exists():
        return CSS_PATH.read_text(encoding="utf-8")
    return ""


def apply_theme() -> None:
    """Inject global CSS rules into the Streamlit document."""
    css = load_global_css()
    if css:
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
