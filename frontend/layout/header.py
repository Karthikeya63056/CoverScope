"""Brand header and navigation layout for CoverScope."""
from __future__ import annotations

import streamlit as st

from backend.config import settings
from frontend.components.icons import icon_shield
from frontend.state import DOC_KEY, reset_app

PAGE_TITLE = "CoverScope"
TAGLINE = "Your policy. Made clear."


def render_brand_header() -> None:
    """Render the top brand navigation bar."""
    shield_svg = icon_shield(size=22, color="#0f766e")
    st.markdown(
        f"""
        <div class="cs-header-bar">
          <div class="cs-brand-cluster">
            <span style="display:flex; align-items:center;">{shield_svg}</span>
            <span class="cs-brand-name">{PAGE_TITLE}</span>
            <span class="cs-brand-tag">Evidence-Grounded</span>
          </div>
          <div style="font-size:0.85rem; color:#64748b; font-weight:500;">
            {TAGLINE}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    """Render the persistent sidebar with status and system overview."""
    with st.sidebar:
        shield_svg = icon_shield(size=24, color="#0f766e")
        st.markdown(
            f"""
            <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.25rem;">
              {shield_svg}
              <span style="font-size:1.35rem; font-weight:800; color:#0a2233;">{PAGE_TITLE}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(TAGLINE)
        st.divider()

        st.markdown("**How it works**")
        st.markdown(
            "1. **Upload** a text-based policy PDF\n"
            "2. **Ask** a coverage or exclusion question\n"
            "3. **Verify** citations against cited page wording"
        )
        st.divider()

        st.caption(f"Model: `{settings.groq_model}`")
        st.caption(f"Evidence window: top {settings.retrieval_top_k} retrieved chunks")

        if st.session_state.get(DOC_KEY) is not None:
            st.button(
                "Start a new document",
                on_click=reset_app,
                use_container_width=True,
                key="start_over",
            )

        st.divider()
        st.caption(
            "CoverScope is an informational tool, not insurance advice or a claim "
            "decision. Always verify against the policy schedule and your insurer."
        )
