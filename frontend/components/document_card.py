"""Document workspace card displaying verified metadata of an uploaded policy."""
from __future__ import annotations

from typing import Any

import streamlit as st

from frontend.components.icons import icon_check_circle, icon_file_text
from frontend.utils.formatters import clean_html
from frontend.utils.view_models import DocumentViewModel


def render_document_card(policy: Any) -> None:
    """Render the active policy workspace summary with verified document metadata.

    Parameters
    ----------
    policy : ProcessedPolicy or Any
        The prepared policy document containing extraction and quality metadata.
    """
    if policy is None:
        return

    vm = DocumentViewModel.from_policy(policy)
    file_icon = icon_file_text(size=22, color="#0f766e")
    check_icon = icon_check_circle(size=13, color="#15803d")

    with st.container(border=True):
        header_col, status_col = st.columns([5, 1])
        with header_col:
            doc_header_html = f"""
            <div class="cs-doc-title-cluster">
              <div class="cs-doc-icon-badge">{file_icon}</div>
              <div>
                <h3 class="cs-doc-name">{vm.escaped_filename}</h3>
                <div class="cs-doc-subtext">
                  <span>{vm.status_label}</span>
                  <span class="cs-doc-dot">&bull;</span>
                  <span>Extracted in memory</span>
                </div>
              </div>
            </div>
            """
            st.markdown(clean_html(doc_header_html), unsafe_allow_html=True)

        with status_col:
            st.markdown(
                f'<span class="cs-chip cs-chip-ok">'
                f'<span style="display:inline-flex; align-items:center;">{check_icon}</span>'
                '<span>Ready</span></span>',
                unsafe_allow_html=True,
            )

        # Primary and secondary document metrics
        columns = st.columns(4)
        columns[0].metric("Pages", vm.page_count_display)
        columns[1].metric(
            "Extracted text",
            vm.extracted_characters_display,
            help=(
                "Characters of selectable text. Documents exceeding configured limits "
                "are rejected, never truncated."
            ),
        )
        columns[2].metric("Searchable chunks", vm.chunk_count_display)
        columns[3].metric("File size", vm.file_size_display)

        # Extraction quality notices (text-poor or table-dense pages)
        if vm.text_poor_pages:
            pages_list = ", ".join(map(str, vm.text_poor_pages))
            st.warning(
                f"Low-text pages: {pages_list}. Review these pages manually if "
                "relevant to your question.",
                icon="📄",
            )

        if vm.table_review_pages:
            tables_list = ", ".join(map(str, vm.table_review_pages))
            st.warning(
                f"Possible table / multi-column pages for manual review: {tables_list}. "
                "Text extraction does not guarantee table row/column order.",
                icon="📊",
            )


        if vm.quality_warnings:
            with st.expander("Extraction notes"):
                for warning in vm.quality_warnings:
                    st.markdown(f"- {warning}")
