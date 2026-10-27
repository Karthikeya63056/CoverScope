"""Ask My Policy workspace view for CoverScope."""
from __future__ import annotations

import streamlit as st

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
from frontend.components.empty_state import render_empty_answer_state
from frontend.components.evidence_card import render_evidence_section
from frontend.components.hero import render_hero, render_value_props
from frontend.components.privacy_notice import render_privacy_notice
from frontend.components.question_composer import render_question_composer
from frontend.components.upload import render_upload_error, render_uploader
from frontend.components.verdict_card import render_verdict_card
from frontend.state import (
    DOC_ERROR_KEY,
    DOC_FP_KEY,
    DOC_KEY,
    ERROR_KEY,
    JUST_PROCESSED_KEY,
    LAST_Q_KEY,
    RESULT_KEY,
    clear_document,
    ensure_processed,
    get_active_policy,
)
from frontend.utils.view_models import AnswerViewModel


def _render_answer(result: AnswerResult, question: str | None = None) -> None:
    """Render the structured verdict and cited evidence components."""
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
    """Render error, previous answer, or empty answer state."""
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
        render_empty_answer_state()


def render_ask_view() -> None:
    """Render the primary Ask My Policy Q&A workspace."""
    policy = get_active_policy()
    render_hero(compact=policy is not None)

    uploaded = render_uploader()
    if uploaded is None:
        if st.session_state.get(DOC_FP_KEY) and policy is None:
            clear_document()
    else:
        ensure_processed(uploaded)

    if st.session_state.pop(JUST_PROCESSED_KEY, False):
        st.success("Policy processed. You can ask a question now.")

    policy = get_active_policy()
    if policy is None:
        render_upload_error()
        if not st.session_state.get(DOC_ERROR_KEY):
            render_value_props()
            render_privacy_notice(expanded=False)
    else:
        render_document_card(policy)
        st.write("")
        render_question_composer(policy)
        st.divider()
        _render_answer_zone()
