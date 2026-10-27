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
from frontend.components.brand_intro import render_brand_intro, render_cinematic_intro
from frontend.components.caveats import (
    render_caveats_and_warnings,
    render_manual_review_banner,
)
from frontend.components.confidence import render_confidence_metrics
from frontend.components.document_card import render_document_card
from frontend.components.empty_state import render_empty_answer_state
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
from frontend.components.privacy_notice import render_privacy_notice
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
from frontend.layout.navigation import render_navigation
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
    VIEW_ASK,
    VIEW_EXPLORER,
    VIEW_LIBRARY,
    VIEW_SCENARIO,
    VIEW_COMPARISON,
    clear_document,
    cooldown_remaining,
    ensure_processed,
    init_state,
    reset_app,
    run_question,
    use_suggestion,
)
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
from frontend.views.ask_view import _render_answer, _render_answer_zone, render_ask_view
from frontend.views.comparison_view import render_comparison_view
from frontend.views.explorer_view import render_explorer_view
from frontend.views.library_view import render_library_view
from frontend.views.scenario_view import render_scenario_view

# Backwards compatibility private aliases
_run_question = run_question
_ensure_processed = ensure_processed
_reset_app = reset_app
_use_suggestion = use_suggestion
_cooldown_remaining = cooldown_remaining
_clear_document = clear_document
_init_state = init_state

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


def main() -> None:
    setup_page()
    render_sidebar()

    # Cinematic 3D intro overlay (plays on initial landing or explicit replay)
    force_replay = bool(st.session_state.pop("cs_replay_intro", False))
    render_cinematic_intro(force_play=force_replay)

    render_brand_header()
    active_view = render_navigation()

    # Route to selected workspace
    if active_view == VIEW_EXPLORER:
        render_explorer_view()
    elif active_view == VIEW_SCENARIO:
        render_scenario_view()
    elif active_view == VIEW_COMPARISON:
        render_comparison_view()
    elif active_view == VIEW_LIBRARY:
        render_library_view()
    else:
        render_ask_view()

    render_footer()


if __name__ == "__main__":
    main()
