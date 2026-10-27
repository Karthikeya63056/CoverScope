"""Canonical insurance policy domain foundation package."""
from __future__ import annotations

from backend.domain.adapter import (
    create_evidence_from_chunk,
    create_source_document,
    create_source_pages,
    extract_candidate_facts,
)
from backend.domain.comparison import (
    ComparisonAssumptions,
    DimensionComparison,
    PolicyComparisonEngine,
    PolicyComparisonResult,
    PolicyDimensionValue,
    ProtectionGap,
)
from backend.domain.enums import (
    ComparisonDimensionKey,
    ComparisonStatus,
    DecisionIntegrityState,
    DocumentAssociationStatus,
    DocumentType,
    DurationUnit,
    ExtractionMethod,
    FactCategory,
    FactValidationStatus,
    ProtectionGapSeverity,
    RelationshipType,
    ScenarioType,
    ScenarioVerdict,
    ScheduleFieldStatus,
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
    StructuredValue,
)
from backend.domain.scenario import (
    ScenarioEvaluator,
    ScenarioInput,
    ScenarioResult,
)
from backend.domain.schedule import (
    ExtractedScheduleField,
    InsuredMember,
    PolicySchedule,
    PolicyScheduleAssociator,
    PolicyScheduleExtractor,
    mask_policy_number,
)
from backend.domain.validation import (
    ValidationIssue,
    ValidationReport,
    validate_domain_bundle,
    validate_evidence,
    validate_fact,
    validate_relationship,
)

__all__ = [
    # Enums
    "DocumentType",
    "FactCategory",
    "FactValidationStatus",
    "RelationshipType",
    "ExtractionMethod",
    "DurationUnit",
    "ScenarioType",
    "ScenarioVerdict",
    "ComparisonStatus",
    "ComparisonDimensionKey",
    "DecisionIntegrityState",
    "ProtectionGapSeverity",
    "ScheduleFieldStatus",
    "DocumentAssociationStatus",
    # Models
    "PolicyIdentity",
    "SourceDocument",
    "SourcePage",
    "EvidenceReference",
    "DurationValue",
    "MonetaryLimit",
    "PercentageValue",
    "StructuredValue",
    "PolicyFact",
    "FactRelationship",
    "ScenarioInput",
    "ScenarioResult",
    "ScenarioEvaluator",
    "ComparisonAssumptions",
    "PolicyDimensionValue",
    "DimensionComparison",
    "ProtectionGap",
    "PolicyComparisonResult",
    "PolicyComparisonEngine",
    "InsuredMember",
    "ExtractedScheduleField",
    "PolicySchedule",
    "PolicyScheduleExtractor",
    "PolicyScheduleAssociator",
    "mask_policy_number",
    # Validation
    "ValidationIssue",
    "ValidationReport",
    "validate_evidence",
    "validate_fact",
    "validate_relationship",
    "validate_domain_bundle",
    # Adapters
    "create_source_document",
    "create_source_pages",
    "create_evidence_from_chunk",
    "extract_candidate_facts",
]
