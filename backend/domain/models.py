"""Canonical domain models for insurance policies, source documents, evidence, and facts."""
from __future__ import annotations

from typing import Annotated, Any, Union

from pydantic import BaseModel, ConfigDict, Field

from backend.domain.enums import (
    DocumentType,
    DurationUnit,
    ExtractionMethod,
    FactCategory,
    FactValidationStatus,
    RelationshipType,
)


class PolicyIdentity(BaseModel):
    """Represents a logical insurance policy separately from any PDF document describing it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = Field(min_length=1, description="Unique, stable policy identifier")
    insurer_name: str | None = Field(default=None, description="Legal insurer entity if verified")
    product_name: str | None = Field(default=None, description="Commercial product name if verified")
    policy_type: str | None = Field(default=None, description="Category (e.g. comprehensive_health)")
    jurisdiction: str = Field(default="IN", description="ISO 3166-1 alpha-2 jurisdiction code")
    metadata_confidence: str = Field(default="unverified", description="'unverified', 'low', 'medium', 'high'")
    notes: str | None = Field(default=None, description="Ambiguity or provenance notes")


class SourceDocument(BaseModel):
    """Represents an uploaded or supplied source document (PDF) independently."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: str = Field(min_length=1, description="Stable document fingerprint or ID")
    policy_id: str | None = Field(default=None, description="Associated policy identity if established")
    filename: str = Field(min_length=1, description="Original source filename")
    content_hash: str = Field(min_length=1, description="SHA-256 hash of raw file bytes")
    document_type: DocumentType = Field(default=DocumentType.UNKNOWN)
    page_count: int = Field(ge=1, description="Total number of pages in the document")
    size_bytes: int = Field(ge=0, description="File size in bytes")
    extracted_characters: int = Field(ge=0, default=0)
    extraction_status: str = Field(default="extracted")
    extraction_warnings: tuple[str, ...] = Field(default=())
    table_review_pages: tuple[int, ...] = Field(default=())
    text_poor_pages: tuple[int, ...] = Field(default=())


class SourcePage(BaseModel):
    """A single page extracted from a source document."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    page_number: int = Field(ge=1, description="1-based page number")
    text: str = Field(description="Extracted verbatim text from this page")
    char_count: int = Field(ge=0)
    text_block_count: int = Field(ge=0, default=0)
    image_count: int = Field(ge=0, default=0)
    is_table_review: bool = Field(default=False)
    is_text_poor: bool = Field(default=False)


class EvidenceReference(BaseModel):
    """Evidence span grounding a policy fact in exact source document text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str = Field(min_length=1, description="Globally unique evidence identifier")
    document_id: str = Field(min_length=1, description="Source document identifier")
    page_number: int = Field(ge=1, description="1-based source page number")
    exact_text: str = Field(min_length=1, description="Verbatim quote or excerpt from the page")
    chunk_id: str | None = Field(default=None, description="Local chunk identifier (e.g. P1-C1)")
    char_offset_start: int | None = Field(default=None, ge=0)
    char_offset_end: int | None = Field(default=None, ge=0)
    quality_warning: str | None = Field(default=None)
    validation_status: FactValidationStatus = Field(default=FactValidationStatus.CANDIDATE)


class DurationValue(BaseModel):
    """Typed temporal duration for waiting periods or policy terms."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    amount: int = Field(ge=0, description="Numeric duration count")
    unit: DurationUnit = Field(description="Temporal unit (days, months, years)")
    raw_text: str | None = Field(default=None, description="Original textual phrasing")


class MonetaryLimit(BaseModel):
    """Typed monetary amount and scope for sums insured, sublimits, or caps."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    amount: float = Field(ge=0.0, description="Monetary value")
    currency: str = Field(default="INR", description="ISO 4217 currency code")
    scope: str = Field(default="lump_sum", description="Scope: 'lump_sum', 'per_day', 'per_eye', etc.")
    raw_text: str | None = Field(default=None, description="Original textual phrasing")


class PercentageValue(BaseModel):
    """Typed percentage value for copayments, deductibles, or bonuses."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    percentage: float = Field(ge=0.0, le=100.0, description="Percentage value between 0.0 and 100.0")
    scope: str | None = Field(default=None, description="Scope: 'copayment', 'cumulative_bonus', etc.")
    raw_text: str | None = Field(default=None, description="Original textual phrasing")


StructuredValue = Annotated[
    Union[DurationValue, MonetaryLimit, PercentageValue],
    Field(discriminator=None),
]


class PolicyFact(BaseModel):
    """Structured, evidence-grounded policy fact proposition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fact_id: str = Field(min_length=1, description="Unique fact identifier")
    policy_id: str | None = Field(default=None, description="Linked policy identity if known")
    document_id: str = Field(min_length=1, description="Source document identifier")
    category: FactCategory = Field(description="Taxonomy category")
    proposition: str = Field(min_length=1, description="Concise factual statement")
    evidence_references: tuple[EvidenceReference, ...] = Field(default=())
    clause_label: str | None = Field(default=None, description="Clause marker if grounded (e.g. Excl01)")
    conditions: tuple[str, ...] = Field(default=(), description="Conditions attached to this fact")
    exceptions: tuple[str, ...] = Field(default=(), description="Exceptions to this provision")
    structured_value: Union[DurationValue, MonetaryLimit, PercentageValue, None] = Field(default=None)
    extraction_method: ExtractionMethod = Field(default=ExtractionMethod.UNKNOWN)
    validation_status: FactValidationStatus = Field(default=FactValidationStatus.CANDIDATE)
    is_evidence_grounded: bool = Field(default=False, description="True if quote matches source page text")
    semantic_status: str = Field(default="unreviewed", description="'unreviewed', 'confirmed', 'ambiguous', 'disputed'")
    review_reasons: tuple[str, ...] = Field(default=(), description="Flags explaining why manual review is required")
    uncertainty_notes: tuple[str, ...] = Field(default=())


class FactRelationship(BaseModel):
    """Typed semantic link connecting two policy facts or clauses."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    relationship_id: str = Field(min_length=1, description="Unique relationship identifier")
    source_fact_id: str = Field(min_length=1, description="ID of the source fact")
    relationship_type: RelationshipType = Field(description="Semantic nature of the connection")
    target_fact_id: str = Field(min_length=1, description="ID of the target fact")
    evidence_ids: tuple[str, ...] = Field(default=(), description="Supporting evidence IDs if any")
    validation_status: FactValidationStatus = Field(default=FactValidationStatus.CANDIDATE)
    notes: str | None = Field(default=None, description="Relationship rationale or conflict details")
