"""Tests for Claim Rehearsal service and API endpoints."""
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.api.deps import cache_processed_policy, create_access_token
from backend.api.schemas import ClaimRehearsalRequest
from backend.main import app
from backend.qa.workflow import prepare_policy
from backend.services.claim_rehearsal_service import evaluate_claim_rehearsal
from backend.services.auth_service import AuthUser

client = TestClient(app)

SAMPLE_POLICY_TEXT = """
Section 1. Coverage Benefits
In-patient Hospitalization Expenses: Room Rent (Single Private A/C Room) is covered up to Sum Insured.
Day Care Treatment: All day care procedures are covered up to Sum Insured.

Section 2. Waiting Periods
Initial Waiting Period: 30 days for any illness except accidental injury.
Specific Waiting Period: 24 months for cataract, hernia, joint replacement, hysterectomy, and gall bladder stones.
Pre-Existing Diseases: 36 months of continuous coverage before expenses are payable.

Section 3. Co-Payment
A 10% co-payment applies on each and every claim for insured persons whose age at entry is 61 years or above.
"""


@pytest.fixture(scope="module")
def prepared_sample_policy():
    from tests.test_workflow import make_pdf
    pdf_bytes = make_pdf(SAMPLE_POLICY_TEXT)
    policy = prepare_policy(pdf_bytes, "test_rehearsal_policy.pdf")
    cache_processed_policy(policy, user_id=None)
    return policy


@pytest.fixture
def auth_headers():
    user = AuthUser(
        user_id="rehearsal_tester",
        email="tester@example.com",
        display_name="Tester",
        role="policyholder",
    )
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


def test_claim_rehearsal_specific_ailment_waiting_period_active(prepared_sample_policy):
    req = ClaimRehearsalRequest(
        policy_id=prepared_sample_policy.fingerprint,
        treatment_description="Total Knee Replacement Surgery",
        estimated_expense=300000.0,
        policy_duration_months=12,  # less than 24 months
        member_age=50,
        room_category="single_private",
    )
    res = evaluate_claim_rehearsal(prepared_sample_policy, req)
    assert res.readiness_status == "important_checks_required"
    assert any("Specific Waiting Period Applicable" in c["title"] for c in res.relevant_conditions)
    assert len(res.supporting_clauses) > 0
    assert len(res.checklist) >= 3
    assert len(res.questions_to_ask_tpa) > 0


def test_claim_rehearsal_waiting_period_satisfied(prepared_sample_policy):
    req = ClaimRehearsalRequest(
        policy_id=prepared_sample_policy.fingerprint,
        treatment_description="Cataract Surgery in Right Eye",
        estimated_expense=50000.0,
        policy_duration_months=30,  # exceeds 24 months
        member_age=55,
        room_category="single_private",
    )
    res = evaluate_claim_rehearsal(prepared_sample_policy, req)
    assert res.readiness_status == "ready_to_verify"
    assert any("Waiting Period Satisfied" in c["title"] for c in res.relevant_conditions)


def test_claim_rehearsal_senior_citizen_copayment_financials(prepared_sample_policy):
    bill = 200000.0
    req = ClaimRehearsalRequest(
        policy_id=prepared_sample_policy.fingerprint,
        treatment_description="Laparoscopic Appendectomy",
        estimated_expense=bill,
        policy_duration_months=24,
        member_age=65,  # >= 61 triggers 10% copay
        room_category="single_private",
    )
    res = evaluate_claim_rehearsal(prepared_sample_policy, req)
    assert res.financial_breakdown is not None
    fb = res.financial_breakdown
    assert fb.copayment_percentage == 10.0
    assert fb.deductible_or_copay_amount == 20000.0
    assert fb.estimated_out_of_pocket > 20000.0
    assert fb.estimated_insurer_coverage < bill


def test_claim_rehearsal_room_category_proportionate_deduction(prepared_sample_policy):
    req = ClaimRehearsalRequest(
        policy_id=prepared_sample_policy.fingerprint,
        treatment_description="Fever and Dengue Hospitalization",
        estimated_expense=100000.0,
        policy_duration_months=24,
        member_age=40,
        room_category="deluxe_suite",  # triggers room rent warning
    )
    res = evaluate_claim_rehearsal(prepared_sample_policy, req)
    assert res.readiness_status == "important_checks_required"
    assert any("Proportionate Deduction Risk" in c["title"] for c in res.relevant_conditions)
    assert res.financial_breakdown is not None
    assert res.financial_breakdown.room_rent_deduction_amount is not None


def test_claim_rehearsal_insufficient_information(prepared_sample_policy):
    req = ClaimRehearsalRequest(
        policy_id=prepared_sample_policy.fingerprint,
        treatment_description="ill",  # too short
        policy_duration_months=12,
    )
    res = evaluate_claim_rehearsal(prepared_sample_policy, req)
    assert res.readiness_status == "insufficient_information"
    assert len(res.missing_information) > 0


def test_claim_rehearsal_api_endpoint_auth_required():
    # Unauthenticated request must return 401
    resp = client.post(
        "/api/v1/claim-rehearsal/rehearse",
        json={"policy_id": "dummy", "treatment_description": "Surgery"},
    )
    assert resp.status_code == 401


def test_claim_rehearsal_api_endpoint_success(prepared_sample_policy, auth_headers):
    payload = {
        "policy_id": prepared_sample_policy.fingerprint,
        "treatment_description": "Total Knee Replacement",
        "estimated_expense": 250000,
        "member_age": 62,
        "policy_duration_months": 18,
        "room_category": "single_private",
        "hospital_type": "network_cashless",
    }
    resp = client.post("/api/v1/claim-rehearsal/rehearse", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "rehearsal_id" in data
    assert data["policy_id"] == prepared_sample_policy.fingerprint
    assert data["readiness_status"] in ["ready_to_verify", "important_checks_required"]
    assert len(data["checklist"]) >= 3
    assert len(data["questions_to_ask_tpa"]) >= 1


def test_claim_rehearsal_history_endpoint(auth_headers):
    resp = client.get("/api/v1/claim-rehearsal/history", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_claim_rehearsal_history_unauthenticated_rejected():
    resp = client.get("/api/v1/claim-rehearsal/history")
    assert resp.status_code == 401


def test_claim_rehearsal_history_with_valid_policy_filter(prepared_sample_policy, auth_headers):
    resp = client.get(
        f"/api/v1/claim-rehearsal/history?policy_id={prepared_sample_policy.fingerprint}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_claim_rehearsal_history_with_nonexistent_policy_filter(auth_headers):
    resp = client.get(
        "/api/v1/claim-rehearsal/history?policy_id=nonexistent-policy-9999",
        headers=auth_headers,
    )
    assert resp.status_code == 404
    assert "not found or access denied" in resp.json()["detail"].lower()


def test_claim_rehearsal_sublimit_and_copay_admissibility(prepared_sample_policy):
    """Ensure copay applies to admissible amount and out-of-pocket is clamped to total bill."""
    req = ClaimRehearsalRequest(
        policy_id=prepared_sample_policy.fingerprint,
        treatment_description="Cataract Eye Surgery with Monofocal Lens",
        estimated_expense=120000.0,
        policy_duration_months=36,
        member_age=65,  # triggers 10% copay
        room_category="single_private",
    )
    res = evaluate_claim_rehearsal(prepared_sample_policy, req)
    assert res.financial_breakdown is not None
    fb = res.financial_breakdown
    assert fb.estimated_out_of_pocket <= 120000.0
    assert fb.estimated_insurer_coverage >= 0.0
    # Insurer coverage + out of pocket must be coherent
    assert fb.estimated_out_of_pocket + fb.estimated_insurer_coverage >= 120000.0


def test_claim_rehearsal_no_false_positive_substring_match(prepared_sample_policy):
    """Ensure non-clinical substrings do not trigger false positive specific waiting periods."""
    req = ClaimRehearsalRequest(
        policy_id=prepared_sample_policy.fingerprint,
        treatment_description="Home delivery of prescription medications and medical records",
        estimated_expense=5000.0,
        policy_duration_months=36,
        member_age=30,
        room_category="single_private",
    )
    res = evaluate_claim_rehearsal(prepared_sample_policy, req)
    # Should not trigger maternity delivery waiting period
    assert not any("Maternity delivery" in c["title"] for c in res.relevant_conditions)

