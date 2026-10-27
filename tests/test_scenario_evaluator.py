"""Tests for deterministic insurance scenario analysis engine."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import pymupdf
import pytest

from backend.domain.enums import (
    DurationUnit,
    FactCategory,
    FactValidationStatus,
    ScenarioType,
    ScenarioVerdict,
)
from backend.domain.models import DurationValue, EvidenceReference, PercentageValue, PolicyFact, SourceDocument
from backend.domain.scenario import ScenarioEvaluator, ScenarioInput, ScenarioResult, calculate_elapsed_time
from backend.qa.workflow import prepare_policy
from backend.services.policy_service import PolicyService

ROOT_DIR = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------------------
# 1. Month-Boundary & Timing Calculation Tests
# ------------------------------------------------------------------------------

def test_exact_month_boundary_calculations():
    """Verify month-boundary calculations without 30-day crude approximations."""
    # Case 1: Exactly 20 months
    m, d, notes = calculate_elapsed_time("2024-01-15", "2025-09-15")
    assert m == 20
    assert d == (date(2025, 9, 15) - date(2024, 1, 15)).days

    # Case 2: One day before the month boundary (19 full months elapsed)
    m, d, notes = calculate_elapsed_time("2024-01-15", "2025-09-14")
    assert m == 19

    # Case 3: Leap year month-end boundary (Jan 31 to Feb 29 2024 is exactly 1 month)
    m, d, notes = calculate_elapsed_time("2024-01-31", "2024-02-29")
    assert m == 1

    # Case 4: Non-leap year month-end boundary (Jan 31 to Feb 28 2025 is exactly 1 month)
    m, d, notes = calculate_elapsed_time("2025-01-31", "2025-02-28")
    assert m == 1

    # Case 5: Direct user-supplied duration
    m, d, notes = calculate_elapsed_time(None, None, user_elapsed_months=24)
    assert m == 24
    assert any("user" in n.lower() for n in notes)

    # Case 6: Invalid date order
    m, d, notes = calculate_elapsed_time("2025-01-01", "2024-01-01")
    assert m is None
    assert any("prior to" in n.lower() for n in notes)


# ------------------------------------------------------------------------------
# 2. Pre-Existing Disease Waiting Period Scenario Tests
# ------------------------------------------------------------------------------

def _create_mock_policy(doc_name: str, text: str):
    doc = pymupdf.open()
    p = doc.new_page()
    padded_text = text if len(text) >= 60 else text + "\n" + ("Standard policy text line padding. " * 3)
    p.insert_textbox(pymupdf.Rect(50, 50, 500, 300), padded_text)
    data = doc.tobytes()
    doc.close()
    return prepare_policy(data, doc_name)


def test_ped_waiting_period_active():
    """Verify WAITING_PERIOD_ACTIVE verdict when elapsed duration is less than waiting period."""
    text = (
        "SECTION 2: WAITING PERIODS\n"
        "Expenses related to the treatment of a pre-existing disease (PED) "
        "shall be excluded until the expiry of 36 months of continuous coverage."
    )
    pol = _create_mock_policy("ped_test.pdf", text)
    evaluator = ScenarioEvaluator()

    # User has 20 months continuous coverage (< 36 months)
    inp = ScenarioInput(
        scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
        elapsed_months=20,
    )
    res = evaluator.evaluate(pol, inp)

    assert res.verdict == ScenarioVerdict.WAITING_PERIOD_ACTIVE
    assert res.applicable_duration_amount == 36
    assert res.elapsed_duration_amount == 20
    assert res.remaining_duration_amount == 16
    assert "16 Months Remaining" in res.headline
    assert len(res.source_references) >= 1
    assert "pre-existing" in res.source_references[0]["quote"].lower()


def test_ped_waiting_period_satisfied_not_unconditional_coverage():
    """Verify WAITING_PERIOD_SATISFIED verdict when elapsed duration >= waiting period, with explicit safeguards."""
    text = (
        "SECTION 2: WAITING PERIODS\n"
        "Expenses related to the treatment of a pre-existing disease (PED) "
        "shall be excluded until the expiry of 36 months of continuous coverage."
    )
    pol = _create_mock_policy("ped_test.pdf", text)
    evaluator = ScenarioEvaluator()

    # User has 40 months continuous coverage (>= 36 months)
    inp = ScenarioInput(
        scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
        elapsed_months=40,
    )
    res = evaluator.evaluate(pol, inp)

    assert res.verdict == ScenarioVerdict.WAITING_PERIOD_SATISFIED
    assert res.remaining_duration_amount == 0
    assert "Satisfied" in res.headline
    # Must NOT present satisfaction as a positive claim approval guarantee
    assert any("does not confirm treatment admissibility" in lim for lim in res.limitations)
    assert any("medical necessity" in lim for lim in res.limitations)


def test_ped_waiting_period_missing_duration():
    """Verify INSUFFICIENT_EVIDENCE when elapsed duration is missing."""
    text = (
        "SECTION 2: WAITING PERIODS\n"
        "Expenses related to the treatment of a pre-existing disease (PED) "
        "shall be excluded until the expiry of 36 months of continuous coverage."
    )
    pol = _create_mock_policy("ped_test.pdf", text)
    evaluator = ScenarioEvaluator()

    inp = ScenarioInput(
        scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
        elapsed_months=None,
    )
    res = evaluator.evaluate(pol, inp)

    assert res.verdict == ScenarioVerdict.INSUFFICIENT_EVIDENCE
    assert "Missing Policy Duration" in res.headline
    assert len(res.missing_inputs) >= 1


def test_conditional_rider_buyback_waiting_period():
    """Verify rider-reduced waiting period evaluation with verification conditions."""
    text = (
        "Pre-Existing Disease Waiting Period: 36 months\n"
        "Upon purchase of this optional cover, the PED Waiting Period reduces from 36 months to 12 months."
    )
    pol = _create_mock_policy("star_buyback.pdf", text)
    evaluator = ScenarioEvaluator()

    # With buy-back rider and 14 months coverage (>= 12 months rider duration)
    inp = ScenarioInput(
        scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
        elapsed_months=14,
        has_buyback_rider=True,
    )
    res = evaluator.evaluate(pol, inp)

    assert res.applicable_duration_amount == 12
    # Unresolved schedule verification cannot be presented as unconditionally satisfied
    assert res.verdict == ScenarioVerdict.CONDITIONAL_REVIEW
    assert any("optional ped buy-back cover was endorsed" in cond.lower() for cond in res.unresolved_conditions)


# ------------------------------------------------------------------------------
# 3. Initial 30-Day Waiting Period Scenario Tests
# ------------------------------------------------------------------------------

def test_initial_waiting_period_active_and_satisfied():
    """Verify 30-day initial waiting period active vs satisfied verdicts."""
    text = (
        "5.1.3. 30-day waiting period (Code- Excl03): \n"
        "Expenses related to the treatment of any Illness within 30 days from the first Policy "
        "commencement date shall be excluded except claims arising due to an Accident."
    )
    pol = _create_mock_policy("init_test.pdf", text)
    evaluator = ScenarioEvaluator()

    # Case A: Day 12 of policy (< 30 days) -> ACTIVE
    inp_active = ScenarioInput(
        scenario_type=ScenarioType.INITIAL_WAITING_PERIOD,
        elapsed_days=12,
        is_accidental_injury=False,
    )
    res_active = evaluator.evaluate(pol, inp_active)
    assert res_active.verdict == ScenarioVerdict.WAITING_PERIOD_ACTIVE
    assert res_active.remaining_duration_amount == 18

    # Case B: Day 45 of policy (>= 30 days) -> SATISFIED
    inp_sat = ScenarioInput(
        scenario_type=ScenarioType.INITIAL_WAITING_PERIOD,
        elapsed_days=45,
        is_accidental_injury=False,
    )
    res_sat = evaluator.evaluate(pol, inp_sat)
    assert res_sat.verdict == ScenarioVerdict.WAITING_PERIOD_SATISFIED
    assert res_sat.remaining_duration_amount == 0


def test_initial_waiting_period_accidental_injury_exception():
    """Verify that accidental injury invokes the legal exception to initial waiting period."""
    text = (
        "5.1.3. 30-day waiting period (Code- Excl03): \n"
        "Expenses related to the treatment of any Illness within 30 days from the first Policy "
        "commencement date shall be excluded except claims arising due to an Accident."
    )
    pol = _create_mock_policy("init_test.pdf", text)
    evaluator = ScenarioEvaluator()

    inp_accident = ScenarioInput(
        scenario_type=ScenarioType.INITIAL_WAITING_PERIOD,
        elapsed_days=5,
        is_accidental_injury=True,
    )
    res_accident = evaluator.evaluate(pol, inp_accident)

    assert res_accident.verdict == ScenarioVerdict.CONDITIONAL_REVIEW
    assert "Accidental Injury" in res_accident.headline
    assert any("accidental injury" in cond.lower() for cond in res_accident.unresolved_conditions)


# ------------------------------------------------------------------------------
# 4. Exclusion & Exception Scenario Tests
# ------------------------------------------------------------------------------

def test_unconditional_exclusion_identified():
    """Verify EXCLUSION_IDENTIFIED for standard unconditional exclusions (e.g. alcoholism)."""
    text = (
        "5.1.11. Treatment for, alcoholism, drug or substance abuse or any "
        "addictive condition and consequences thereof. (Code-Excl12)"
    )
    pol = _create_mock_policy("alcohol_test.pdf", text)
    evaluator = ScenarioEvaluator()

    inp = ScenarioInput(
        scenario_type=ScenarioType.CONDITIONAL_EXCLUSION,
        condition_name="Alcoholism & Substance Abuse",
    )
    res = evaluator.evaluate(pol, inp)

    assert res.verdict == ScenarioVerdict.EXCLUSION_IDENTIFIED
    assert "Standard Exclusion" in res.headline
    assert len(res.source_references) >= 1
    assert "alcoholism" in res.source_references[0]["quote"].lower()


def test_conditional_exclusion_with_clinical_exceptions():
    """Verify CONDITIONAL_REVIEW and explicit unresolved criteria for obesity surgery."""
    text = (
        "5.1.6. Obesity/ Weight Control (Code-Excl06)\n"
        "Expenses related to the surgical treatment of obesity that does not fulfil all the below conditions:\n"
        "a. Surgery upon doctor advice. b. Body Mass Index (BMI) >= 40."
    )
    pol = _create_mock_policy("obesity_test.pdf", text)
    evaluator = ScenarioEvaluator()

    inp = ScenarioInput(
        scenario_type=ScenarioType.CONDITIONAL_EXCLUSION,
        condition_name="Obesity / Weight Control Surgery",
    )
    res = evaluator.evaluate(pol, inp)

    assert res.verdict == ScenarioVerdict.CONDITIONAL_REVIEW
    assert "Conditional Exclusion" in res.headline
    assert len(res.unresolved_conditions) >= 1
    assert any("bmi" in cond.lower() or "clinical" in cond.lower() for cond in res.unresolved_conditions)


# ------------------------------------------------------------------------------
# 5. Co-Payment & Claim Share Tests
# ------------------------------------------------------------------------------

def test_copayment_calculation_with_and_without_claim_amount():
    """Verify entry-age co-payment arithmetic with known claim amount and percentage formula without amount."""
    text = (
        "SECTION 3: TERMS\n"
        "This policy is subject to Co-payment of 10% of each and every claim amount for "
        "fresh as well as renewal policies for Insured Persons aged 61 years and above."
    )
    pol = _create_mock_policy("copay_test.pdf", text)
    evaluator = ScenarioEvaluator()

    # Case A: Age 65, claim amount Rs 1,00,000 -> Patient share 10,000, Insurer share 90,000
    inp_calc = ScenarioInput(
        scenario_type=ScenarioType.ENTRY_AGE_COPAYMENT,
        member_age_at_entry=65,
        claim_amount=100000.0,
    )
    res_calc = evaluator.evaluate(pol, inp_calc)
    assert res_calc.verdict == ScenarioVerdict.CONDITIONAL_REVIEW
    assert res_calc.copayment_percentage == 10.0
    assert res_calc.calculated_copayment_amount == 10000.0
    assert res_calc.calculated_insurer_portion == 90000.0
    assert "10,000" in res_calc.headline

    # Case B: Age 65, claim amount unknown -> Percentage formula explanation
    inp_no_amt = ScenarioInput(
        scenario_type=ScenarioType.ENTRY_AGE_COPAYMENT,
        member_age_at_entry=65,
        claim_amount=None,
    )
    res_no_amt = evaluator.evaluate(pol, inp_no_amt)
    assert res_no_amt.verdict == ScenarioVerdict.CONDITIONAL_REVIEW
    assert res_no_amt.copayment_percentage == 10.0
    assert res_no_amt.calculated_copayment_amount is None
    assert "Patient Share = Admissible Claim Amount * 0.1" in res_no_amt.explanation

    # Case C: Age 55 (< 61 threshold) -> Co-payment does not apply
    inp_young = ScenarioInput(
        scenario_type=ScenarioType.ENTRY_AGE_COPAYMENT,
        member_age_at_entry=55,
        claim_amount=100000.0,
    )
    res_young = evaluator.evaluate(pol, inp_young)
    assert res_young.verdict == ScenarioVerdict.WAITING_PERIOD_SATISFIED
    assert "Does Not Apply" in res_young.headline

    # Case D: Missing member entry age -> INSUFFICIENT_EVIDENCE
    inp_missing_age = ScenarioInput(
        scenario_type=ScenarioType.ENTRY_AGE_COPAYMENT,
        member_age_at_entry=None,
    )
    res_missing_age = evaluator.evaluate(pol, inp_missing_age)
    assert res_missing_age.verdict == ScenarioVerdict.INSUFFICIENT_EVIDENCE
    assert "Entry Age Required" in res_missing_age.headline


# ------------------------------------------------------------------------------
# 6. Safety & Negative Tests
# ------------------------------------------------------------------------------

def test_unsupported_scenario_clean_abstention():
    """Verify that unsupported scenarios abstain cleanly with UNSUPPORTED_SCENARIO."""
    pol = _create_mock_policy("dummy.pdf", "General insurance policy terms.")
    evaluator = ScenarioEvaluator()

    inp = ScenarioInput(scenario_type=ScenarioType.UNSUPPORTED)
    res = evaluator.evaluate(pol, inp)

    assert res.verdict == ScenarioVerdict.UNSUPPORTED_SCENARIO
    assert "Unsupported" in res.headline


def test_fact_from_different_policy_rejected():
    """Verify that facts from a different policy cannot be applied."""
    pol_a = _create_mock_policy("policy_a.pdf", "No waiting period defined.")
    evaluator = ScenarioEvaluator()

    # Fact belonging to doc_other
    alien_fact = PolicyFact(
        fact_id="fact_alien_001",
        document_id="doc_other",
        category=FactCategory.WAITING_PERIOD,
        proposition="PED waiting period of 36 months.",
        structured_value=DurationValue(amount=36, unit=DurationUnit.MONTHS),
        validation_status=FactValidationStatus.REJECTED,  # Rejected status
    )

    inp = ScenarioInput(
        scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
        elapsed_months=20,
    )
    # Passed facts list with rejected alien fact
    res = evaluator.evaluate(pol_a, inp, facts=[alien_fact])
    assert res.verdict == ScenarioVerdict.INSUFFICIENT_EVIDENCE


def test_bundled_pdf_end_to_end_evaluation(tmp_path):
    """End-to-end integration test against actual bundled Star Comprehensive brochure."""
    star_pdf_path = ROOT_DIR / "pdfs" / "Brochure_Star_Comprehensive_Insurance_Policy_V_15_Web_633bcfcaaf.pdf"
    assert star_pdf_path.exists()
    with open(star_pdf_path, "rb") as f:
        data = f.read()

    service = PolicyService()
    pol = service.prepare_policy(data, star_pdf_path.name)

    # 1. Evaluate PED in month 20 (base 36 months) -> ACTIVE
    inp_ped = ScenarioInput(
        scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
        elapsed_months=20,
        has_buyback_rider=False,
    )
    res_ped = service.evaluate_scenario(pol, inp_ped)
    assert res_ped.verdict == ScenarioVerdict.WAITING_PERIOD_ACTIVE
    assert res_ped.applicable_duration_amount == 36
    assert res_ped.remaining_duration_amount == 16

    # 2. Evaluate PED with buy-back cover in month 20 (12 months rider) -> CONDITIONAL_REVIEW (requires schedule verification)
    inp_buyback = ScenarioInput(
        scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
        elapsed_months=20,
        has_buyback_rider=True,
    )
    res_buyback = service.evaluate_scenario(pol, inp_buyback)
    assert res_buyback.verdict == ScenarioVerdict.CONDITIONAL_REVIEW
    assert res_buyback.applicable_duration_amount == 12
    assert any("Policy Schedule" in c for c in res_buyback.unresolved_conditions)

    # 3. Evaluate entry-age co-payment for 65-year-old on Rs 2,00,000 claim -> Rs 20,000 patient share
    inp_copay = ScenarioInput(
        scenario_type=ScenarioType.ENTRY_AGE_COPAYMENT,
        member_age_at_entry=65,
        claim_amount=200000.0,
    )
    res_copay = service.evaluate_scenario(pol, inp_copay)
    assert res_copay.verdict == ScenarioVerdict.CONDITIONAL_REVIEW
    assert res_copay.copayment_percentage == 10.0
    assert res_copay.calculated_copayment_amount == 20000.0
    assert res_copay.calculated_insurer_portion == 180000.0
    assert res_copay.policy_fingerprint == pol.fingerprint


def test_rider_toggle_cannot_be_unconditionally_satisfied():
    """Verify that user-toggled optional rider is marked CONDITIONAL_REVIEW, never unconditional."""
    text = (
        "Pre-existing diseases are excluded for 36 months of continuous coverage.\n"
        "Upon purchase of this optional cover, the PED Waiting Period reduces from 36 months to 12 months."
    )
    pol = _create_mock_policy("ped_rider.pdf", text)
    evaluator = ScenarioEvaluator()

    # User toggles buyback with 15 months elapsed (which exceeds 12 months rider)
    inp = ScenarioInput(
        scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
        elapsed_months=15,
        has_buyback_rider=True,
    )
    res = evaluator.evaluate(pol, inp)

    # Must NOT be WAITING_PERIOD_SATISFIED unconditionally
    assert res.verdict == ScenarioVerdict.CONDITIONAL_REVIEW
    assert "Conditionally Satisfied" in res.headline
    assert len(res.unresolved_conditions) >= 1
    assert any("Policy Schedule" in c for c in res.unresolved_conditions)


def test_scenario_result_provenance_and_fingerprint_binding():
    """Verify that all ScenarioResult instantiations bind to the source policy fingerprint."""
    text = (
        "Pre-existing diseases are excluded for 36 months of continuous coverage.\n"
        "Expenses related to the treatment of any illness within 30 days from the first policy commencement date shall be excluded.\n"
        "5.1.11. Treatment for alcoholism or substance abuse is excluded. (Code-Excl12)\n"
        "A co-payment of 10% applies to all admissible claims for persons aged 61 years and above at entry."
    )
    pol = _create_mock_policy("provenance_test.pdf", text)
    evaluator = ScenarioEvaluator()

    # PED scenario
    res_ped = evaluator.evaluate(pol, ScenarioInput(scenario_type=ScenarioType.PRE_EXISTING_CONDITION, elapsed_months=10))
    assert res_ped.policy_fingerprint == pol.fingerprint

    # Initial waiting period
    res_init = evaluator.evaluate(pol, ScenarioInput(scenario_type=ScenarioType.INITIAL_WAITING_PERIOD, elapsed_days=10))
    assert res_init.policy_fingerprint == pol.fingerprint

    # Exclusion
    res_excl = evaluator.evaluate(pol, ScenarioInput(scenario_type=ScenarioType.CONDITIONAL_EXCLUSION, condition_name="Alcoholism"))
    assert res_excl.policy_fingerprint == pol.fingerprint

    # Co-payment
    res_copay = evaluator.evaluate(pol, ScenarioInput(scenario_type=ScenarioType.ENTRY_AGE_COPAYMENT, member_age_at_entry=65, claim_amount=100000.0))
    assert res_copay.policy_fingerprint == pol.fingerprint

    # Insufficient evidence on clean policy without PED
    empty_pol = _create_mock_policy("empty.pdf", "This policy document contains general terms and definitions only with no waiting periods.")
    res_empty = evaluator.evaluate(empty_pol, ScenarioInput(scenario_type=ScenarioType.PRE_EXISTING_CONDITION, elapsed_months=10))
    assert res_empty.policy_fingerprint == empty_pol.fingerprint
    assert res_empty.verdict == ScenarioVerdict.INSUFFICIENT_EVIDENCE
