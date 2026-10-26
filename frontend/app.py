"""CoverScope Streamlit app.

Entry point:
    streamlit run frontend/app.py
"""
from __future__ import annotations

from pathlib import Path
import sys

import streamlit as st

# Streamlit adds the script directory to sys.path; add repository root so
# the backend package is importable without requiring explicit PYTHONPATH.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.qa.answer import AnswerResult
from backend.qa.workflow import ProcessedPolicy
from frontend.components.hero import render_hero, render_value_props
from frontend.components.icons import (
    icon_alert_triangle,
    icon_bookmark,
    icon_check_circle,
    icon_help_circle,
    icon_lock,
    icon_shield,
    icon_upload,
    icon_x_circle,
)
from frontend.components.upload import render_upload_error, render_uploader
from frontend.layout.footer import render_footer
from frontend.layout.header import (
    PAGE_TITLE,
    TAGLINE,
    render_brand_header,
    render_sidebar,
)
from frontend.layout.page import setup_page
from frontend.messages import (
    CONFIDENCE_LABELS,
    MANUAL_REVIEW_MESSAGE,
    MAX_QUESTION_CHARS,
    NOT_STATED_MESSAGE,
    SUGGESTED_QUESTIONS,
    VERDICT_LABELS,
    VERDICT_SUMMARIES,
)
from frontend.state import (
    AUTO_ASK_KEY,
    COOLDOWN_KEY,
    DOC_ERROR_KEY,
    DOC_FP_KEY,
    DOC_KEY,
    ERROR_KEY,
    JUST_PROCESSED_KEY,
    LAST_Q_KEY,
    QUESTION_KEY,
    RESULT_KEY,
    UPLOADER_VERSION_KEY,
    clear_document,
    cooldown_remaining,
    ensure_processed,
    init_state,
    reset_app,
    run_question,
    use_suggestion,
)

# Backwards compatibility private aliases
_run_question = run_question
_ensure_processed = ensure_processed
_reset_app = reset_app
_use_suggestion = use_suggestion
_cooldown_remaining = cooldown_remaining
_clear_document = clear_document
_init_state = init_state
from frontend.utils.formatters import (
    _blockquote,
    _escape_md,
    blockquote,
    confidence_label,
    escape_md,
    format_bytes,
    verdict_label,
)
from frontend.utils.view_models import AnswerViewModel

# Backwards compatibility aliases for existing tests
__all__ = [
    "DOC_KEY",
    "DOC_FP_KEY",
    "DOC_ERROR_KEY",
    "RESULT_KEY",
    "LAST_Q_KEY",
    "ERROR_KEY",
    "COOLDOWN_KEY",
    "AUTO_ASK_KEY",
    "QUESTION_KEY",
    "UPLOADER_VERSION_KEY",
    "JUST_PROCESSED_KEY",
    "PAGE_TITLE",
    "TAGLINE",
    "format_bytes",
    "verdict_label",
    "confidence_label",
    "_escape_md",
    "_blockquote",
]


# Hero and Upload aliases
_render_hero = render_hero
_render_landing = render_value_props
_render_uploader = render_uploader
_render_document_error = render_upload_error


def _render_document_summary(policy: ProcessedPolicy) -> None:
    with st.container(border=True):
        title_col, status_col = st.columns([5, 1])
        with title_col:
            st.markdown(f"### {escape_md(policy.filename)}")
            st.caption("Policy loaded · extracted and chunked in memory")
        with status_col:
            st.markdown(
                '<span class="cs-chip cs-chip-ok">Ready</span>',
                unsafe_allow_html=True,
            )

        columns = st.columns(4)
        columns[0].metric("Pages", f"{policy.page_count:,}")
        columns[1].metric(
            "Extracted text",
            f"{policy.extracted_characters:,}",
            help="Characters of selectable text. Documents above the limit are rejected, never truncated.",
        )
        columns[2].metric("Searchable chunks", f"{len(policy.chunks):,}")
        columns[3].metric("File size", format_bytes(policy.size_bytes))

        if policy.quality.text_poor_pages:
            st.caption(
                "Low-text pages: "
                + ", ".join(map(str, policy.quality.text_poor_pages))
                + ". Review these pages if they are relevant to your question."
            )
        if policy.quality.table_review_pages:
            st.caption(
                "Possible table / multi-column pages for manual review: "
                + ", ".join(map(str, policy.quality.table_review_pages))
                + ". Text extraction does not guarantee table row/column order."
            )
        if policy.quality.warnings:
            with st.expander("Extraction notes"):
                for warning in policy.quality.warnings:
                    st.markdown(f"- {warning}")


def _render_question_area(policy: ProcessedPolicy) -> None:
    st.markdown("## Ask about this policy")
    st.caption("Suggested questions")
    suggestion_columns = st.columns(2)
    for index, suggestion in enumerate(SUGGESTED_QUESTIONS):
        suggestion_columns[index % 2].button(
            suggestion,
            key=f"suggestion_{index}",
            on_click=use_suggestion,
            args=(suggestion,),
            use_container_width=True,
        )

    question = st.text_area(
        "Your question",
        key=QUESTION_KEY,
        height=96,
        max_chars=MAX_QUESTION_CHARS,
        placeholder="e.g. Is a pre-existing disease covered in month 20?",
    )

    cooldown = cooldown_remaining()
    if cooldown > 0:
        st.info(
            f"The AI provider rate limit was reached. Try again in about "
            f"{cooldown} seconds; CoverScope will not retry automatically."
        )

    ask_clicked = st.button(
        "Ask CoverScope",
        type="primary",
        key="ask_button",
    )
    auto_ask = bool(st.session_state.pop(AUTO_ASK_KEY, False))

    if ask_clicked or auto_ask:
        if cooldown > 0:
            st.warning("Please wait for the rate-limit cooldown before asking again.")
        elif not question or not question.strip():
            st.warning("Enter a question first.")
        else:
            run_question(policy, question.strip())


def _render_answer(result: AnswerResult, question: str | None = None) -> None:
    vm = AnswerViewModel.from_result(result)

    if vm.manual_review_required:
        st.warning(MANUAL_REVIEW_MESSAGE, title="Manual review required", icon="⚠️")

    badge = (
        f'<span class="cs-badge {vm.verdict.badge_class}">'
        f"{vm.verdict.display_label}</span>"
    )
    chip = (
        '<span class="cs-chip cs-chip-warn">Manual review</span>'
        if vm.manual_review_required
        else '<span class="cs-chip cs-chip-ok">Citations verified</span>'
    )
    st.markdown(
        f'<div class="cs-answer-head">{badge}{chip}</div>',
        unsafe_allow_html=True,
    )
    st.caption(vm.verdict.summary_text)

    if question:
        st.caption(f"Question: {question}")
    st.markdown("#### Answer")
    st.markdown(vm.answer_text)

    if vm.verdict.is_not_stated:
        st.info(NOT_STATED_MESSAGE)

    metric_columns = st.columns(3)
    metric_columns[0].metric(
        "Model-reported confidence",
        vm.confidence_display,
        help="Reported by the model. This is not a guarantee that the verdict is correct.",
    )
    metric_columns[1].metric(
        "Citation check",
        "Verified" if vm.citations_valid else "Failed",
        help="Every quotation is matched against the retrieved policy text.",
    )
    metric_columns[2].metric(
        "Cited pages",
        vm.cited_pages_display,
    )
    st.caption(
        "Confidence is reported by the model and is not a guarantee of correctness. "
        "A valid quotation confirms the wording, not the coverage decision."
    )

    if vm.citations:
        st.markdown("#### Cited evidence")
        for citation in vm.citations:
            with st.container(border=True):
                st.markdown(
                    f'<span class="cs-cite-meta">Page {citation.page_number} · '
                    f"{citation.chunk_id}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(blockquote(citation.quote))
    else:
        st.caption("No verified quotations were returned for this answer.")

    if vm.warnings:
        st.markdown("#### Verification warnings")
        for warning in vm.warnings:
            st.markdown(f"- {warning}")
    if vm.caveats:
        st.markdown("#### Policy caveats")
        for caveat in vm.caveats:
            st.markdown(f"- {caveat}")

    if vm.unverified_answer:
        with st.expander("Unverified model answer — not a coverage decision"):
            st.write(vm.unverified_answer)


def _render_answer_zone() -> None:
    error = st.session_state.get(ERROR_KEY)
    result = st.session_state.get(RESULT_KEY)

    if error:
        st.error(error, title="Could not answer")
    if result:
        if error:
            st.markdown("#### Previous answer")
            st.caption(
                "This is the last verified result and may not answer your latest question."
            )
        _render_answer(result, st.session_state.get(LAST_Q_KEY))
    elif not error:
        st.caption("Ask a question to see a verdict with cited evidence.")


def main() -> None:
    setup_page()
    render_sidebar()
    render_brand_header()
    policy = st.session_state.get(DOC_KEY)
    render_hero(compact=policy is not None)

    uploaded = render_uploader()

    if uploaded is None:
        if st.session_state.get(DOC_FP_KEY):
            clear_document()
    else:
        ensure_processed(uploaded)

    if st.session_state.pop(JUST_PROCESSED_KEY, False):
        st.success("Policy processed. You can ask a question now.")

    policy = st.session_state.get(DOC_KEY)
    if policy is None:
        render_upload_error()
        if not st.session_state.get(DOC_ERROR_KEY):
            render_value_props()
    else:
        _render_document_summary(policy)
        st.write("")
        _render_question_area(policy)
        st.divider()
        _render_answer_zone()

    render_footer()


if __name__ == "__main__":
    main()
