"""Tests for the deterministic domain validation layer and evidence invariants."""
from __future__ import annotations

import pytest

from backend.domain.enums import (
    DocumentType,
    DurationUnit,
    FactCategory,
    FactValidationStatus,
    RelationshipType,
)
from backend.domain.models import (
    DurationValue,
    EvidenceReference,
    FactRelationship,
    PolicyFact,
    SourceDocument,
)
from backend.domain.validation import (
    validate_domain_bundle,
    validate_evidence,
    validate_fact,
    validate_relationship,
)

SAMPLE_DOC = SourceDocument(
    document_id="doc_test_01",
    filename="Sample_Policy.pdf",
    content_hash="hash_01",
    document_type=DocumentType.POLICY_WORDING,
    page_count=10,
    size_bytes=50000,
    extracted_characters=20000,
    table_review_pages=(4,),
    text_poor_pages=(9,),
)

SAMPLE_PAGE_TEXT = (
    "SECTION 2: EXCLUSIONS\n"
    "Pre-existing diseases (PED) are excluded for 36 months of continuous coverage.\n"
    "Treatment for alcoholism is excluded."
)


def test_evidence_validation_valid():
    ev = EvidenceReference(
        evidence_id="ev_01",
        document_id=SAMPLE_DOC.document_id,
        page_number=2,
        exact_text="Pre-existing diseases (PED) are excluded for 36 months",
    )
    issues = validate_evidence(ev, SAMPLE_DOC, SAMPLE_PAGE_TEXT)
    errors = [i for i in issues if i.severity == "ERROR"]
    assert not errors


def test_evidence_validation_out_of_bounds_page():
    ev = EvidenceReference(
        evidence_id="ev_oob",
        document_id=SAMPLE_DOC.document_id,
        page_number=99,  # Document only has 10 pages
        exact_text="Some text",
    )
    issues = validate_evidence(ev, SAMPLE_DOC)
    errors = [i for i in issues if i.severity == "ERROR"]
    assert len(errors) == 1
    assert "out of bounds" in errors[0].message


def test_evidence_validation_mismatched_document_id():
    ev = EvidenceReference(
        evidence_id="ev_mismatch",
        document_id="other_doc_id",
        page_number=2,
        exact_text="Some text",
    )
    issues = validate_evidence(ev, SAMPLE_DOC)
    errors = [i for i in issues if i.severity == "ERROR"]
    assert len(errors) == 1
    assert "does not match target document" in errors[0].message


def test_evidence_validation_quote_not_found_on_page():
    ev = EvidenceReference(
        evidence_id="ev_not_found",
        document_id=SAMPLE_DOC.document_id,
        page_number=2,
        exact_text="This sentence does not exist anywhere in the policy text at all.",
    )
    issues = validate_evidence(ev, SAMPLE_DOC, SAMPLE_PAGE_TEXT)
    errors = [i for i in issues if i.severity == "ERROR"]
    assert len(errors) == 1
    assert "was not found on page" in errors[0].message


def test_fact_validation_verified_requires_evidence():
    fact = PolicyFact(
        fact_id="fact_no_ev",
        document_id=SAMPLE_DOC.document_id,
        category=FactCategory.WAITING_PERIOD,
        proposition="Waiting period is 36 months.",
        evidence_references=(),
        validation_status=FactValidationStatus.EVIDENCE_VERIFIED,
    )
    issues = validate_fact(fact, {SAMPLE_DOC.document_id: SAMPLE_DOC})
    errors = [i for i in issues if i.severity == "ERROR"]
    assert len(errors) >= 1
    assert any("lacks supporting evidence" in e.message for e in errors)


def test_fact_validation_cross_document_evidence_mixing_rejected():
    ev_wrong_doc = EvidenceReference(
        evidence_id="ev_wrong",
        document_id="doc_DIFFERENT",
        page_number=1,
        exact_text="Some text",
    )
    fact = PolicyFact(
        fact_id="fact_cross_doc",
        document_id=SAMPLE_DOC.document_id,
        category=FactCategory.EXCLUSION,
        proposition="Some proposition",
        evidence_references=(ev_wrong_doc,),
        validation_status=FactValidationStatus.CANDIDATE,
    )
    issues = validate_fact(fact, {SAMPLE_DOC.document_id: SAMPLE_DOC})
    errors = [i for i in issues if i.severity == "ERROR"]
    assert len(errors) >= 1
    assert any("contains evidence from mismatched document" in e.message for e in errors)


def test_relationship_validation_missing_endpoints():
    fact_map = {}
    rel = FactRelationship(
        relationship_id="rel_bad",
        source_fact_id="fact_nonexistent_1",
        relationship_type=RelationshipType.EXCEPTION_TO,
        target_fact_id="fact_nonexistent_2",
    )
    issues = validate_relationship(rel, fact_map)
    errors = [i for i in issues if i.severity == "ERROR"]
    assert len(errors) == 2
    assert any("source_fact_id" in e.message for e in errors)
    assert any("target_fact_id" in e.message for e in errors)


def test_relationship_validation_self_referential_rejected():
    fact = PolicyFact(
        fact_id="fact_1",
        document_id=SAMPLE_DOC.document_id,
        category=FactCategory.BENEFIT,
        proposition="Hospitalization is covered.",
    )
    rel = FactRelationship(
        relationship_id="rel_self",
        source_fact_id=fact.fact_id,
        relationship_type=RelationshipType.RELATED_TO,
        target_fact_id=fact.fact_id,  # Self reference
    )
    issues = validate_relationship(rel, {fact.fact_id: fact})
    errors = [i for i in issues if i.severity == "ERROR"]
    assert len(errors) >= 1
    assert any("Self-referential" in e.message for e in errors)


def test_relationship_supersedes_requires_evidence():
    fact1 = PolicyFact(
        fact_id="fact_old",
        document_id=SAMPLE_DOC.document_id,
        category=FactCategory.WAITING_PERIOD,
        proposition="Waiting period is 48 months in older endorsement.",
    )
    fact2 = PolicyFact(
        fact_id="fact_new",
        document_id=SAMPLE_DOC.document_id,
        category=FactCategory.WAITING_PERIOD,
        proposition="Waiting period is 36 months in new policy wording.",
    )
    # Verified SUPERSEDES without evidence IDs must fail
    rel_unsupported = FactRelationship(
        relationship_id="rel_sup_unsupported",
        source_fact_id=fact2.fact_id,
        relationship_type=RelationshipType.SUPERSEDES,
        target_fact_id=fact1.fact_id,
        evidence_ids=(),
        validation_status=FactValidationStatus.EVIDENCE_VERIFIED,
    )
    issues = validate_relationship(rel_unsupported, {fact1.fact_id: fact1, fact2.fact_id: fact2})
    errors = [i for i in issues if i.severity == "ERROR"]
    assert len(errors) >= 1
    assert any("SUPERSEDES relationship cannot be EVIDENCE_VERIFIED" in e.message for e in errors)


def test_validate_domain_bundle_detects_duplicates():
    doc1 = SAMPLE_DOC
    doc2 = SourceDocument(
        document_id=SAMPLE_DOC.document_id,  # Duplicate ID
        filename="Other.pdf",
        content_hash="hash_02",
        page_count=5,
        size_bytes=1000,
    )
    fact = PolicyFact(
        fact_id="fact_1",
        document_id=SAMPLE_DOC.document_id,
        category=FactCategory.BENEFIT,
        proposition="Valid proposition",
        validation_status=FactValidationStatus.CANDIDATE,
    )
    report = validate_domain_bundle(
        documents=[doc1, doc2],
        facts=[fact],
    )
    assert not report.is_valid
    assert any("Duplicate document_id" in e.message for e in report.errors)
