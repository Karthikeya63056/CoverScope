"""Empty state presentation components for CoverScope."""
from __future__ import annotations

import streamlit as st

from frontend.components.icons import icon_file_text, icon_search
from frontend.utils.formatters import clean_html


def render_empty_policy_guidance() -> None:
    """Render helpful initial guidance when no policy PDF has been uploaded."""
    search_icon = icon_search(size=18, color="#0f766e")
    guidance_html = f"""
    <div class="cs-card" style="margin-top: 1rem; border-style: dashed;">
      <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.35rem;">
        {search_icon}
        <h3 style="margin:0; font-size:1rem; color:#0a2233;">Ready to analyze your policy</h3>
      </div>
      <p style="font-size:0.88rem; color:#64748b; line-height:1.55;">
        Select or drag a text-based health insurance policy PDF above. Once loaded, you can ask
        coverage questions about waiting periods, pre-existing conditions, sublimits, or exclusions.
        CoverScope will evaluate only the policy wording and cite exact source clauses and page numbers.
      </p>
    </div>
    """
    st.markdown(clean_html(guidance_html), unsafe_allow_html=True)



def render_empty_answer_state() -> None:
    """Render placeholder message when a policy is loaded but no question has been asked yet."""
    st.caption("Ask a question to see a verdict with cited evidence.")


def render_empty_evidence_state() -> None:
    """Render notice when no verified quotations accompanied the verdict."""
    empty_html = """
    <div class="cs-empty-evidence-box">
      <div style="font-size:0.88rem; font-weight:600; color:#334155; margin-bottom:0.25rem;">
        No explicit matching clauses found
      </div>
      <div style="font-size:0.8rem; color:#64748b; line-height:1.5;">
        The policy wording contains no verified excerpts matching this specific topic or inquiry.
      </div>
    </div>
    """
    st.markdown(clean_html(empty_html), unsafe_allow_html=True)
    st.caption("No verified quotations were returned for this answer.")
