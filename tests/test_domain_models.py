"""Tests for canonical domain models, serialization, and immutability."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.domain.enums import (
    DocumentType,
    DurationUnit,
    ExtractionMethod,
    FactCategory,
    FactValidationStatus,
    RelationshipType,
)
from backend.domain.models import (
    DurationValue,
    EvidenceReference,
    FactRelationship,
    MonetaryLimit,
    PercentageValue,
    PolicyFact,
    PolicyIdentity,
    SourceDocument,
    SourcePage,
)


def test_policy_identity_creation_and_immutability():
    ident = PolicyIdentity(
        policy_id="pol_hdfc_optima_01",
        insurer_name="HDFC ERGO General Insurance Company Limited",
        product_name="Optima Secure",
        policy_type="comprehensive_health",
        jurisdiction="IN",
        metadata_confidence="high",
    )
    assert ident.policy_id == "pol_hdfc_optima_01"
    assert ident.insurer_name == "HDFC ERGO General Insurance Company Limited"
    assert ident.jurisdiction == "IN"

    # Frozen immutability check
    with pytest.raises(ValidationError):
        ident.product_name = "Different Product"  # type: ignore[misc]


def test_policy_identity_missing_optional_fields_is_allowed():
    ident = PolicyIdentity(policy_id="pol_unknown_01")
    assert ident.insurer_name is None
    assert ident.product_name is None
    assert ident.metadata_confidence == "unverified"
    assert ident.jurisdiction == "IN"


def test_source_document_bounds_and_serialization():
    doc = SourceDocument(
        document_id="doc_abc123",
        filename="Policy_Wording.pdf",
        content_hash="hash_abc123",
        document_type=DocumentType.POLICY_WORDING,
        page_count=35,
        size_bytes=1024000,
        extracted_characters=85000,
        table_review_pages=(12, 13),
        text_poor_pages=(1,),
    )
    assert doc.document_id == "doc_abc123"
    assert doc.page_count == 35

    # Roundtrip serialization
    data = doc.model_dump()
    restored = SourceDocument.model_validate(data)
    assert restored == doc
    assert restored.table_review_pages == (12, 13)

    # Invalid page count
    with pytest.raises(ValidationError):
        SourceDocument(
            document_id="doc_bad",
            filename="bad.pdf",
            content_hash="h",
            page_count=0,  # ge=1 violated
            size_bytes=100,
        )


def test_source_page_representation():
    page = SourcePage(
        page_number=1,
        text="Section 1: Coverage Terms",
        char_count=25,
        text_block_count=2,
        image_count=0,
    )
    assert page.page_number == 1
    assert page.char_count == 25
    assert not page.is_table_review


def test_evidence_reference_provenance_and_serialization():
    ev = EvidenceReference(
        evidence_id="ev_doc1_p1_c1",
        document_id="doc1",
        page_number=1,
        exact_text="Pre-existing diseases are excluded for 36 months.",
        chunk_id="P1-C1",
        validation_status=FactValidationStatus.EVIDENCE_VERIFIED,
    )
    assert ev.page_number == 1
    assert ev.chunk_id == "P1-C1"

    data = ev.model_dump()
    restored = EvidenceReference.model_validate(data)
    assert restored == ev


def test_structured_values_validation():
    # Valid duration
    dur = DurationValue(amount=36, unit=DurationUnit.MONTHS, raw_text="36 months")
    assert dur.amount == 36
    assert dur.unit == DurationUnit.MONTHS

    # Negative duration is rejected
    with pytest.raises(ValidationError):
        DurationValue(amount=-5, unit=DurationUnit.MONTHS)

    # Valid monetary limit
    limit = MonetaryLimit(amount=50000.0, currency="INR", scope="per_eye")
    assert limit.amount == 50000.0
    assert limit.scope == "per_eye"

    # Negative monetary limit is rejected
    with pytest.raises(ValidationError):
        MonetaryLimit(amount=-1000.0)

    # Valid percentage value
    pct = PercentageValue(percentage=20.0, scope="copayment")
    assert pct.percentage == 20.0

    # Percentage over 100 is rejected
    with pytest.raises(ValidationError):
        PercentageValue(percentage=150.0)

    # Percentage below 0 is rejected
    with pytest.raises(ValidationError):
        PercentageValue(percentage=-5.0)


def test_policy_fact_and_relationship_models():
    ev = EvidenceReference(
        evidence_id="ev_01",
        document_id="doc_a",
        page_number=10,
        exact_text="Maternity expenses are excluded.",
        validation_status=FactValidationStatus.EVIDENCE_VERIFIED,
    )
    fact1 = PolicyFact(
        fact_id="fact_01",
        document_id="doc_a",
        category=FactCategory.EXCLUSION,
        proposition="Maternity is excluded.",
        evidence_references=(ev,),
        validation_status=FactValidationStatus.EVIDENCE_VERIFIED,
    )
    fact2 = PolicyFact(
        fact_id="fact_02",
        document_id="doc_a",
        category=FactCategory.EXCEPTION,
        proposition="Maternity is covered under optional rider.",
        validation_status=FactValidationStatus.CANDIDATE,
    )

    rel = FactRelationship(
        relationship_id="rel_01",
        source_fact_id=fact2.fact_id,
        relationship_type=RelationshipType.EXCEPTION_TO,
        target_fact_id=fact1.fact_id,
        validation_status=FactValidationStatus.CANDIDATE,
    )
    assert rel.relationship_type == RelationshipType.EXCEPTION_TO
    assert rel.source_fact_id == "fact_02"
    assert rel.target_fact_id == "fact_01"

    # Verify serialization
    data = rel.model_dump()
    restored = FactRelationship.model_validate(data)
    assert restored == rel
