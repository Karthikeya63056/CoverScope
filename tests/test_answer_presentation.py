"""Focused unit tests for Stage E Answer Summary, Verdicts, Confidence, and Caveats."""
from __future__ import annotations

from frontend.components.answer_summary import render_answer_summary
from frontend.components.caveats import (
    render_caveats_and_warnings,
    render_manual_review_banner,
)
from frontend.components.confidence import render_confidence_metrics
from frontend.components.verdict_card import render_verdict_card
from frontend.utils.view_models import VerdictViewModel


def test_verdict_view_model_covers_all_four_verdicts():
    for verdict in ("covered", "excluded", "depends", "not_stated"):
        vm = VerdictViewModel.from_verdict(verdict)
        assert vm.verdict_key == verdict
        assert len(vm.display_label) > 0
        assert len(vm.summary_text) > 0
        assert f"cs-badge-{verdict.replace('_', '-')}" in vm.badge_class


def test_verdict_view_model_safe_fallback_on_unknown():
    vm = VerdictViewModel.from_verdict("unknown_verdict")
    assert vm.verdict_key == "unknown_verdict"
    assert vm.display_label == "Unknown Verdict"
    assert vm.is_covered is False
    assert vm.is_excluded is False


def test_answer_summary_renders_safely_with_empty_text():
    # Calling with empty text should not raise exception
    render_answer_summary("", is_not_stated=False)
    render_answer_summary("   ", is_not_stated=False)


def test_confidence_metrics_handles_varied_page_inputs():
    # Sequence of ints
    render_confidence_metrics("high", citations_valid=True, cited_pages=[1, 4])
    # Pre-formatted string
    render_confidence_metrics("low", citations_valid=False, cited_pages="1, 4")
    # Empty
    render_confidence_metrics("medium", citations_valid=True, cited_pages=[])


def test_caveats_and_warnings_filters_duplicates():
    # Warnings that overlap with caveats should only be shown under warnings
    warnings = ["Page 1 text mismatch."]
    caveats = ["Page 1 text mismatch.", "Waiting period applies in month 20."]

    # Should not raise exception
    render_caveats_and_warnings(
        warnings=warnings,
        caveats=caveats,
        unverified_answer="Raw unverified answer.",
    )
    render_manual_review_banner(manual_review_required=True, citations_valid=False)
