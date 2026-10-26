"""Hero and value proposition component for CoverScope."""
from __future__ import annotations

import streamlit as st

from frontend.components.icons import icon_shield

PAGE_TITLE = "CoverScope"
TAGLINE = "Your policy. Made clear."


def render_hero(compact: bool = False) -> None:
    """Render the hero headline and value proposition.

    Parameters
    ----------
    compact : bool
        If True, renders a streamlined version when a policy is already active.
    """
    shield_icon = icon_shield(size=14, color="#0f766e")

    if compact:
        st.markdown(
            f"""
            <div class="cs-hero cs-hero-compact" style="padding: 0.25rem 0 0.85rem;">
              <div class="cs-kicker">{shield_icon} Evidence-grounded policy Q&amp;A</div>
              <h1 class="cs-title" style="font-size: 2.1rem; margin-top: 0.15rem;">{PAGE_TITLE}</h1>
              <div class="cs-tagline" style="font-size: 1.05rem; margin-top: 0.15rem;">{TAGLINE}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"""
        <div class="cs-hero">
          <div class="cs-kicker">{shield_icon} Evidence-grounded policy Q&amp;A</div>
          <h1 class="cs-title">{PAGE_TITLE}</h1>
          <div class="cs-tagline">{TAGLINE}</div>
          <p class="cs-lede">
            Upload an Indian health insurance policy PDF and ask questions in plain English.
            CoverScope retrieves relevant clauses, checks quotations against the policy text,
            and highlights exact page citations so you can verify coverage with confidence.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_value_props() -> None:
    """Render the three core product commitments on the landing view."""
    cols = st.columns(3)
    with cols[0]:
        st.markdown(
            """
            <div class="cs-card">
              <div class="cs-step">01 · CITED</div>
              <h3>Cited, not guessed</h3>
              <p>Every coverage verdict points directly to a verified quotation and page number from your policy.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(
            """
            <div class="cs-card">
              <div class="cs-step">02 · SAFE</div>
              <h3>Safe by default</h3>
              <p>If a citation cannot be verified in the source text, CoverScope returns a manual review flag rather than guessing.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with cols[2]:
        st.markdown(
            """
            <div class="cs-card">
              <div class="cs-step">03 · GROUNDED</div>
              <h3>Real policy wording</h3>
              <p>Waiting periods, exclusions, sublimits, and plan-dependent conditions are highlighted as conditional factors.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.write("")
    st.caption(
        "Public sample wordings are bundled in the repository under `pdfs/`. "
        "Do not upload documents you are not permitted to share."
    )
