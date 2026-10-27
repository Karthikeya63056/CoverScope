"""Tests for CoverScope Phase 3.1: Coverage Verification, Association Robustness, and Decision Integrity."""
from __future__ import annotations

import pymupdf
import pytest

from backend.domain.enums import (
    DecisionIntegrityState,
    DocumentAssociationStatus,
    DurationUnit,
    FactCategory,
    FactValidationStatus,
    ScenarioType,
    ScenarioVerdict,
    ScheduleFieldStatus,
)
from backend.domain.models import DurationValue, EvidenceReference, PercentageValue, PolicyFact
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


def _create_mock_policy(doc_name: str, text: str):
    doc = pymupdf.open()
    p = doc.new_page(width=595, height=842)  # A4
    padded_text = text if len(text) >= 60 else text + "\n" + ("Standard policy text line padding. " * 3)
    p.insert_textbox(pymupdf.Rect(40, 40, 550, 800), padded_text)
    data = doc.tobytes()
    doc.close()
    return prepare_policy(data, doc_name)


# =============================================================================
# 1. Document Association Hardening & Conflict Prevention
# =============================================================================

def test_association_same_insurer_different_product():
    """Verify that a schedule for a different product by the same insurer triggers CONFLICT_DETECTED."""
    wording = _create_mock_policy(
        "Optima_Secure.pdf",
        "HDFC ERGO General Insurance Company Limited. Welcome to Optima Secure health insurance terms.",
    )
    schedule = PolicySchedule(
        schedule_id="sch_diff_prod",
        filename="my_health_suraksha_schedule.pdf",
        document_fingerprint="fp_diff_prod",
        insurer_name="HDFC ERGO General Insurance",
        product_name="My:Health Suraksha",
    )
    associator = PolicyScheduleAssociator()
    status, reasons = associator.evaluate_association(schedule, wording)

    assert status == DocumentAssociationStatus.CONFLICT_DETECTED
    assert any("Product mismatch" in r or "Product conflict" in r for r in reasons)


def test_association_same_product_conflicting_variants():
    """Verify that conflicting plan variants trigger CONFLICT_DETECTED."""
    wording = _create_mock_policy(
        "Optima_Secure_Tiers.pdf",
        "HDFC ERGO General Insurance Company Limited. Optima Secure plan. This document applies strictly and only to Silver and Gold plans.",
    )
    schedule = PolicySchedule(
        schedule_id="sch_variant_conflict",
        filename="optima_titanium_schedule.pdf",
        document_fingerprint="fp_variant_conflict",
        insurer_name="HDFC ERGO General Insurance",
        product_name="Optima Secure",
        product_variant="Titanium",
    )
    associator = PolicyScheduleAssociator()
    status, reasons = associator.evaluate_association(schedule, wording)

    assert status == DocumentAssociationStatus.CONFLICT_DETECTED
    assert any("variant mismatch" in r.lower() for r in reasons)


def test_association_unclear_product_identity_needs_review():
    """Verify that a schedule lacking product identity returns NEEDS_REVIEW."""
    wording = _create_mock_policy(
        "Star_Comprehensive.pdf",
        "Star Health and Allied Insurance Company Limited. Star Comprehensive Insurance Policy.",
    )
    schedule = PolicySchedule(
        schedule_id="sch_unclear",
        filename="unclear_schedule.pdf",
        document_fingerprint="fp_unclear",
        insurer_name="Star Health & Allied Insurance",
        product_name=None,  # missing product
    )
    associator = PolicyScheduleAssociator()
    status, reasons = associator.evaluate_association(schedule, wording)

    assert status == DocumentAssociationStatus.NEEDS_REVIEW
    assert any("product name not identified" in r.lower() for r in reasons)


def test_association_missing_insurer_needs_review():
    """Verify that a schedule lacking insurer identity returns NEEDS_REVIEW."""
    wording = _create_mock_policy(
        "ReAssure.pdf",
        "Niva Bupa Health Insurance Company Limited. ReAssure 2.0 policy wording.",
    )
    schedule = PolicySchedule(
        schedule_id="sch_no_ins",
        filename="no_insurer_schedule.pdf",
        document_fingerprint="fp_no_ins",
        insurer_name=None,
        product_name="ReAssure 2.0",
    )
    associator = PolicyScheduleAssociator()
    status, reasons = associator.evaluate_association(schedule, wording)

    assert status == DocumentAssociationStatus.NEEDS_REVIEW
    assert any("insurer not identified" in r.lower() for r in reasons)


def test_association_endorsement_referencing_different_policy_conflict():
    """Verify that an endorsement referencing an unrelated policy number triggers CONFLICT_DETECTED."""
    wording = _create_mock_policy(
        "Optima_Secure.pdf",
        "HDFC ERGO General Insurance Company Limited. Optima Secure health insurance.",
    )
    schedule = PolicySchedule(
        schedule_id="sch_endorse_mismatch",
        filename="hdfc_schedule.pdf",
        document_fingerprint="fp_endorse_mismatch",
        insurer_name="HDFC ERGO General Insurance",
        product_name="Optima Secure",
        policy_number_masked="28-******-1234",
        endorsement_policy_refs=("998877665544",),  # different policy number
    )
    associator = PolicyScheduleAssociator()
    status, reasons = associator.evaluate_association(schedule, wording)

    assert status == DocumentAssociationStatus.CONFLICT_DETECTED
    assert any("Endorsement conflict" in r for r in reasons)


def test_user_confirmation_cannot_erase_actual_conflict():
    """Verify that user confirmation strictly rejects overriding an active document conflict."""
    associator = PolicyScheduleAssociator()
    conflicted_schedule = PolicySchedule(
        schedule_id="sch_conflict_1",
        filename="niva_schedule.pdf",
        document_fingerprint="fp_conf_1",
        association_status=DocumentAssociationStatus.CONFLICT_DETECTED,
        conflicts=("Insurer mismatch detected.",),
    )

    confirmed_schedule = associator.confirm_association(conflicted_schedule)

    # Must NOT become USER_CONFIRMED; must remain CONFLICT_DETECTED
    assert confirmed_schedule.association_status == DocumentAssociationStatus.CONFLICT_DETECTED
    assert any("User confirmation rejected" in c for c in confirmed_schedule.conflicts)


def test_user_confirmation_applies_to_suggested_match():
    """Verify that user confirmation successfully updates a suggested match."""
    associator = PolicyScheduleAssociator()
    suggested_schedule = PolicySchedule(
        schedule_id="sch_sugg_1",
        filename="valid_schedule.pdf",
        document_fingerprint="fp_sugg_1",
        association_status=DocumentAssociationStatus.SUGGESTED_MATCH,
    )

    confirmed = associator.confirm_association(suggested_schedule)
    assert confirmed.association_status == DocumentAssociationStatus.USER_CONFIRMED


# =============================================================================
# 2. Rule-Based Rider Verification & Negative Cases
# =============================================================================

def test_ped_rider_present_but_inapplicable_benefit():
    """Verify that having an unrelated rider (Hospital Cash) does NOT reduce PED waiting period."""
    text = (
        "SECTION 2: WAITING PERIODS\n"
        "Expenses related to the treatment of a pre-existing disease (PED) shall be excluded until the expiry of 36 months of continuous coverage.\n\n"
        "Standard policy wording conditions and general terms line. " * 8 + "\n\n"
        "SECTION 8: OPTIONAL COVERS\n"
        "Upon purchase of this optional cover, the PED Waiting Period reduces from 36 months to 12 months."
    )
    pol = _create_mock_policy("ped_rider_test.pdf", text)
    evaluator = ScenarioEvaluator()

    # Schedule has Hospital Daily Cash Rider, but NO PED rider
    sch_with_other_rider = PolicySchedule(
        schedule_id="sch_hosp_cash",
        filename="schedule_with_cash_rider.pdf",
        document_fingerprint="fp_hosp_cash",
        optional_riders=("Hospital Daily Cash Rider",),
        association_status=DocumentAssociationStatus.SUGGESTED_MATCH,
    )

    # User indicates buy-back rider, but schedule proves it's for Hospital Daily Cash
    inp = ScenarioInput(
        scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
        elapsed_months=18,
        has_buyback_rider=True,
    )
    res = evaluator.evaluate(pol, inp, schedule=sch_with_other_rider)

    # Base 36-month waiting period must apply (18 < 36 -> WAITING_PERIOD_ACTIVE)
    assert res.verdict == ScenarioVerdict.WAITING_PERIOD_ACTIVE
    assert res.applicable_duration_amount == 36
    assert res.remaining_duration_amount == 18
    assert any("Hospital Daily Cash" in cond for cond in res.unresolved_conditions)


def test_ped_rider_present_but_duration_unknown():
    """Verify that when PED rider is documented but duration is unknown, verdict is INSUFFICIENT_EVIDENCE."""
    text = (
        "Pre-Existing Disease Waiting Period: 36 months\n"
        "Upon purchase of this optional cover, the PED Waiting Period reduces from 36 months to 12 months."
    )
    pol = _create_mock_policy("ped_rider_test.pdf", text)
    evaluator = ScenarioEvaluator()

    sch_with_ped_rider = PolicySchedule(
        schedule_id="sch_ped_active",
        filename="schedule_ped.pdf",
        document_fingerprint="fp_ped_active",
        optional_riders=("Pre-Existing Disease (PED) Waiting Period Modification Rider",),
        association_status=DocumentAssociationStatus.SUGGESTED_MATCH,
    )

    # User does not provide duration or dates
    inp_missing_dur = ScenarioInput(
        scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
        elapsed_months=None,
        has_buyback_rider=True,
    )
    res = evaluator.evaluate(pol, inp_missing_dur, schedule=sch_with_ped_rider)

    assert res.verdict == ScenarioVerdict.INSUFFICIENT_EVIDENCE
    assert res.decision_state == DecisionIntegrityState.EVIDENCE_INSUFFICIENT
    assert "Missing Policy Duration" in res.headline
    assert any("Continuous coverage duration" in inp for inp in res.missing_inputs)


def test_ped_rider_under_conflicted_schedule_suspended():
    """Verify that if a schedule has an unresolved document conflict, endorsement proof is suspended."""
    text = (
        "Pre-Existing Disease Waiting Period: 36 months\n"
        "Upon purchase of this optional cover, the PED Waiting Period reduces from 36 months to 12 months."
    )
    pol = _create_mock_policy("ped_rider_test.pdf", text)
    evaluator = ScenarioEvaluator()

    conflicted_sch = PolicySchedule(
        schedule_id="sch_conflicted",
        filename="conflicted_schedule.pdf",
        document_fingerprint="fp_conflicted",
        optional_riders=("Pre-Existing Disease (PED) Waiting Period Modification Rider",),
        association_status=DocumentAssociationStatus.CONFLICT_DETECTED,
        conflicts=("Insurer mismatch detected.",),
    )

    inp = ScenarioInput(
        scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
        elapsed_months=14,
        has_buyback_rider=True,
    )
    res = evaluator.evaluate(pol, inp, schedule=conflicted_sch)

    # Cannot be unconditionally satisfied while document conflict exists
    assert res.verdict == ScenarioVerdict.CONDITIONAL_REVIEW
    assert any("document conflict" in cond.lower() for cond in res.unresolved_conditions)


def test_ped_waiting_period_satisfaction_explicitly_disclaims_claim_approval():
    """Verify that satisfied waiting period includes strict disclaimers that it does NOT equal claim approval."""
    text = (
        "Pre-Existing Disease Waiting Period: 36 months\n"
        "Upon purchase of this optional cover, the PED Waiting Period reduces from 36 months to 12 months."
    )
    pol = _create_mock_policy("ped_rider_test.pdf", text)
    evaluator = ScenarioEvaluator()

    sch = PolicySchedule(
        schedule_id="sch_clean",
        filename="clean_schedule.pdf",
        document_fingerprint="fp_clean",
        optional_riders=("Pre-Existing Disease (PED) Waiting Period Modification Rider",),
        association_status=DocumentAssociationStatus.SUGGESTED_MATCH,
    )

    inp = ScenarioInput(
        scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
        elapsed_months=14,
        has_buyback_rider=True,
    )
    res = evaluator.evaluate(pol, inp, schedule=sch)

    assert res.verdict == ScenarioVerdict.WAITING_PERIOD_SATISFIED
    assert res.decision_state == DecisionIntegrityState.WAITING_PERIOD_CONDITION_SATISFIED
    # Check disclaimers
    assert any("does not confirm treatment admissibility" in lim.lower() for lim in res.limitations)
    assert any("claims adjudication" in lim.lower() for lim in res.limitations)


# =============================================================================
# 3. Calculation Hardening & Multi-Rule Cost Sharing
# =============================================================================

def test_copayment_deductible_sequential_calculation():
    """Verify that voluntary deductible is applied before co-payment to prevent double counting."""
    text = (
        "SECTION 3: TERMS\n"
        "This policy is subject to Co-payment of 10% of each and every claim amount for "
        "Insured Persons aged 61 years and above."
    )
    pol = _create_mock_policy("copay_deduct_test.pdf", text)
    evaluator = ScenarioEvaluator()

    # Schedule has voluntary deductible of Rs 25,000
    schedule = PolicySchedule(
        schedule_id="sch_ded",
        filename="schedule_ded.pdf",
        document_fingerprint="fp_ded",
        voluntary_deductible=25000.0,
    )

    inp = ScenarioInput(
        scenario_type=ScenarioType.ENTRY_AGE_COPAYMENT,
        member_age_at_entry=65,
        claim_amount=100000.0,
    )
    res = evaluator.evaluate(pol, inp, schedule=schedule)

    assert res.verdict == ScenarioVerdict.CONDITIONAL_REVIEW
    # Gross claim = 100,000. Deductible = 25,000. Remainder = 75,000.
    # Co-pay = 10% of 75,000 = 7,500. Insurer share = 67,500. Total patient = 32,500.
    assert res.calculated_copayment_amount == 7500.0
    assert res.calculated_insurer_portion == 67500.0
    assert "without double counting" in res.explanation
    assert res.calculation_formula is not None
    assert "Deductible Rs 25,000" in res.calculation_formula
    assert any("Admissible claim estimate does NOT equal the final insurer payout" in lim for lim in res.limitations)


# =============================================================================
# 4. Policy Identifier Privacy Audit
# =============================================================================

def test_policy_number_masking_comprehensive():
    """Verify various policy number patterns are securely pre-masked and raw digits never leak."""
    raw_numbers = [
        "POL1234567890",
        "2825 2045 1234 5678",
        "P/161114/01/2024/005432",
        "NB/987654321",
        "HDFC/MUM/2024/0009988",
    ]
    for raw in raw_numbers:
        masked = mask_policy_number(raw)
        # Suffix must be 4 characters
        clean_raw = raw.replace(" ", "")
        assert masked.endswith(clean_raw[-4:])
        # Middle digits must not appear unmasked
        mid_digits = clean_raw[3:-4]
        if len(mid_digits) >= 4:
            assert mid_digits not in masked


def test_exact_quote_does_not_leak_raw_policy_number():
    """Verify that ExtractedScheduleField.exact_quote masks the raw policy number."""
    raw_schedule_text = (
        "HDFC ERGO General Insurance Company Limited\n"
        "Policy No: 2825-9988-7766-4433\n"
        "Product: Optima Secure\n"
    )
    pol_doc = _create_mock_policy("priv_schedule.pdf", raw_schedule_text)
    extractor = PolicyScheduleExtractor()
    sch = extractor.extract(pol_doc)

    pol_field = next((f for f in sch.fields if f.field_key == "policy_number"), None)
    assert pol_field is not None
    assert pol_field.exact_quote is not None
    # Raw number 9988-7766 must NOT be in exact_quote
    assert "9988-7766" not in pol_field.exact_quote
    assert "******" in pol_field.exact_quote
