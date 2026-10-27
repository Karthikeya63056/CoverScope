"""Unit and integration tests for Policy Comparison and Protection Gap Analysis."""
from __future__ import annotations

import pymupdf
import pytest

from backend.domain.comparison import (
    ComparisonAssumptions,
    PolicyComparisonEngine,
    PolicyComparisonResult,
)
from backend.domain.enums import (
    ComparisonDimensionKey,
    ComparisonStatus,
    ProtectionGapSeverity,
)
from backend.qa.workflow import prepare_policy
from backend.services.policy_service import PolicyService


def make_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _create_mock_policy(filename: str, text: str):
    data = make_pdf(text)
    return prepare_policy(data, filename)


def test_compare_identical_policies():
    text = (
        "Pre-existing diseases are excluded for 36 months of continuous coverage.\n"
        "Expenses related to illness within 30 days shall be excluded."
    )
    pol_a = _create_mock_policy("Policy_A.pdf", text)
    engine = PolicyComparisonEngine()

    result = engine.compare(pol_a, pol_a)

    assert result.is_identical_policy is True
    assert result.policy_a_fingerprint == result.policy_b_fingerprint
    ped_comp = next(d for d in result.dimensions if d.dimension_key == ComparisonDimensionKey.PED_WAITING_PERIOD)
    assert "Identical policy document" in ped_comp.summary_difference


def test_compare_differing_waiting_periods():
    text_a = (
        "Pre-existing diseases are excluded for 36 months of continuous coverage.\n"
        "Expenses related to illness within 30 days shall be excluded."
    )
    text_b = (
        "Pre-existing diseases are excluded for 24 months of continuous coverage.\n"
        "Expenses related to illness within 30 days shall be excluded."
    )
    pol_a = _create_mock_policy("Plan_36m.pdf", text_a)
    pol_b = _create_mock_policy("Plan_24m.pdf", text_b)

    engine = PolicyComparisonEngine()
    result = engine.compare(pol_a, pol_b)

    assert result.is_identical_policy is False
    ped_comp = next(d for d in result.dimensions if d.dimension_key == ComparisonDimensionKey.PED_WAITING_PERIOD)

    assert ped_comp.policy_a_value.numeric_amount == 36.0
    assert ped_comp.policy_b_value.numeric_amount == 24.0
    assert "Plan_24m.pdf establishes a shorter waiting duration" in ped_comp.summary_difference
    assert ped_comp.status == ComparisonStatus.COMPARABLE


def test_one_policy_missing_clause_is_missing_not_excluded():
    text_a = (
        "Pre-existing diseases are excluded for 36 months of continuous coverage.\n"
        "5.1.11. Treatment for alcoholism or drug abuse is excluded. (Code-Excl12)"
    )
    text_b = "This policy document contains general definitions and introductory terms only."

    pol_a = _create_mock_policy("Doc_A.pdf", text_a)
    pol_b = _create_mock_policy("Doc_B.pdf", text_b)

    engine = PolicyComparisonEngine()
    result = engine.compare(pol_a, pol_b)

    ped_comp = next(d for d in result.dimensions if d.dimension_key == ComparisonDimensionKey.PED_WAITING_PERIOD)
    assert ped_comp.status == ComparisonStatus.MISSING_FROM_DOCUMENTS
    assert ped_comp.policy_a_value.is_available is True
    assert ped_comp.policy_b_value.is_available is False
    assert "no clause was found in Doc_B.pdf" in ped_comp.summary_difference

    # Protection gaps must flag unverified detail for Doc_B, not falsely assert coverage
    gap_unverified = next((g for g in result.protection_gaps if g.policy_filename == "Doc_B.pdf" and g.dimension_key == ComparisonDimensionKey.PED_WAITING_PERIOD), None)
    assert gap_unverified is not None
    assert gap_unverified.severity == ProtectionGapSeverity.UNVERIFIED_GAP


def test_both_policies_missing_clause():
    text_a = "General terms and definitions on page 1 without specific exclusion provisions."
    text_b = "General terms and conditions on page 1 with no specific exclusion provisions."

    pol_a = _create_mock_policy("Empty_A.pdf", text_a)
    pol_b = _create_mock_policy("Empty_B.pdf", text_b)

    engine = PolicyComparisonEngine()
    result = engine.compare(pol_a, pol_b)

    ped_comp = next(d for d in result.dimensions if d.dimension_key == ComparisonDimensionKey.PED_WAITING_PERIOD)
    assert ped_comp.status == ComparisonStatus.MISSING_FROM_DOCUMENTS
    assert "Neither policy document established a verified clause" in ped_comp.summary_difference


def test_copayment_comparison_and_cost_sharing_gap():
    text_a = "A co-payment of 10% applies to all admissible claims for persons aged 61 years and above at entry."
    text_b = "This policy has standard coverage limits with no entry age co-payment specified."

    pol_a = _create_mock_policy("Copay_Plan.pdf", text_a)
    pol_b = _create_mock_policy("Standard_Plan.pdf", text_b)

    service = PolicyService()
    assumptions = ComparisonAssumptions(member_entry_age=65, claim_amount=200000.0)

    result = service.compare_policies(pol_a, pol_b, assumptions=assumptions)

    copay_comp = next(d for d in result.dimensions if d.dimension_key == ComparisonDimensionKey.COPAYMENT)
    assert copay_comp.policy_a_value.numeric_amount == 10.0
    assert copay_comp.policy_b_value.numeric_amount == 0.0

    # Protection gap on Copay_Plan
    gap = next((g for g in result.protection_gaps if g.dimension_key == ComparisonDimensionKey.COPAYMENT and g.policy_filename == "Copay_Plan.pdf"), None)
    assert gap is not None
    assert gap.severity == ProtectionGapSeverity.CAUTION
    assert "₹20,000" in gap.description
    assert any("200,000" in a for a in gap.assumptions)


def test_policy_fingerprint_provenance_isolation():
    text_a = "Pre-existing diseases are excluded for 36 months of continuous coverage."
    text_b = "Pre-existing diseases are excluded for 24 months of continuous coverage."

    pol_a = _create_mock_policy("Pol_A.pdf", text_a)
    pol_b = _create_mock_policy("Pol_B.pdf", text_b)

    engine = PolicyComparisonEngine()
    result = engine.compare(pol_a, pol_b)

    ped_comp = next(d for d in result.dimensions if d.dimension_key == ComparisonDimensionKey.PED_WAITING_PERIOD)
    assert ped_comp.policy_a_value.policy_fingerprint == pol_a.fingerprint
    assert ped_comp.policy_b_value.policy_fingerprint == pol_b.fingerprint
    assert ped_comp.policy_a_value.source_page == 1
    assert ped_comp.policy_b_value.source_page == 1
    assert "36" in (ped_comp.policy_a_value.evidence_quote or "")
    assert "24" in (ped_comp.policy_b_value.evidence_quote or "")
