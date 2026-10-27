"""Tests for multi-policy session registry and active document switching."""
from __future__ import annotations

from unittest.mock import patch
import pymupdf
import pytest

from backend.qa.answer import AnswerResult, VerifiedCitation
from backend.qa.workflow import prepare_policy
import frontend.state as state

TEXT_POLICY_A = "Policy A: Maternity coverage is excluded for the first 24 months."
TEXT_POLICY_B = "Policy B: Critical illness benefit pays a lump sum of Rs 10,00,000."


def make_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


class MockUploadedFile:
    def __init__(self, name: str, data: bytes) -> None:
        self.name = name
        self._data = data

    def getvalue(self) -> bytes:
        return self._data


@pytest.fixture(autouse=True)
def clean_streamlit_session():
    """Clear mock Streamlit session state between tests."""
    import streamlit as st
    st.session_state.clear()
    state.init_state()
    yield
    st.session_state.clear()


def test_registry_registration_and_active_policy():
    pdf_a = make_pdf(TEXT_POLICY_A)
    pdf_b = make_pdf(TEXT_POLICY_B)

    pol_a = prepare_policy(pdf_a, "Policy_A.pdf")
    pol_b = prepare_policy(pdf_b, "Policy_B.pdf")

    fp_a = state.register_policy(pol_a, set_active=True)
    assert state.get_active_fingerprint() == fp_a
    assert state.get_active_policy() == pol_a

    fp_b = state.register_policy(pol_b, set_active=True)
    assert state.get_active_fingerprint() == fp_b
    assert state.get_active_policy() == pol_b

    reg = state.get_registry()
    assert len(reg) == 2
    assert fp_a in reg
    assert fp_b in reg


def test_registry_switching_preserves_question_and_answer_history():
    pdf_a = make_pdf(TEXT_POLICY_A)
    pdf_b = make_pdf(TEXT_POLICY_B)
    pol_a = prepare_policy(pdf_a, "Policy_A.pdf")
    pol_b = prepare_policy(pdf_b, "Policy_B.pdf")

    fp_a = state.register_policy(pol_a, set_active=True)
    # Simulate answer on Policy A
    res_a = AnswerResult(
        verdict="excluded",
        answer="Maternity is excluded for 24 months.",
        citations=(VerifiedCitation("P1-C1", 1, "Maternity coverage is excluded", True),),
        confidence="high",
        caveats=(),
        citations_valid=True,
        manual_review_required=False,
        warnings=(),
    )
    import streamlit as st
    st.session_state[state.RESULT_KEY] = res_a
    st.session_state[state.LAST_Q_KEY] = "Is maternity covered?"

    # Register and switch to Policy B
    fp_b = state.register_policy(pol_b, set_active=True)
    assert state.get_active_fingerprint() == fp_b
    assert st.session_state.get(state.RESULT_KEY) is None

    # Simulate answer on Policy B
    res_b = AnswerResult(
        verdict="covered",
        answer="Critical illness lump sum is payable.",
        citations=(VerifiedCitation("P1-C1", 1, "Critical illness benefit pays", True),),
        confidence="high",
        caveats=(),
        citations_valid=True,
        manual_review_required=False,
        warnings=(),
    )
    st.session_state[state.RESULT_KEY] = res_b
    st.session_state[state.LAST_Q_KEY] = "What is critical illness benefit?"

    # Switch back to Policy A
    switched = state.set_active_policy(fp_a)
    assert switched is True
    assert state.get_active_fingerprint() == fp_a
    assert state.get_active_policy() == pol_a
    assert st.session_state.get(state.RESULT_KEY) == res_a
    assert st.session_state.get(state.LAST_Q_KEY) == "Is maternity covered?"

    # Switch back to Policy B
    state.set_active_policy(fp_b)
    assert state.get_active_fingerprint() == fp_b
    assert st.session_state.get(state.RESULT_KEY) == res_b
    assert st.session_state.get(state.LAST_Q_KEY) == "What is critical illness benefit?"


def test_registry_duplicate_upload_reuses_processed_policy():
    data = make_pdf(TEXT_POLICY_A)
    upload_1 = MockUploadedFile("Policy_A.pdf", data)
    upload_2 = MockUploadedFile("Policy_A.pdf", data)

    with patch("frontend.state.policy_service.prepare_policy", wraps=state.policy_service.prepare_policy) as mock_prep:
        state.ensure_processed(upload_1)
        assert mock_prep.call_count == 1
        reg = state.get_registry()
        assert len(reg) == 1

        # Second upload of the exact same document
        state.ensure_processed(upload_2)
        # Should not prepare again
        assert mock_prep.call_count == 1
        assert len(state.get_registry()) == 1


def test_registry_removal_semantics():
    pol_a = prepare_policy(make_pdf(TEXT_POLICY_A), "Policy_A.pdf")
    pol_b = prepare_policy(make_pdf(TEXT_POLICY_B), "Policy_B.pdf")

    fp_a = state.register_policy(pol_a, set_active=True)
    fp_b = state.register_policy(pol_b, set_active=False)

    reg = state.get_registry()
    assert len(reg) == 2

    # Remove non-active Policy B
    assert state.remove_policy(fp_b) is True
    assert len(state.get_registry()) == 1
    assert state.get_active_fingerprint() == fp_a

    # Remove active Policy A
    assert state.remove_policy(fp_a) is True
    assert len(state.get_registry()) == 0
    assert state.get_active_policy() is None
    assert state.get_active_fingerprint() is None


def test_reset_app_clears_registry():
    pol_a = prepare_policy(make_pdf(TEXT_POLICY_A), "Policy_A.pdf")
    state.register_policy(pol_a, set_active=True)
    assert len(state.get_registry()) == 1

    state.reset_app()
    assert len(state.get_registry()) == 0
    assert state.get_active_policy() is None


def test_complete_nine_state_transitions():
    """Verify all 9 transitions specified in Review B:
    1. Upload policy A and ask a question.
    2. Upload policy B and ask a different question.
    3. Switch between A and B and verify their respective histories.
    4. Upload the same file again and verify deduplication behaves intentionally.
    5. Remove a non-active policy and verify active policy remains undisturbed.
    6. Remove the active policy and observe resulting active state.
    7. Re-upload a removed policy and confirm clean restoration.
    8. Trigger an invalid upload while a valid policy is active and check active policy is preserved in registry.
    9. Clear the entire session and verify all state is cleanly reset.
    """
    import streamlit as st

    # --- Transition 1: Upload policy A and ask question ---
    pdf_a = make_pdf(TEXT_POLICY_A)
    upload_a = MockUploadedFile("Policy_A.pdf", pdf_a)
    state.ensure_processed(upload_a)
    pol_a = state.get_active_policy()
    assert pol_a is not None
    fp_a = pol_a.fingerprint
    assert state.get_active_fingerprint() == fp_a

    res_a = AnswerResult(
        verdict="excluded",
        answer="Maternity is excluded for 24 months.",
        citations=(VerifiedCitation("P1-C1", 1, "Maternity coverage is excluded", True),),
        confidence="high",
        caveats=(),
        citations_valid=True,
        manual_review_required=False,
        warnings=(),
    )
    st.session_state[state.RESULT_KEY] = res_a
    st.session_state[state.LAST_Q_KEY] = "Is maternity covered?"

    # --- Transition 2: Upload policy B and ask different question ---
    pdf_b = make_pdf(TEXT_POLICY_B)
    upload_b = MockUploadedFile("Policy_B.pdf", pdf_b)
    state.ensure_processed(upload_b)
    pol_b = state.get_active_policy()
    assert pol_b is not None
    fp_b = pol_b.fingerprint
    assert fp_b != fp_a
    assert state.get_active_fingerprint() == fp_b
    assert st.session_state.get(state.RESULT_KEY) is None  # fresh state for B

    res_b = AnswerResult(
        verdict="covered",
        answer="Critical illness lump sum Rs 10,00,000.",
        citations=(VerifiedCitation("P1-C1", 1, "Critical illness benefit pays", True),),
        confidence="high",
        caveats=(),
        citations_valid=True,
        manual_review_required=False,
        warnings=(),
    )
    st.session_state[state.RESULT_KEY] = res_b
    st.session_state[state.LAST_Q_KEY] = "What is critical illness limit?"

    # --- Transition 3: Switch between A and B and verify histories ---
    # Switch to A
    state.set_active_policy(fp_a)
    assert state.get_active_fingerprint() == fp_a
    assert st.session_state.get(state.RESULT_KEY) == res_a
    assert st.session_state.get(state.LAST_Q_KEY) == "Is maternity covered?"

    # Switch back to B
    state.set_active_policy(fp_b)
    assert state.get_active_fingerprint() == fp_b
    assert st.session_state.get(state.RESULT_KEY) == res_b
    assert st.session_state.get(state.LAST_Q_KEY) == "What is critical illness limit?"

    # --- Transition 4: Upload same file again and verify deduplication ---
    with patch("frontend.state.policy_service.prepare_policy", wraps=state.policy_service.prepare_policy) as mock_prep:
        state.ensure_processed(upload_b)
        assert mock_prep.call_count == 0  # Deduped: no re-processing
    assert state.get_active_fingerprint() == fp_b
    assert len(state.get_registry()) == 2

    # --- Transition 5: Remove non-active policy (A) while B is active ---
    assert state.remove_policy(fp_a) is True
    assert len(state.get_registry()) == 1
    assert fp_a not in state.get_registry()
    assert state.get_active_fingerprint() == fp_b  # B remains undisturbed
    assert state.get_active_policy() == pol_b
    assert st.session_state.get(state.RESULT_KEY) == res_b

    # --- Transition 6: Remove active policy (B) and observe resulting state ---
    assert state.remove_policy(fp_b) is True
    assert len(state.get_registry()) == 0
    assert state.get_active_fingerprint() is None
    assert state.get_active_policy() is None
    assert st.session_state.get(state.RESULT_KEY) is None

    # --- Transition 7: Re-upload removed policy (A) and confirm clean restoration ---
    state.ensure_processed(upload_a)
    pol_a_restored = state.get_active_policy()
    assert pol_a_restored is not None
    assert pol_a_restored.fingerprint == fp_a
    assert state.get_active_fingerprint() == fp_a
    assert len(state.get_registry()) == 1

    # --- Transition 8: Trigger invalid upload while valid policy A is active ---
    bad_upload = MockUploadedFile("corrupt.pdf", b"NOT_A_REAL_PDF_DATA")
    state.ensure_processed(bad_upload)
    # Upload error is recorded
    assert st.session_state.get(state.DOC_ERROR_KEY) is not None
    # Policy A in registry is preserved uncorrupted
    reg = state.get_registry()
    assert fp_a in reg
    assert reg[fp_a]["policy"].fingerprint == fp_a
    # Can switch back or restore Policy A cleanly
    state.set_active_policy(fp_a)
    assert state.get_active_fingerprint() == fp_a
    assert state.get_active_policy() == pol_a_restored

    # --- Transition 9: Clear entire session and verify clean reset ---
    state.reset_app()
    assert len(state.get_registry()) == 0
    assert state.get_active_fingerprint() is None
    assert state.get_active_policy() is None
    assert st.session_state.get(state.DOC_ERROR_KEY) is None
    assert st.session_state.get(state.RESULT_KEY) is None


def test_scenario_state_isolated_across_policy_switches():
    import streamlit as st
    from backend.domain.enums import ScenarioType, ScenarioVerdict
    from backend.domain.scenario import ScenarioInput, ScenarioResult

    pdf_a = make_pdf(TEXT_POLICY_A)
    pdf_b = make_pdf(TEXT_POLICY_B)
    pol_a = prepare_policy(pdf_a, "Policy_A.pdf")
    pol_b = prepare_policy(pdf_b, "Policy_B.pdf")

    fp_a = state.register_policy(pol_a, set_active=True)
    input_a = ScenarioInput(scenario_type=ScenarioType.PRE_EXISTING_CONDITION, elapsed_months=20)
    result_a = ScenarioResult(
        scenario_id="scen_a",
        scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
        policy_fingerprint=fp_a,
        verdict=ScenarioVerdict.WAITING_PERIOD_ACTIVE,
        headline="Policy A PED Waiting Period Active",
        explanation="20 months elapsed against 36 months.",
    )
    st.session_state[state.SCENARIO_INPUT_KEY] = input_a
    st.session_state[state.SCENARIO_RESULT_KEY] = result_a

    # Register Policy B and switch to it
    fp_b = state.register_policy(pol_b, set_active=True)
    assert state.get_active_fingerprint() == fp_b
    # Fresh state for B: scenario state is None
    assert st.session_state.get(state.SCENARIO_INPUT_KEY) is None
    assert st.session_state.get(state.SCENARIO_RESULT_KEY) is None

    # Set scenario on Policy B
    input_b = ScenarioInput(scenario_type=ScenarioType.ENTRY_AGE_COPAYMENT, member_age_at_entry=65)
    result_b = ScenarioResult(
        scenario_id="scen_b",
        scenario_type=ScenarioType.ENTRY_AGE_COPAYMENT,
        policy_fingerprint=fp_b,
        verdict=ScenarioVerdict.CONDITIONAL_REVIEW,
        headline="Policy B Co-payment applies",
        explanation="Age 65 exceeds entry threshold.",
    )
    st.session_state[state.SCENARIO_INPUT_KEY] = input_b
    st.session_state[state.SCENARIO_RESULT_KEY] = result_b

    # Switch back to Policy A
    state.set_active_policy(fp_a)
    assert state.get_active_fingerprint() == fp_a
    assert st.session_state.get(state.SCENARIO_INPUT_KEY) == input_a
    assert st.session_state.get(state.SCENARIO_RESULT_KEY) == result_a
    assert st.session_state[state.SCENARIO_RESULT_KEY].policy_fingerprint == fp_a

    # Switch back to Policy B
    state.set_active_policy(fp_b)
    assert state.get_active_fingerprint() == fp_b
    assert st.session_state.get(state.SCENARIO_INPUT_KEY) == input_b
    assert st.session_state.get(state.SCENARIO_RESULT_KEY) == result_b
    assert st.session_state[state.SCENARIO_RESULT_KEY].policy_fingerprint == fp_b

    # Clear document clears scenario state
    state.clear_document()
    assert st.session_state.get(state.SCENARIO_INPUT_KEY) is None
    assert st.session_state.get(state.SCENARIO_RESULT_KEY) is None
