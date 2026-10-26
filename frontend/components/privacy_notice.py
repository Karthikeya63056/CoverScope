"""Privacy, data handling, and provenance disclosure component for CoverScope."""
from __future__ import annotations

import streamlit as st

from frontend.components.icons import icon_lock, icon_shield
from frontend.utils.formatters import clean_html


def render_privacy_notice(expanded: bool = False) -> None:
    """Render an honest, accurate disclosure of CoverScope's data handling lifecycle.

    Accurate architectural data flow:
    - In-Memory Extraction: Uploaded PDFs are read in-memory using PyMuPDF. CoverScope
      does not write the document or extracted text to a database or local disk.
    - AI Provider Transmission: When a question is asked, only the retrieved text chunks
      most relevant to the query (top retrieved chunks) along with the question are
      transmitted over HTTPS to the configured LLM provider (Groq) for structured parsing.
    - Python Citation Verification: Model responses and quotations are deterministically
      checked against the in-memory policy text before citations are marked as verified.
    - User Privacy Guidance: Users should avoid uploading documents containing personal
      sensitive information (e.g. personal health records, Aadhaar numbers, or bank details).
    - Scope Limitation: CoverScope is an informational policy-reading aid, not an insurer
      or claim adjudicator.
    """
    lock_icon = icon_lock(size=15, color="#0f766e")

    with st.expander("Privacy & Data Handling Details", expanded=expanded):
        privacy_html = """
        <div style="font-size:0.875rem; color:#334155; line-height:1.6;">
          <p><strong>How your policy data is handled:</strong></p>
          <ul>
            <li><strong>In-memory processing:</strong> Your PDF is extracted and chunked in RAM. CoverScope does not write the document to a database or disk.</li>
            <li><strong>Retrieved excerpts sent to AI provider:</strong> When you submit a question, only the relevant policy excerpts (retrieved chunks) and your query are sent to the configured AI provider (Groq) to generate the structured answer.</li>
            <li><strong>Python verification:</strong> All citations are matched directly against the source text in Python to prevent hallucinated quotes.</li>
            <li><strong>Sensitive data advice:</strong> Health insurance wordings are public contracts, but do not upload documents containing personal medical history, personal identifiers (e.g., Aadhaar), or payment information.</li>
            <li><strong>Informational use only:</strong> CoverScope provides evidence-grounded assistance. It does not replace your insurer's official policy schedule or guarantee claim payment.</li>
          </ul>
        </div>
        """
        st.markdown(clean_html(privacy_html), unsafe_allow_html=True)



def render_compact_privacy_callout() -> None:
    """Render a compact privacy callout suited for the upload workflow."""
    st.info(
        "Privacy: your PDF is processed in memory and is not written to disk by "
        "CoverScope. The policy sections retrieved for your question are sent to "
        "the configured LLM provider (Groq) for analysis. Do not upload documents "
        "you are not permitted to share.",
        icon="🔒",
    )
