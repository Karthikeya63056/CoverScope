"""Policy PDF upload component for CoverScope."""
from __future__ import annotations

from typing import Any

import streamlit as st

from backend.config import settings
from frontend.components.error_state import render_document_error
from frontend.components.icons import icon_alert_triangle, icon_file_text, icon_lock, icon_upload
from frontend.components.privacy_notice import render_compact_privacy_callout
from frontend.state import DOC_ERROR_KEY, DOC_KEY, UPLOADER_VERSION_KEY
from frontend.utils.formatters import clean_html, format_bytes


def render_uploader() -> Any:
    """Render the native Streamlit PDF file uploader with premium styling and constraints.

    Returns
    -------
    UploadedFile or None
        The uploaded file object if selected by the user.
    """
    doc = st.session_state.get(DOC_KEY)
    is_loaded = doc is not None

    expander_title = "Upload a different policy document" if is_loaded else "Start with your policy document"
    upload_icon = icon_upload(size=18, color="#0f766e")

    with st.expander(expander_title, expanded=not is_loaded):
        header_html = f"""
        <div class="cs-upload-header-row">
          <span class="cs-upload-icon-badge">{upload_icon}</span>
          <div>
            <h3 class="cs-upload-title">{"Replace current policy" if is_loaded else "Start with your policy"}</h3>
            <p class="cs-upload-subtext">
              Upload an Indian health insurance policy wording or schedule in text-based PDF format.
            </p>
          </div>
        </div>
        """
        st.markdown(clean_html(header_html), unsafe_allow_html=True)

        uploaded = st.file_uploader(
            "Choose a text-based health insurance policy",
            type=["pdf"],
            key=f"policy_upload_{st.session_state[UPLOADER_VERSION_KEY]}",
            max_upload_size=max(1, settings.max_upload_bytes // 1_000_000),
            help=(
                "PDF only. Scanned or image-only PDFs are rejected because OCR is "
                "not supported. Oversized documents are rejected, never truncated."
            ),
            label_visibility="collapsed",
        )

        constraints_html = f"""
        <div class="cs-upload-constraints">
          <span class="cs-constraint-chip">PDF format only</span>
          <span class="cs-constraint-chip">Up to {format_bytes(settings.max_upload_bytes)}</span>
          <span class="cs-constraint-chip">Max {settings.max_extracted_chars:,} extracted characters</span>
          <span class="cs-constraint-chip cs-constraint-warn">Text-based (OCR not supported)</span>
        </div>
        """
        st.markdown(clean_html(constraints_html), unsafe_allow_html=True)

        render_compact_privacy_callout()

    return uploaded



def render_upload_error() -> None:
    """Render safe user error feedback if the selected PDF failed preparation."""
    error = st.session_state.get(DOC_ERROR_KEY)
    render_document_error(error)
