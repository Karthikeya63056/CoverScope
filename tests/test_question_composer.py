"""Focused unit tests for Stage D question composer, suggestions, and analysis status."""
from __future__ import annotations

from unittest.mock import MagicMock

from frontend.components.analysis_status import render_cooldown_notice, render_provider_error
from frontend.components.suggested_questions import render_suggested_questions
from frontend.messages import SUGGESTED_QUESTIONS


def test_suggested_questions_list_has_valid_items():
    assert len(SUGGESTED_QUESTIONS) >= 4
    for q in SUGGESTED_QUESTIONS:
        assert isinstance(q, str)
        assert len(q.strip()) > 0
        assert q.endswith("?")


def test_cooldown_notice_no_op_when_zero_or_negative():
    # Should not raise exception
    render_cooldown_notice(0)
    render_cooldown_notice(-5)


def test_provider_error_no_op_when_none_or_empty():
    # Should not raise exception
    render_provider_error(None)
    render_provider_error("")
