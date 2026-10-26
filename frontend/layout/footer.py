"""Footer and legal disclaimer layout for CoverScope."""
from __future__ import annotations

import streamlit as st

from frontend.components.icons import icon_brand_symbol
from frontend.utils.formatters import clean_html

PAGE_TITLE = "CoverScope"
TAGLINE = "Your policy. Made clear."


def render_footer() -> None:
    """Render the standardized bottom disclaimer and provenance note."""
    st.divider()
    emblem = icon_brand_symbol(size=20, color="#0f766e")
    html = f"""
    <div class="cs-footer-container">
      <div class="cs-footer-brand-row">
        <span style="display:inline-flex; align-items:center;">{emblem}</span>
        <span style="font-weight:700; color:#0a2233; font-size:0.95rem;">{PAGE_TITLE}</span>
        <span style="color:#64748b; font-size:0.85rem;">&mdash; {TAGLINE}</span>
      </div>
      <div class="cs-footer-text">
        CoverScope is an evidence-grounded policy interpretation tool designed to help policyholders understand
        dense insurance wording. Verdicts reflect the retrieved wording of the uploaded document and may omit
        endorsements or conditions stated elsewhere in the complete policy schedule. This tool does not constitute
        legal or financial advice, does not bind any insurer, and does not guarantee claim payouts. Always verify
        coverage details against your official policy schedule with your insurance company.
      </div>
    </div>
    """
    st.markdown(clean_html(html), unsafe_allow_html=True)
