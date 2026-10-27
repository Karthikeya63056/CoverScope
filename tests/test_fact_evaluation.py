"""Tests for gold fact dataset integrity, semantic validation, and offline evaluation."""
from __future__ import annotations

import json
from pathlib import Path
import pymupdf
import pytest

from backend.document_processing.normalization import normalize_for_match
from backend.domain.adapter import extract_candidate_facts
from backend.domain.enums import FactCategory, FactValidationStatus
from backend.domain.models import DurationUnit, DurationValue, EvidenceReference, PolicyFact, SourceDocument
from backend.domain.validation import validate_domain_bundle, validate_fact
from backend.qa.workflow import prepare_policy
from scripts.evaluate_facts import DEFAULT_GOLD_PATH, evaluate_policy_facts, load_gold_facts

ROOT_DIR = Path(__file__).resolve().parents[1]


def test_gold_dataset_integrity():
    """Verify gold facts dataset is well-formed, all PDFs exist, and quotes match verbatim."""
    assert DEFAULT_GOLD_PATH.exists()
    gold_facts = load_gold_facts(DEFAULT_GOLD_PATH)
    assert len(gold_facts) >= 15

    for item in gold_facts:
        assert "id" in item
        assert "document_file" in item
        assert "page_number" in item
        assert item["page_number"] >= 1
        assert "quote" in item
        assert "category" in item
        assert "expected_status" in item

        pdf_path = ROOT_DIR / item["document_file"]
        assert pdf_path.exists(), f"Gold dataset references non-existent PDF: {pdf_path}"

        # If not a negative test case, quote must exist verbatim in the PDF
        if item["expected_status"] != "rejected":
            doc = pymupdf.open(pdf_path)
            assert item["page_number"] <= len(doc), f"Page out of bounds for {pdf_path}"
            page_text = doc[item["page_number"] - 1].get_text("text")
            assert normalize_for_match(item["quote"]) in normalize_for_match(page_text), (
                f"Gold quote for {item['id']} not found on page {item['page_number']} of {item['document_file']}"
            )


def test_copayment_and_percentage_extraction():
    """Verify co-payment extraction extracts percentage values and scopes correctly."""
    text = (
        "SECTION 3: TERMS\n"
        "This policy is subject to Co-payment of 10% of each and every claim amount for "
        "fresh as well as renewal policies for Insured Persons aged 61 years and above."
    )
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_textbox(pymupdf.Rect(50, 50, 500, 300), text)
    data = doc.tobytes()
    doc.close()

    pol = prepare_policy(data, "copay_test.pdf")
    facts = extract_candidate_facts(pol)

    copay_facts = [f for f in facts if f.category == FactCategory.DEDUCTIBLE_OR_COPAY]
    assert len(copay_facts) >= 1
    f = copay_facts[0]
    assert f.structured_value is not None
    assert getattr(f.structured_value, "percentage") == 10.0
    assert getattr(f.structured_value, "scope") == "copayment"
    assert "61" in f.conditions[0]


def test_conditional_clauses_marked_needs_review():
    """Verify conditional clauses and exceptions are marked NEEDS_REVIEW with explicit reasons."""
    text = (
        "SECTION 4: EXCLUSIONS\n"
        "5.1.6. Obesity/ Weight Control (Code-Excl06)\n"
        "Expenses related to the surgical treatment of obesity that does not fulfil all the below conditions:\n"
        "a. Surgery is upon doctor advice. b. Body Mass Index (BMI) greater than or equal to 40."
    )
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()

    pol = prepare_policy(data, "obesity_test.pdf")
    facts = extract_candidate_facts(pol)

    obesity_facts = [f for f in facts if "obesity" in f.proposition.lower()]
    assert len(obesity_facts) >= 1
    f = obesity_facts[0]
    assert f.validation_status == FactValidationStatus.NEEDS_REVIEW
    assert any("clinical exceptions" in r.lower() for r in f.review_reasons)
    assert len(f.exceptions) >= 1


def test_conflicting_unconditional_facts_flagged_by_validator():
    """Verify that multiple conflicting unconditional facts on the same scope trigger a validation warning."""
    doc = SourceDocument(
        document_id="doc_conflict",
        filename="conflict.pdf",
        content_hash="h1",
        page_count=5,
        size_bytes=1000,
    )
    fact1 = PolicyFact(
        fact_id="f1",
        document_id="doc_conflict",
        category=FactCategory.WAITING_PERIOD,
        proposition="Pre-existing disease waiting period of 36 months.",
        structured_value=DurationValue(amount=36, unit=DurationUnit.MONTHS),
        validation_status=FactValidationStatus.EVIDENCE_GROUNDED,
    )
    fact2 = PolicyFact(
        fact_id="f2",
        document_id="doc_conflict",
        category=FactCategory.WAITING_PERIOD,
        proposition="Pre-existing disease waiting period of 12 months.",
        structured_value=DurationValue(amount=12, unit=DurationUnit.MONTHS),
        validation_status=FactValidationStatus.EVIDENCE_GROUNDED,
    )

    report = validate_domain_bundle([doc], [fact1, fact2])
    warnings = [w for w in report.warnings if "conflicting" in w.message.lower()]
    assert len(warnings) >= 1
    assert "pre-existing" in warnings[0].message.lower()


# ==============================================================================
# Phase 1.4 Hardening & Regression Tests
# ==============================================================================

def test_clause_split_across_lines():
    """Test 1: Clause split across lines in extracted PDF text is extracted accurately."""
    text = (
        "SECTION 2. WAITING PERIODS\n"
        "Expenses related to the treatment of a pre-existing\n"
        "disease (PED) and its direct complications shall be excluded until the\n"
        "expiry of 36 months of continuous coverage."
    )
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_textbox(pymupdf.Rect(50, 50, 500, 300), text)
    data = doc.tobytes()
    doc.close()

    pol = prepare_policy(data, "split_clause.pdf")
    facts = extract_candidate_facts(pol)

    ped_facts = [f for f in facts if f.category == FactCategory.WAITING_PERIOD and "pre-existing" in f.proposition.lower()]
    assert len(ped_facts) == 1
    assert ped_facts[0].structured_value is not None
    assert getattr(ped_facts[0].structured_value, "amount") == 36
    assert getattr(ped_facts[0].structured_value, "unit") == DurationUnit.MONTHS


def test_unrelated_definition_lookback_number_not_extracted_as_waiting_period():
    """Test 2: A definition lookback window is not mistakenly extracted as an exclusion waiting period."""
    text = (
        "SECTION 1. DEFINITIONS\n"
        "Pre-Existing Disease means any condition, ailment, injury or disease:\n"
        "a) that is/are diagnosed by a physician not more than 36 months prior to the effective date."
    )
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_textbox(pymupdf.Rect(50, 50, 500, 300), text)
    data = doc.tobytes()
    doc.close()

    pol = prepare_policy(data, "definition_lookback.pdf")
    facts = extract_candidate_facts(pol)

    # Must NOT extract definition lookback as an exclusion waiting period
    waiting_facts = [f for f in facts if f.category == FactCategory.WAITING_PERIOD]
    assert len(waiting_facts) == 0


def test_different_procedures_do_not_conflict():
    """Test 3: Two waiting periods applying to different procedures do not trigger a conflict warning."""
    doc = SourceDocument(
        document_id="doc_diff",
        filename="diff.pdf",
        content_hash="h_diff",
        page_count=5,
        size_bytes=1000,
    )
    fact_bariatric = PolicyFact(
        fact_id="f_bari",
        document_id="doc_diff",
        category=FactCategory.WAITING_PERIOD,
        proposition="Waiting period for Bariatric Surgery is 36 months on page 12.",
        structured_value=DurationValue(amount=36, unit=DurationUnit.MONTHS),
        validation_status=FactValidationStatus.EVIDENCE_GROUNDED,
    )
    fact_delivery = PolicyFact(
        fact_id="f_deliv",
        document_id="doc_diff",
        category=FactCategory.WAITING_PERIOD,
        proposition="Waiting period for Delivery Expenses is 24 months on page 12.",
        structured_value=DurationValue(amount=24, unit=DurationUnit.MONTHS),
        validation_status=FactValidationStatus.EVIDENCE_GROUNDED,
    )

    report = validate_domain_bundle([doc], [fact_bariatric, fact_delivery])
    conflict_warnings = [w for w in report.warnings if "conflicting" in w.message.lower()]
    assert len(conflict_warnings) == 0


def test_base_policy_modified_by_optional_rider_no_conflict():
    """Test 4: Base policy waiting period modified by an optional rider does not produce conflict warnings."""
    doc = SourceDocument(
        document_id="doc_rider",
        filename="rider.pdf",
        content_hash="h_rider",
        page_count=5,
        size_bytes=1000,
    )
    fact_base = PolicyFact(
        fact_id="f_base",
        document_id="doc_rider",
        category=FactCategory.WAITING_PERIOD,
        proposition="Pre-existing disease waiting period of 36 months on page 12.",
        structured_value=DurationValue(amount=36, unit=DurationUnit.MONTHS),
        validation_status=FactValidationStatus.EVIDENCE_GROUNDED,
    )
    fact_rider = PolicyFact(
        fact_id="f_rider",
        document_id="doc_rider",
        category=FactCategory.WAITING_PERIOD,
        proposition="Optional cover reduces pre-existing disease waiting period to 12 months on page 12.",
        conditions=("Upon purchase of optional buy-back cover",),
        structured_value=DurationValue(amount=12, unit=DurationUnit.MONTHS),
        validation_status=FactValidationStatus.NEEDS_REVIEW,
        review_reasons=("Optional rider modifying base waiting period",),
    )

    report = validate_domain_bundle([doc], [fact_base, fact_rider])
    conflict_warnings = [w for w in report.warnings if "conflicting" in w.message.lower()]
    assert len(conflict_warnings) == 0


def test_exception_to_exclusion_cannot_be_semantically_confirmed_unconditionally():
    """Test 5: An exclusion with exceptions cannot be marked SEMANTICALLY_CONFIRMED without resolution."""
    doc = SourceDocument(
        document_id="doc_ex",
        filename="ex.pdf",
        content_hash="h_ex",
        page_count=5,
        size_bytes=1000,
    )
    ev = EvidenceReference(
        evidence_id="ev_ex",
        document_id="doc_ex",
        page_number=1,
        exact_text="Surgery for obesity is excluded except when BMI >= 40.",
        validation_status=FactValidationStatus.EVIDENCE_GROUNDED,
    )
    # Incorrectly claiming semantic confirmation on a conditional exclusion
    fact = PolicyFact(
        fact_id="f_obesity",
        document_id="doc_ex",
        category=FactCategory.EXCLUSION,
        proposition="Obesity surgery is excluded.",
        evidence_references=(ev,),
        exceptions=("Surgeries meeting BMI >= 40 are eligible",),
        validation_status=FactValidationStatus.SEMANTICALLY_CONFIRMED,
    )

    report = validate_domain_bundle([doc], [fact], page_texts={("doc_ex", 1): ev.exact_text})
    errors = [e for e in report.errors if "SEMANTICALLY_CONFIRMED" in e.message]
    assert len(errors) >= 1
    assert "conditions or exceptions" in errors[0].message.lower()


def test_duplicate_candidate_facts_detected():
    """Test 6: Duplicate candidate facts within the same document are flagged by the validator."""
    doc = SourceDocument(
        document_id="doc_dup",
        filename="dup.pdf",
        content_hash="h_dup",
        page_count=5,
        size_bytes=1000,
    )
    ev = EvidenceReference(
        evidence_id="ev_dup",
        document_id="doc_dup",
        page_number=2,
        exact_text="30-day waiting period applies.",
        validation_status=FactValidationStatus.EVIDENCE_GROUNDED,
    )
    f1 = PolicyFact(
        fact_id="f1",
        document_id="doc_dup",
        category=FactCategory.WAITING_PERIOD,
        proposition="Initial waiting period of 30 days.",
        evidence_references=(ev,),
        structured_value=DurationValue(amount=30, unit=DurationUnit.DAYS),
        validation_status=FactValidationStatus.EVIDENCE_GROUNDED,
    )
    f2 = PolicyFact(
        fact_id="f2",
        document_id="doc_dup",
        category=FactCategory.WAITING_PERIOD,
        proposition="Initial waiting period of 30 days.",
        evidence_references=(ev,),
        structured_value=DurationValue(amount=30, unit=DurationUnit.DAYS),
        validation_status=FactValidationStatus.EVIDENCE_GROUNDED,
    )

    report = validate_domain_bundle([doc], [f1, f2], page_texts={("doc_dup", 2): ev.exact_text})
    dup_warnings = [w for w in report.warnings if "duplicate candidate fact" in w.message.lower()]
    assert len(dup_warnings) >= 1


def test_evidence_from_wrong_page_or_mismatched_document():
    """Test 7: Evidence citing a non-existent page or mismatched document is rejected."""
    doc = SourceDocument(
        document_id="doc_real",
        filename="real.pdf",
        content_hash="h_real",
        page_count=5,
        size_bytes=1000,
    )
    # Citing page 99 (out of bounds)
    ev_oob = EvidenceReference(
        evidence_id="ev_oob",
        document_id="doc_real",
        page_number=99,
        exact_text="Sample text",
    )
    fact_oob = PolicyFact(
        fact_id="f_oob",
        document_id="doc_real",
        category=FactCategory.WAITING_PERIOD,
        proposition="Sample proposition",
        evidence_references=(ev_oob,),
        validation_status=FactValidationStatus.EVIDENCE_GROUNDED,
    )
    report_oob = validate_domain_bundle([doc], [fact_oob])
    assert any("out of bounds" in e.message.lower() for e in report_oob.errors)

    # Citing mismatched document_id
    ev_mismatch = EvidenceReference(
        evidence_id="ev_mis",
        document_id="other_doc",
        page_number=1,
        exact_text="Sample text",
    )
    fact_mismatch = PolicyFact(
        fact_id="f_mis",
        document_id="doc_real",
        category=FactCategory.WAITING_PERIOD,
        proposition="Sample proposition",
        evidence_references=(ev_mismatch,),
        validation_status=FactValidationStatus.EVIDENCE_GROUNDED,
    )
    report_mis = validate_domain_bundle([doc], [fact_mismatch])
    assert any("mismatched document" in e.message.lower() for e in report_mis.errors)


def test_unresolved_cross_reference_retains_review():
    """Test 8: Conditional rider referencing a schedule retains NEEDS_REVIEW status."""
    text = (
        "Pre-Existing Diseases: Code - Excl01\n"
        "Expenses shall be excluded until 36 months (Unless specified otherwise in the Policy Schedule)."
    )
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_textbox(pymupdf.Rect(50, 50, 500, 300), text)
    data = doc.tobytes()
    doc.close()

    pol = prepare_policy(data, "schedule_ref.pdf")
    facts = extract_candidate_facts(pol)

    assert len(facts) >= 1
    f = facts[0]
    assert f.validation_status == FactValidationStatus.NEEDS_REVIEW
    assert any("conditional" in r.lower() for r in f.review_reasons)


def test_mismatched_normalized_value_triggers_warning():
    """Test 9: A fact whose structured value number does not appear in supporting quotation triggers a warning."""
    doc = SourceDocument(
        document_id="doc_val",
        filename="val.pdf",
        content_hash="h_val",
        page_count=5,
        size_bytes=1000,
    )
    ev = EvidenceReference(
        evidence_id="ev_val",
        document_id="doc_val",
        page_number=1,
        exact_text="Pre-existing disease waiting period of 36 months applies.",
        validation_status=FactValidationStatus.EVIDENCE_GROUNDED,
    )
    # Incorrect normalized value: 12 months instead of 36 months
    fact = PolicyFact(
        fact_id="f_bad_val",
        document_id="doc_val",
        category=FactCategory.WAITING_PERIOD,
        proposition="Pre-existing disease waiting period of 12 months.",
        evidence_references=(ev,),
        structured_value=DurationValue(amount=12, unit=DurationUnit.MONTHS, raw_text="12 months"),
        validation_status=FactValidationStatus.EVIDENCE_GROUNDED,
    )

    report = validate_domain_bundle([doc], [fact], page_texts={("doc_val", 1): ev.exact_text})
    val_warnings = [w for w in report.warnings if "structured value number (12)" in w.message.lower()]
    assert len(val_warnings) >= 1


def test_missing_expected_fact_penalized_in_evaluation_metrics():
    """Test 10: Missing expected facts in evaluation are explicitly penalized in recall, category, and value accuracy."""
    dummy_gold = [
        {
            "id": "gold_present",
            "document_file": "pdfs/ReAssure 2.0 - Policy Wording.pdf",
            "page_number": 10,
            "quote": "30-day waiting period",
            "category": "waiting_period",
            "expected_value": {"type": "duration", "amount": 30, "unit": "days"},
            "expected_status": "evidence_grounded",
        },
        {
            "id": "gold_missing_unextracted",
            "document_file": "pdfs/ReAssure 2.0 - Policy Wording.pdf",
            "page_number": 10,
            "quote": "Non-existent fictional clause that extractor will never find",
            "category": "limit_or_sublimit",
            "expected_value": {"type": "monetary", "amount": 50000.0, "currency": "INR"},
            "expected_status": "evidence_grounded",
        },
    ]

    results = evaluate_policy_facts(dummy_gold)
    m = results["metrics"]
    # 1 present, 1 missing -> 50% recall, 50% category match, 50% value match
    assert m["extraction_recall"]["numerator"] == 1
    assert m["extraction_recall"]["denominator"] == 2
    assert m["extraction_recall"]["percentage"] == 50.0

    assert m["category_match_accuracy"]["numerator"] == 1
    assert m["category_match_accuracy"]["denominator"] == 2
    assert m["category_match_accuracy"]["percentage"] == 50.0

    assert m["value_match_accuracy"]["numerator"] == 1
    assert m["value_match_accuracy"]["denominator"] == 2
    assert m["value_match_accuracy"]["percentage"] == 50.0

    missing_detail = next(d for d in results["details"] if d["id"] == "gold_missing_unextracted")
    assert "MISS" in missing_detail["status"]
    assert missing_detail["failure_reason"] is not None


def test_offline_evaluation_harness_execution():
    """Verify the offline evaluation harness computes benchmark metrics without error."""
    gold_facts = load_gold_facts(DEFAULT_GOLD_PATH)
    results = evaluate_policy_facts(gold_facts, verbose=False)

    assert results["total_gold_facts"] >= 15
    m = results["metrics"]
    assert m["citation_grounding"]["percentage"] >= 90.0
    assert m["extraction_recall"]["percentage"] >= 85.0
    assert m["category_match_accuracy"]["percentage"] >= 85.0
    assert m["value_match_accuracy"]["percentage"] >= 95.0
    assert m["review_alignment_rate"]["percentage"] >= 90.0
    assert "waiting_period" in results["per_category"]
    assert "exclusion" in results["per_category"]
