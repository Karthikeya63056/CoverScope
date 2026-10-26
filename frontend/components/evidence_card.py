"""Evidence and citation card components for CoverScope."""
from __future__ import annotations

from typing import Any, Sequence

import streamlit as st

from frontend.components.empty_state import render_empty_evidence_state
from frontend.components.icons import icon_alert_triangle, icon_bookmark, icon_check_circle
from frontend.utils.formatters import blockquote


def render_evidence_card(
    citation: Any,
    *,
    index: int | None = None,
) -> None:
    """Render a single verified or unverified citation block.

    Parameters
    ----------
    citation : VerifiedCitation or Any
        The citation object containing chunk_id, page_number, quote, and verified flag.
    index : int, optional
        1-based index or display index for the citation.
    """
    if citation is None:
        return

    # Extract metadata safely without inventing values
    raw_page = getattr(citation, "page_number", None)
    page_text = f"Page {raw_page}" if raw_page is not None and raw_page > 0 else "Page unlisted"

    chunk_id = getattr(citation, "chunk_id", "") or "Source chunk unlisted"
    is_verified = bool(getattr(citation, "verified", True))
    warning = getattr(citation, "warning", None)
    quote = getattr(citation, "quote", "") or ""

    with st.container(border=True):
        header_col, status_col = st.columns([4, 1])

        with header_col:
            st.markdown(
                f'<span class="cs-cite-meta">{page_text} · {chunk_id}</span>',
                unsafe_allow_html=True,
            )

        with status_col:
            if is_verified:
                st.markdown(
                    '<span class="cs-chip cs-chip-ok">'
                    f'<span style="display:inline-flex; align-items:center;">{icon_check_circle(size=12, color="#15803d")}</span>'
                    '<span>Verified</span></span>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<span class="cs-chip cs-chip-warn">'
                    f'<span style="display:inline-flex; align-items:center;">{icon_alert_triangle(size=12, color="#b45309")}</span>'
                    '<span>Unverified</span></span>',
                    unsafe_allow_html=True,
                )

        if warning:
            st.caption(f"Citation note: {warning}")

        # Render verbatim quotation using native markdown blockquote
        # Do not use unsafe_allow_html for untrusted policy document text
        if quote.strip():
            st.markdown(blockquote(quote))
        else:
            st.caption("No quotation text was attached to this citation.")


def render_evidence_section(
    citations: Sequence[Any] = (),
) -> None:
    """Render the evidence section header and cards for all citations.

    Parameters
    ----------
    citations : Sequence[Any]
        The sequence of VerifiedCitation objects associated with the answer.
    """
    st.markdown("#### Cited evidence")

    if not citations:
        render_empty_evidence_state()
        return

    for idx, citation in enumerate(citations, start=1):
        render_evidence_card(citation, index=idx)
