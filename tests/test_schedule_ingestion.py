"""Unit and integration tests for CoverScope Policy Schedule Ingestion, Association, and Personalization."""
from __future__ import annotations

from pathlib import Path
import pymupdf
import pytest

from backend.domain.comparison import ComparisonAssumptions, PolicyComparisonEngine
from backend.domain.enums import (
    ComparisonDimensionKey,
    ComparisonStatus,
    DocumentAssociationStatus,
    DurationUnit,
    FactCategory,
    FactValidationStatus,
    ScenarioType,
    ScenarioVerdict,
    ScheduleFieldStatus,
)
from backend.domain.models import DurationValue, EvidenceReference, PolicyFact
from backend.domain.scenario import ScenarioEvaluator, ScenarioInput
from backend.domain.schedule import (
    ExtractedScheduleField,
    InsuredMember,
    PolicySchedule,
    PolicyScheduleAssociator,
    PolicyScheduleExtractor,
    mask_policy_number,
)
from backend.qa.workflow import prepare_policy
from backend.services.policy_service import PolicyService
from frontend.state import (
    get_policy_schedule,
    init_state,
    set_policy_schedule,
)


def _create_mock_policy(doc_name: str, text: str):
    doc = pymupdf.open()
    p = doc.new_page()
    padded_text = text if len(text) >= 60 else text + "\n" + ("Standard policy text line padding. " * 3)
    p.insert_textbox(pymupdf.Rect(50, 50, 500, 300), padded_text)
    data = doc.tobytes()
    doc.close()
    return prepare_policy(data, doc_name)


def test_mask_policy_number():
    """Verify sensitive policy numbers are masked at the boundary with prefix and suffix preserved."""
    assert mask_policy_number("POL1234567890") == "PO-******-7890"
    assert mask_policy_number("2825 2045 1234 5678") == "28-******-5678"
    assert mask_policy_number("P/161114/01/2024/005432") == "P/-******-5432"
    # Short policy numbers should be replaced safely
    assert mask_policy_number("12345") == "****"


def test_policy_schedule_extractor():
    """Verify deterministic extraction of schedule fields from synthetic text."""
    sample_text = (
        "HDFC ERGO General Insurance Company Limited\n"
        "SCHEDULE OF INSURANCE\n"
        "Policy No: 2825-9988-7766\n"
        "Product: Optima Secure\n"
        "Policy Period: From 15/05/2023 to 14/05/2024\n"
        "Sum Insured: Rs. 1,000,000\n"
        "Voluntary Deductible: Rs. 25,000\n"
        "INSURED PERSONS:\n"
        "1. Rohan Verma | Age: 34 | Relation: Self\n"
        "2. Priya Verma | Age: 32 | Relation: Spouse\n"
        "ENDORSEMENTS & RIDERS:\n"
        "- Reduction in PED Waiting Period\n"
        "- Hospital Daily Cash\n"
    )
    policy_doc = _create_mock_policy("sample_schedule.pdf", sample_text)
    extractor = PolicyScheduleExtractor()
    schedule = extractor.extract(policy_doc)

    assert schedule.insurer_name == "HDFC ERGO General Insurance"
    assert schedule.product_name == "Optima Secure"
    assert schedule.policy_number_masked is not None
    assert schedule.policy_number_masked.startswith("28-")
    assert schedule.policy_number_masked.endswith("-7766")
    assert "9988" not in schedule.policy_number_masked
    assert schedule.inception_date == "2023-05-15"
    assert schedule.expiry_date == "2024-05-14"
    assert schedule.sum_insured == 1000000.0
    assert schedule.voluntary_deductible == 25000.0
    assert len(schedule.members) == 2
    assert schedule.members[0].name == "Rohan Verma"
    assert schedule.members[0].age == 34
    assert schedule.members[1].name == "Priya Verma"
    assert schedule.members[1].age == 32
    assert len(schedule.optional_riders) == 2


def test_policy_schedule_associator_compatible_and_conflict():
    """Verify schedule associator reliably confirms matches and detects cross-insurer conflicts."""
    optima_wording = _create_mock_policy(
        "Optima_Secure_Policy_Wording.pdf",
        "HDFC ERGO General Insurance Company Limited. Welcome to Optima Secure health policy.",
    )
    star_wording = _create_mock_policy(
        "Star_Comprehensive_Wording.pdf",
        "Star Health and Allied Insurance Company Limited. Star Comprehensive Insurance Policy terms.",
    )

    extractor = PolicyScheduleExtractor()
    hdfc_schedule_doc = _create_mock_policy(
        "hdfc_schedule.pdf",
        "HDFC ERGO General Insurance Company Limited\nPolicy No: 123456789\nProduct: Optima Secure\nSum Insured: Rs. 500,000",
    )
    hdfc_schedule = extractor.extract(hdfc_schedule_doc)

    associator = PolicyScheduleAssociator()

    # Compatible match
    status_match, reasons_match = associator.evaluate_association(hdfc_schedule, optima_wording)
    assert status_match == DocumentAssociationStatus.SUGGESTED_MATCH
    assert len(reasons_match) > 0

    # Incompatible match (HDFC schedule against Star Health wording)
    status_conflict, conflicts = associator.evaluate_association(hdfc_schedule, star_wording)
    assert status_conflict == DocumentAssociationStatus.CONFLICT_DETECTED
    assert any("Insurer mismatch" in c for c in conflicts)


def test_policy_service_prepare_and_associate_schedule():
    """Verify PolicyService can parse and associate a policy schedule."""
    service = PolicyService()

    wording_doc = _create_mock_policy(
        "Star_Comprehensive.pdf",
        "Star Health and Allied Insurance Company Limited. Star Comprehensive Insurance Policy.",
    )
    sch_text = (
        "Star Health and Allied Insurance Company Limited\n"
        "Policy Certificate No: P/112233/44/556677\n"
        "Product: Star Comprehensive Insurance Policy\n"
        "Period of Insurance: From 01-Jan-2024 to 31-Dec-2024\n"
        "Sum Insured: Rs. 500,000\n"
        "Name: Anita Sen | Age: 42 | Relation: Self"
    )
    # Prepare schedule using a real PDF
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_textbox(pymupdf.Rect(50, 50, 500, 300), sch_text)
    data = doc.tobytes()
    doc.close()

    schedule = service.prepare_schedule(data, "schedule_anita.pdf")
    assert schedule.insurer_name == "Star Health & Allied Insurance"
    assert schedule.sum_insured == 500000.0
    assert len(schedule.members) == 1

    # Associate schedule
    associated = service.associate_schedule(schedule, wording_doc)
    assert associated.association_status == DocumentAssociationStatus.SUGGESTED_MATCH
    assert associated.associated_policy_fingerprint == wording_doc.fingerprint


def test_frontend_state_schedule_management():
    """Verify schedule storage, retrieval, and clear actions in frontend session state."""
    import frontend.state as state_mod
    import streamlit as st
    st.session_state.clear()
    state_mod.init_state()

    pol_1 = _create_mock_policy("p1.pdf", "Sample policy wording 1")
    pol_2 = _create_mock_policy("p2.pdf", "Sample policy wording 2")

    fp1 = state_mod.register_policy(pol_1)
    fp2 = state_mod.register_policy(pol_2)

    assert state_mod.get_policy_schedule(fp1) is None
    assert state_mod.get_policy_schedule(fp2) is None

    mock_sch = PolicySchedule(
        schedule_id="sch_1",
        filename="p1_sch.pdf",
        document_fingerprint="sch_fp_1",
        sum_insured=500000.0,
    )
    state_mod.set_policy_schedule(fp1, mock_sch)
    assert state_mod.get_policy_schedule(fp1) == mock_sch
    assert state_mod.get_policy_schedule(fp2) is None  # isolated

    # Clear schedule
    state_mod.set_policy_schedule(fp1, None)
    assert state_mod.get_policy_schedule(fp1) is None
    st.session_state.clear()


def test_scenario_personalization_ped_rider_endorsement():
    """Verify ScenarioEvaluator resolves PED waiting period when schedule endorsement is verified."""
    text = (
        "Pre-Existing Disease Waiting Period: 36 months\n"
        "Upon purchase of this optional cover, the PED Waiting Period reduces from 36 months to 12 months."
    )
    pol = _create_mock_policy("ped_rider_test.pdf", text)
    evaluator = ScenarioEvaluator()

    # Case 1: User indicates buy-back rider, but without schedule endorsement -> CONDITIONAL_REVIEW
    inp_hypothetical = ScenarioInput(
        scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
        elapsed_months=14,
        has_buyback_rider=True,
        has_schedule_endorsement=False,
    )
    res1 = evaluator.evaluate(pol, inp_hypothetical)
    assert res1.verdict == ScenarioVerdict.CONDITIONAL_REVIEW
    assert "Policy Schedule" in res1.explanation or any("schedule" in c.lower() for c in res1.unresolved_conditions)

    # Case 2: Schedule endorsement confirmed -> WAITING_PERIOD_SATISFIED
    inp_grounded = ScenarioInput(
        scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
        elapsed_months=14,
        has_buyback_rider=True,
        has_schedule_endorsement=True,
    )
    res2 = evaluator.evaluate(pol, inp_grounded)
    assert res2.verdict == ScenarioVerdict.WAITING_PERIOD_SATISFIED


def test_comparison_personalization_with_schedules():
    """Verify PolicyComparisonEngine compares verified schedule sum insured and lists active riders."""
    engine = PolicyComparisonEngine()

    policy_a = _create_mock_policy("PolicyA.pdf", "General terms for Policy A.")
    policy_b = _create_mock_policy("PolicyB.pdf", "General terms for Policy B.")

    sch_a = PolicySchedule(
        schedule_id="sch_a",
        filename="sch_a.pdf",
        document_fingerprint="sch_fp_a",
        sum_insured=1000000.0,
        optional_riders=("Hospital Daily Cash",),
    )
    sch_b = PolicySchedule(
        schedule_id="sch_b",
        filename="sch_b.pdf",
        document_fingerprint="sch_fp_b",
        sum_insured=500000.0,
        optional_riders=(),
    )

    report = engine.compare(
        policy_a=policy_a,
        facts_a=[],
        policy_b=policy_b,
        facts_b=[],
        assumptions=ComparisonAssumptions(),
        schedule_a=sch_a,
        schedule_b=sch_b,
    )

    # Check SUM_INSURED dimension
    si_dim = next((d for d in report.dimensions if d.dimension_key == ComparisonDimensionKey.SUM_INSURED), None)
    assert si_dim is not None
    assert si_dim.status == ComparisonStatus.COMPARABLE
    assert "1,000,000" in si_dim.summary_difference
    assert "500,000" in si_dim.summary_difference

    # Check riders
    assert "Hospital Daily Cash" in si_dim.policy_a_value.display_value
