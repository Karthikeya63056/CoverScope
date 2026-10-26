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
from frontend.components.analysis_status import render_provider_error
from frontend.components.answer_summary import render_answer_summary
from frontend.components.caveats import (
    render_caveats_and_warnings,
    render_manual_review_banner,
)
from frontend.components.confidence import render_confidence_metrics
from frontend.components.document_card import render_document_card
from frontend.components.evidence_card import render_evidence_section
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
from frontend.components.question_composer import render_question_composer
from frontend.components.upload import render_upload_error, render_uploader
from frontend.components.verdict_card import render_verdict_card
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


# Component aliases
_render_hero = render_hero
_render_landing = render_value_props
_render_uploader = render_uploader
_render_document_error = render_upload_error
_render_document_summary = render_document_card
_render_question_area = render_question_composer


def _render_answer(result: AnswerResult, question: str | None = None) -> None:
    vm = AnswerViewModel.from_result(result)

    render_manual_review_banner(vm.manual_review_required, vm.citations_valid)
    render_verdict_card(
        vm.verdict,
        manual_review_required=vm.manual_review_required,
        citations_valid=vm.citations_valid,
    )
    render_answer_summary(
        vm.answer_text,
        question=question,
        is_not_stated=vm.verdict.is_not_stated,
    )
    render_confidence_metrics(
        vm.confidence_display,
        citations_valid=vm.citations_valid,
        cited_pages=vm.cited_pages_display,
    )
    render_evidence_section(vm.citations)
    render_caveats_and_warnings(
        warnings=vm.warnings,
        caveats=vm.caveats,
        unverified_answer=vm.unverified_answer,
    )


def _render_answer_zone() -> None:
    error = st.session_state.get(ERROR_KEY)
    result = st.session_state.get(RESULT_KEY)

    if error:
        render_provider_error(error)
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
        render_document_card(policy)
        st.write("")
        render_question_composer(policy)
        st.divider()
        _render_answer_zone()

    render_footer()


if __name__ == "__main__":
    main()
