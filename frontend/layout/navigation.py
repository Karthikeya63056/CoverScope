"""Unified workspace navigation component for CoverScope."""
from __future__ import annotations

import streamlit as st

from frontend.components.icons import icon_bookmark, icon_file_text, icon_search
from frontend.state import (
    ACTIVE_FP_KEY,
    ACTIVE_VIEW_KEY,
    DOC_KEY,
    NAV_CHOICE_KEY,
    REGISTRY_KEY,
    VIEW_ASK,
    VIEW_EXPLORER,
    VIEW_LIBRARY,
    VIEW_SCENARIO,
    VIEW_COMPARISON,
    get_active_policy,
    get_registry,
    set_active_view,
)
from frontend.utils.formatters import clean_html, escape_md

NAV_OPTIONS: list[str] = [
    "Ask My Policy",
    "Policy Explorer",
    "Scenario Analyzer",
    "Policy Comparison",
    "Document Library",
]

VIEW_TO_LABEL: dict[str, str] = {
    VIEW_ASK: "Ask My Policy",
    VIEW_EXPLORER: "Policy Explorer",
    VIEW_SCENARIO: "Scenario Analyzer",
    VIEW_COMPARISON: "Policy Comparison",
    VIEW_LIBRARY: "Document Library",
}

LABEL_TO_VIEW: dict[str, str] = {
    "Ask My Policy": VIEW_ASK,
    "Policy Explorer": VIEW_EXPLORER,
    "Scenario Analyzer": VIEW_SCENARIO,
    "Policy Comparison": VIEW_COMPARISON,
    "Document Library": VIEW_LIBRARY,
}


def render_navigation() -> str:
    """Render the top platform workspace switcher and active document context pill.

    Returns
    -------
    str
        The currently active view identifier ('ask', 'explorer', 'scenario', 'library').
    """
    if "_pending_nav_choice" in st.session_state:
        st.session_state[NAV_CHOICE_KEY] = st.session_state.pop("_pending_nav_choice")

    if NAV_CHOICE_KEY in st.session_state and st.session_state[NAV_CHOICE_KEY] in LABEL_TO_VIEW:
        st.session_state[ACTIVE_VIEW_KEY] = LABEL_TO_VIEW[st.session_state[NAV_CHOICE_KEY]]
    elif ACTIVE_VIEW_KEY in st.session_state and st.session_state[ACTIVE_VIEW_KEY] in VIEW_TO_LABEL:
        st.session_state[NAV_CHOICE_KEY] = VIEW_TO_LABEL[st.session_state[ACTIVE_VIEW_KEY]]
    else:
        st.session_state[NAV_CHOICE_KEY] = "Ask My Policy"
        st.session_state[ACTIVE_VIEW_KEY] = VIEW_ASK

    current_view = st.session_state[ACTIVE_VIEW_KEY]
    active_doc = get_active_policy()
    reg = get_registry()
    total_docs = len(reg)

    nav_col, info_col = st.columns([3, 2])

    with nav_col:
        choice = st.segmented_control(
            "Workspace",
            options=NAV_OPTIONS,
            key=NAV_CHOICE_KEY,
            label_visibility="collapsed",
            help="Select workspace: Ask My Policy, Policy Explorer, Scenario Analyzer, or Document Library",
        )
        if choice and choice in LABEL_TO_VIEW:
            current_view = LABEL_TO_VIEW[choice]
            st.session_state[ACTIVE_VIEW_KEY] = current_view

    with info_col:
        if active_doc is not None:
            doc_name = escape_md(active_doc.filename)
            pages = active_doc.page_count
            multi_hint = f" ({total_docs} in library)" if total_docs > 1 else ""
            status_html = f"""
            <div class="cs-nav-active-pill">
              <span class="cs-live-dot" style="background:#0f766e;"></span>
              <span class="cs-nav-active-text">Active: <strong>{doc_name}</strong> ({pages} pages{multi_hint})</span>
            </div>
            """
            st.markdown(clean_html(status_html), unsafe_allow_html=True)
        else:
            status_html = """
            <div class="cs-nav-active-pill cs-nav-no-doc">
              <span class="cs-nav-active-text">No active policy loaded</span>
            </div>
            """
            st.markdown(clean_html(status_html), unsafe_allow_html=True)

    return current_view
