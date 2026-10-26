"""Brand header and navigation layout for CoverScope."""
from __future__ import annotations

import streamlit as st

from backend.config import settings
from frontend.components.icons import icon_brand_symbol, icon_shield
from frontend.state import DOC_KEY, reset_app
from frontend.utils.formatters import clean_html

PAGE_TITLE = "CoverScope"
TAGLINE = "Your policy. Made clear."


def render_brand_header() -> None:
    """Render the top brand navigation bar with custom InsurTech identity."""
    brand_emblem = icon_brand_symbol(size=30, color="#0f766e")
    html = f"""
    <div class="cs-header-bar">
      <div class="cs-brand-cluster">
        {brand_emblem}
        <div>
          <div class="cs-brand-name">{PAGE_TITLE}</div>
          <div class="cs-brand-sublabel">Evidence-Grounded Policy Intelligence</div>
        </div>
        <span class="cs-brand-tag">InsurTech AI</span>
      </div>
      <div class="cs-header-right">
        <span class="cs-live-pill">
          <span class="cs-live-dot"></span>
          <span>Grounded in policy text</span>
        </span>
        <span class="cs-tagline-header">{TAGLINE}</span>
      </div>
    </div>
    """
    st.markdown(clean_html(html), unsafe_allow_html=True)


def render_sidebar() -> None:
    """Render the persistent sidebar with status and system overview."""
    with st.sidebar:
        brand_emblem = icon_brand_symbol(size=32, color="#0f766e")
        html = f"""
        <div style="display:flex; align-items:center; gap:0.65rem; margin-bottom:0.25rem;">
          {brand_emblem}
          <div>
            <span style="font-size:1.35rem; font-weight:800; color:#0a2233; letter-spacing:-0.03em;">{PAGE_TITLE}</span>
            <div style="font-size:0.75rem; color:#0f766e; font-weight:600;">{TAGLINE}</div>
          </div>
        </div>
        """
        st.markdown(clean_html(html), unsafe_allow_html=True)

        st.divider()

        st.markdown("**How CoverScope works**")
        st.markdown(
            "1. **Upload** an Indian health insurance policy PDF\n"
            "2. **Ask** a plain-English coverage question\n"
            "3. **Inspect** the verbatim cited clause & page"
        )
        st.divider()

        st.markdown("**Engine parameters**")
        st.caption(f"Provider model: `{settings.groq_model}`")
        st.caption(f"Evidence retrieval window: top {settings.retrieval_top_k} chunks")
        st.caption("Verification: Python verbatim substring matching")

        if st.session_state.get(DOC_KEY) is not None:
            st.divider()
            st.button(
                "Start a new document",
                on_click=reset_app,
                use_container_width=True,
                key="start_over",
            )

        st.divider()
        if st.button("Replay cinematic intro", use_container_width=True, key="replay_intro"):
            st.session_state["cs_replay_intro"] = True
            st.rerun()


        st.divider()
        st.caption(
            "CoverScope is an informational reading tool, not insurance advice or a claim "
            "determination. Always verify against the policy schedule with your insurer."
        )
