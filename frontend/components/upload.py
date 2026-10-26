"""Policy PDF upload component for CoverScope."""
from __future__ import annotations

from typing import Any

import streamlit as st

from backend.config import settings
from frontend.components.icons import icon_alert_triangle, icon_lock, icon_upload
from frontend.state import DOC_ERROR_KEY, DOC_KEY, UPLOADER_VERSION_KEY
from frontend.utils.formatters import format_bytes


def render_uploader() -> Any:
    """Render the native Streamlit PDF file uploader with styling and constraints.

    Returns
    -------
    UploadedFile or None
        The uploaded file object if selected by the user.
    """
    doc = st.session_state.get(DOC_KEY)
    is_loaded = doc is not None

    expander_title = "Upload a different policy" if is_loaded else "Upload a policy PDF"
    upload_icon = icon_upload(size=18, color="#0f766e")

    with st.expander(expander_title, expanded=not is_loaded):
        st.markdown(
            f"""
            <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.4rem;">
              {upload_icon}
              <span style="font-weight:600; color:#0a2233; font-size:0.95rem;">
                {"Replace current policy" if is_loaded else "Select policy document"}
              </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        uploaded = st.file_uploader(
            "Choose a text-based health insurance policy",
            type=["pdf"],
            key=f"policy_upload_{st.session_state[UPLOADER_VERSION_KEY]}",
            max_upload_size=max(1, settings.max_upload_bytes // 1_000_000),
            help=(
                "PDF only. Scanned or image-only PDFs are rejected because OCR is "
                "not supported. Oversized documents are rejected, never truncated."
            ),
        )

        st.caption(
            f"PDF only · up to {format_bytes(settings.max_upload_bytes)} and "
            f"{settings.max_extracted_chars:,} extracted characters."
        )

        st.info(
            "Privacy: your PDF is processed in memory and is not written to disk by "
            "CoverScope. The policy sections retrieved for your question are sent to "
            "the configured LLM provider (Groq) for analysis. Do not upload documents "
            "you are not permitted to share.",
            icon="🔒",
        )

    return uploaded


def render_upload_error() -> None:
    """Render safe user error feedback if the selected PDF failed preparation."""
    error = st.session_state.get(DOC_ERROR_KEY)
    if not error:
        return

    st.error(error["message"], title="This PDF could not be used")
    if error.get("errors"):
        st.markdown("**What to check**")
        for item in error["errors"]:
            st.markdown(f"- {item}")
    st.caption(
        "The document was rejected, not truncated. Try a text-based PDF within the "
        "size and extracted-text limits."
    )
