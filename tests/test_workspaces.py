"""Integration tests for workspace routing, Policy Explorer, and Document Library."""
from __future__ import annotations

from pathlib import Path
import pymupdf
import pytest
from streamlit.testing.v1 import AppTest

from backend.qa.workflow import prepare_policy
from frontend.app import DOC_KEY
from frontend.state import (
    ACTIVE_VIEW_KEY,
    COMPARISON_POLICY_A_KEY,
    COMPARISON_POLICY_B_KEY,
    REGISTRY_KEY,
    VIEW_ASK,
    VIEW_COMPARISON,
    VIEW_EXPLORER,
    VIEW_LIBRARY,
    VIEW_SCENARIO,
)

APP_PATH = Path(__file__).resolve().parents[1] / "frontend" / "app.py"

POLICY_TEXT_1 = (
    "SECTION 1: COVERAGE PROVISIONS\n"
    "Pre-existing diseases (PED) are excluded for 36 months of continuous coverage.\n"
    "Day care treatments are covered up to the sum insured."
)

POLICY_TEXT_2 = (
    "SECTION 2: ROOM RENT LIMITATIONS\n"
    "Normal room rent is covered at actuals for single private AC room."
)


def make_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def make_test_pdf() -> bytes:
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), POLICY_TEXT_1)
    p2 = doc.new_page()
    p2.insert_text((72, 72), POLICY_TEXT_2)
    data = doc.tobytes()
    doc.close()
    return data


def new_app() -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=30)


def test_workspace_navigation_switching():
    at = new_app()
    at.run()
    assert not list(at.exception)

    # Initial view is Ask My Policy
    assert any("Know what your policy actually covers" in m.value for m in at.markdown)

    # Switch to Policy Explorer
    at.segmented_control(key="cs_nav_choice").set_value("Policy Explorer").run()
    assert not list(at.exception)
    assert any("Policy Explorer" in m.value for m in at.markdown)
    assert any("No active policy selected" in m.value for m in at.markdown)

    # Switch to Document Library
    at.segmented_control(key="cs_nav_choice").set_value("Document Library").run()
    assert not list(at.exception)
    assert any("Document Library" in m.value for m in at.markdown)
    assert any("No documents in your session library" in m.value for m in at.markdown)


def test_policy_explorer_with_active_policy():
    pdf_bytes = make_test_pdf()
    policy = prepare_policy(pdf_bytes, "Sample-Coverage.pdf")

    at = new_app()
    at.session_state[DOC_KEY] = policy
    at.session_state[ACTIVE_VIEW_KEY] = VIEW_EXPLORER
    at.run()

    assert not list(at.exception)
    # Check that explorer view renders document metadata
    rendered = " ".join(m.value for m in at.markdown)
    assert "Sample-Coverage.pdf" in rendered
    assert "Policy Explorer" in rendered
    assert "Search Extracted Text" in rendered
    assert "Page Browser" in rendered
    assert len(at.selectbox) >= 1  # Page selector


def test_policy_explorer_search_filtering():
    pdf_bytes = make_test_pdf()
    policy = prepare_policy(pdf_bytes, "Sample-Coverage.pdf")

    at = new_app()
    at.session_state[DOC_KEY] = policy
    at.session_state[ACTIVE_VIEW_KEY] = VIEW_EXPLORER
    at.run()

    # Enter a search term
    at.text_input(key="explorer_search_query").set_value("pre-existing").run()
    assert not list(at.exception)
    assert any("Found" in s.value for s in at.success)
    assert any("Page(s) 1" in s.value for s in at.success)


def test_document_library_populated_and_actions():
    pdf_bytes = make_test_pdf()
    policy = prepare_policy(pdf_bytes, "Active-Health.pdf")

    at = new_app()
    at.session_state[DOC_KEY] = policy
    at.session_state[ACTIVE_VIEW_KEY] = VIEW_LIBRARY
    at.run()

    assert not list(at.exception)
    rendered = " ".join(m.value for m in at.markdown)
    assert "Active-Health.pdf" in rendered
    assert "Active Document" in rendered
    assert any(b.label == "Explore Clauses" for b in at.button)
    assert any(b.label == "Ask Questions" for b in at.button)
    assert any(b.label == "Remove" for b in at.button)

    # Click Explore Clauses
    explore_btn = next(b for b in at.button if b.label == "Explore Clauses")
    explore_btn.click().run()
    assert not list(at.exception)
    assert at.session_state[ACTIVE_VIEW_KEY] == VIEW_EXPLORER


def test_scenario_analyzer_workspace_navigation_and_evaluation():
    pdf_bytes = make_test_pdf()
    policy = prepare_policy(pdf_bytes, "Scenario-Test.pdf")

    at = new_app()
    at.session_state[DOC_KEY] = policy
    at.session_state[ACTIVE_VIEW_KEY] = VIEW_SCENARIO
    at.run()

    assert not list(at.exception)
    rendered = " ".join(m.value for m in at.markdown)
    assert "Scenario Analyzer" in rendered
    assert "Scenario Parameters" in rendered

    # Click the evaluate button
    ped_btn = next((b for b in at.button if "Analyze" in b.label), None)
    assert ped_btn is not None
    ped_btn.click().run()
    assert not list(at.exception)

    rendered_after = " ".join(m.value for m in at.markdown)
    assert "DETERMINISTIC EVALUATION VERDICT" in rendered_after
    assert "Waiting Period" in rendered_after


def test_scenario_analyzer_stale_verdict_suppressed_on_type_change():
    pdf_bytes = make_test_pdf()
    policy = prepare_policy(pdf_bytes, "Scenario-Test.pdf")

    at = new_app()
    at.session_state[DOC_KEY] = policy
    at.session_state[ACTIVE_VIEW_KEY] = VIEW_SCENARIO
    at.run()

    # Click Analyze for PED
    ped_btn = next((b for b in at.button if "Analyze" in b.label), None)
    assert ped_btn is not None
    ped_btn.click().run()
    assert "DETERMINISTIC EVALUATION VERDICT" in " ".join(m.value for m in at.markdown)

    # Change scenario type selector to Co-Payment
    type_selector = next((s for s in at.selectbox if s.key == "_scenario_type_selector"), None)
    assert type_selector is not None
    type_selector.select("Entry-Age Co-Payment & Claim Share").run()
    assert not list(at.exception)

    # The previous PED verdict must NOT be rendered on the co-payment screen before analyzing
    rendered_after_switch = " ".join(m.value for m in at.markdown)
    assert "DETERMINISTIC EVALUATION VERDICT" not in rendered_after_switch


def test_policy_comparison_workspace_navigation_and_rendering():
    pdf_bytes_1 = make_test_pdf()
    pol_1 = prepare_policy(pdf_bytes_1, "Policy-One.pdf")

    pdf_bytes_2 = make_pdf(
        "Pre-existing diseases are excluded for 24 months of continuous coverage.\n"
        "Expenses related to illness within 30 days shall be excluded."
    )
    pol_2 = prepare_policy(pdf_bytes_2, "Policy-Two.pdf")

    # 1. Test empty comparison workspace
    at = new_app()
    at.session_state[ACTIVE_VIEW_KEY] = VIEW_COMPARISON
    at.run()
    assert not list(at.exception)
    assert any("No policies loaded for comparison" in m.value for m in at.markdown)

    # 2. Test populated comparison workspace with two registered policies
    at = new_app()
    at.session_state[REGISTRY_KEY] = {
        pol_1.fingerprint: {"policy": pol_1, "history": []},
        pol_2.fingerprint: {"policy": pol_2, "history": []},
    }
    at.session_state[COMPARISON_POLICY_A_KEY] = pol_1.fingerprint
    at.session_state[COMPARISON_POLICY_B_KEY] = pol_2.fingerprint
    at.session_state[ACTIVE_VIEW_KEY] = VIEW_COMPARISON
    at.run()

    assert not list(at.exception)
    rendered = " ".join(m.value for m in at.markdown)
    assert "Policy Comparison & Protection Gaps" in rendered
    assert "Side-by-Side Dimension Comparison" in rendered
    assert "Pre-Existing Disease (PED) Waiting Period" in rendered
    assert "Conservative Protection Gaps & Important Limitations" in rendered
    assert "Policy-One.pdf" in rendered
    assert "Policy-Two.pdf" in rendered
