"""Hero and value proposition component for CoverScope."""
from __future__ import annotations

import streamlit as st

from frontend.components.icons import (
    icon_bookmark,
    icon_check_circle,
    icon_file_text,
    icon_shield,
)
from frontend.utils.formatters import clean_html

PAGE_TITLE = "CoverScope"
TAGLINE = "Your policy. Made clear."


def render_hero(compact: bool = False) -> None:
    """Render the high-impact editorial hero headline and evidence visual motif.

    Parameters
    ----------
    compact : bool
        If True, renders a streamlined version when a policy is already active.
    """
    shield_icon = icon_shield(size=14, color="#0f766e")

    if compact:
        html = f"""
        <div class="cs-hero cs-hero-compact">
          <div class="cs-kicker">{shield_icon} Health Insurance, Made Understandable</div>
          <h1 class="cs-title cs-title-compact">{PAGE_TITLE}</h1>
          <div class="cs-tagline cs-tagline-compact">{TAGLINE}</div>
        </div>
        """
        st.markdown(clean_html(html), unsafe_allow_html=True)
        return

    html = f"""
    <div class="cs-hero-container">
      <div class="cs-hero-content">
        <div class="cs-kicker">
          {shield_icon} HEALTH INSURANCE, MADE UNDERSTANDABLE
        </div>
        <h1 class="cs-title">Know what your policy actually covers.</h1>
        <div class="cs-tagline"><strong>{PAGE_TITLE}</strong> &mdash; {TAGLINE}</div>
        <p class="cs-lede">
          Ask questions about your Indian health insurance policy and explore the exact clauses,
          waiting periods, and sublimits behind every answer. Backed by deterministic Python citation
          verification against your uploaded document.
        </p>
        <div class="cs-hero-microcopy">
          <span class="cs-micro-item">
            <span class="cs-micro-dot"></span>
            <span>PDF policy documents</span>
          </span>
          <span class="cs-micro-item">
            <span class="cs-micro-dot"></span>
            <span>Evidence-backed answers</span>
          </span>
          <span class="cs-micro-item">
            <span class="cs-micro-dot"></span>
            <span>Transparent limitations</span>
          </span>
        </div>
      </div>
      <div class="cs-hero-visual-card">
        <div class="cs-visual-header">
          <span class="cs-visual-tag">Audit Trail Preview</span>
          <span class="cs-visual-status">Python Verified</span>
        </div>
        <div class="cs-visual-quote-box">
          <div class="cs-visual-meta">Section 4.1 &middot; Page 18 &middot; Clause B</div>
          <div class="cs-visual-text">
            &ldquo;Expenses related to the treatment of a pre-existing disease (PED) shall be excluded until the expiry of 36 months of continuous coverage...&rdquo;
          </div>
        </div>
        <div class="cs-visual-verdict-row">
          <span class="cs-visual-badge-excluded">Excluded &lt; 36 mos</span>
          <span class="cs-visual-note">&rarr; Fully covered from Month 37</span>
        </div>
      </div>
    </div>
    """
    st.markdown(clean_html(html), unsafe_allow_html=True)


def render_value_props() -> None:
    """Render the three core product commitments on the landing view."""
    cols = st.columns(3)
    with cols[0]:
        html0 = """
        <div class="cs-card cs-card-feature">
          <div class="cs-step">01 &middot; CITED</div>
          <h3>Cited, not guessed</h3>
          <p>Every coverage verdict points directly to a verified quotation and page number from your policy.</p>
        </div>
        """
        st.markdown(clean_html(html0), unsafe_allow_html=True)
    with cols[1]:
        html1 = """
        <div class="cs-card cs-card-feature">
          <div class="cs-step">02 &middot; SAFE</div>
          <h3>Safe by default</h3>
          <p>If a citation cannot be verified in the source text, CoverScope returns a manual review flag rather than guessing.</p>
        </div>
        """
        st.markdown(clean_html(html1), unsafe_allow_html=True)
    with cols[2]:
        html2 = """
        <div class="cs-card cs-card-feature">
          <div class="cs-step">03 &middot; GROUNDED</div>
          <h3>Real policy wording</h3>
          <p>Waiting periods, exclusions, sublimits, and plan-dependent conditions are highlighted as conditional factors.</p>
        </div>
        """
        st.markdown(clean_html(html2), unsafe_allow_html=True)
    st.write("")
    st.caption(
        "Public sample wordings are bundled in the repository under `pdfs/`. "
        "Do not upload documents you are not permitted to share."
    )
