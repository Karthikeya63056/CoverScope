"""Deterministic validation layer for policy domain entities, evidence, and relationships."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from backend.document_processing.normalization import normalize_for_match
from backend.domain.enums import (
    FactCategory,
    FactValidationStatus,
    RelationshipType,
)
from backend.domain.models import (
    EvidenceReference,
    FactRelationship,
    PolicyFact,
    SourceDocument,
)


@dataclass(frozen=True)
class ValidationIssue:
    """A single deterministic validation finding."""

    severity: str  # "ERROR" or "WARNING"
    entity_type: str  # "document", "evidence", "fact", "relationship"
    entity_id: str
    message: str
    field: str | None = None


@dataclass(frozen=True)
class ValidationReport:
    """Collection of validation issues and overall validity status."""

    is_valid: bool
    errors: tuple[ValidationIssue, ...]
    warnings: tuple[ValidationIssue, ...]

    @property
    def total_issues(self) -> int:
        return len(self.errors) + len(self.warnings)


def validate_evidence(
    evidence: EvidenceReference,
    document: SourceDocument,
    page_text: str | None = None,
) -> list[ValidationIssue]:
    """Validate that an evidence reference adheres to document bounds and exact text match."""
    issues: list[ValidationIssue] = []

    # Invariant 1: Document ID alignment
    if evidence.document_id != document.document_id:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                entity_type="evidence",
                entity_id=evidence.evidence_id,
                message=(
                    f"Evidence document_id {evidence.document_id!r} does not match "
                    f"target document {document.document_id!r}."
                ),
                field="document_id",
            )
        )

    # Invariant 2: Page bounds
    if evidence.page_number < 1 or evidence.page_number > document.page_count:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                entity_type="evidence",
                entity_id=evidence.evidence_id,
                message=(
                    f"Evidence page_number {evidence.page_number} is out of bounds for "
                    f"document {document.filename!r} (total pages: {document.page_count})."
                ),
                field="page_number",
            )
        )

    # Invariant 3: Heuristic quality warnings
    if evidence.page_number in document.table_review_pages:
        issues.append(
            ValidationIssue(
                severity="WARNING",
                entity_type="evidence",
                entity_id=evidence.evidence_id,
                message=(
                    f"Evidence cites page {evidence.page_number} which is flagged for table review."
                ),
                field="page_number",
            )
        )

    if evidence.page_number in document.text_poor_pages:
        issues.append(
            ValidationIssue(
                severity="WARNING",
                entity_type="evidence",
                entity_id=evidence.evidence_id,
                message=(
                    f"Evidence cites page {evidence.page_number} which contains low extractable text."
                ),
                field="page_number",
            )
        )

    # Invariant 4: Exact text quotation verification against source page text
    if page_text is not None and not issues:
        norm_quote = normalize_for_match(evidence.exact_text)
        norm_page = normalize_for_match(page_text)
        if len(norm_quote) < 1:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    entity_type="evidence",
                    entity_id=evidence.evidence_id,
                    message="Evidence quotation text is empty or blank.",
                    field="exact_text",
                )
            )
        elif norm_quote not in norm_page:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    entity_type="evidence",
                    entity_id=evidence.evidence_id,
                    message=(
                        f"Evidence quotation for {evidence.evidence_id} was not found on page "
                        f"{evidence.page_number} of document {document.filename!r}."
                    ),
                    field="exact_text",
                )
            )

    return issues


def validate_fact(
    fact: PolicyFact,
    documents: Mapping[str, SourceDocument],
    page_texts: Mapping[tuple[str, int], str] | None = None,
) -> list[ValidationIssue]:
    """Validate a policy fact, its supporting evidence references, and structured values."""
    issues: list[ValidationIssue] = []

    # Invariant 1: Document must exist
    document = documents.get(fact.document_id)
    if document is None:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                entity_type="fact",
                entity_id=fact.fact_id,
                message=f"Fact references unknown document_id {fact.document_id!r}.",
                field="document_id",
            )
        )
        return issues

    # Invariant 2: Grounding requirement for verified facts
    if fact.validation_status in (
        FactValidationStatus.EVIDENCE_VERIFIED,
        FactValidationStatus.EVIDENCE_GROUNDED,
        FactValidationStatus.SEMANTICALLY_CONFIRMED,
    ):
        if not fact.evidence_references:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    entity_type="fact",
                    entity_id=fact.fact_id,
                    message=(
                        f"Fact {fact.fact_id} has verification status {fact.validation_status.value} "
                        "but lacks supporting evidence references."
                    ),
                    field="evidence_references",
                )
            )

    # Invariant 3: Validate each evidence reference
    has_evidence_error = False
    for ev in fact.evidence_references:
        # Cross-document evidence mixing check
        if ev.document_id != fact.document_id:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    entity_type="fact",
                    entity_id=fact.fact_id,
                    message=(
                        f"Fact {fact.fact_id} (doc: {fact.document_id}) contains evidence "
                        f"from mismatched document {ev.document_id}."
                    ),
                    field="evidence_references",
                )
            )
            has_evidence_error = True
            continue

        raw_page_text = None
        if page_texts is not None:
            raw_page_text = page_texts.get((ev.document_id, ev.page_number))

        ev_issues = validate_evidence(ev, document, raw_page_text)
        for issue in ev_issues:
            issues.append(issue)
            if issue.severity == "ERROR":
                has_evidence_error = True

    if fact.validation_status in (
        FactValidationStatus.EVIDENCE_VERIFIED,
        FactValidationStatus.EVIDENCE_GROUNDED,
        FactValidationStatus.SEMANTICALLY_CONFIRMED,
    ) and has_evidence_error:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                entity_type="fact",
                entity_id=fact.fact_id,
                message=(
                    f"Fact {fact.fact_id} cannot have status {fact.validation_status.value} because one "
                    "or more of its supporting evidence references failed validation."
                ),
                field="validation_status",
            )
        )

    # Invariant 4: Candidate status for ungrounded propositions
    if not fact.evidence_references and fact.validation_status != FactValidationStatus.CANDIDATE:
        issues.append(
            ValidationIssue(
                severity="WARNING",
                entity_type="fact",
                entity_id=fact.fact_id,
                message=(
                    f"Fact {fact.fact_id} has no evidence references; status should be "
                    f"CANDIDATE rather than {fact.validation_status.value}."
                ),
                field="validation_status",
            )
        )

    # Invariant 5: Value consistency against quotation text
    if fact.structured_value is not None and fact.evidence_references:
        amt = getattr(fact.structured_value, "amount", None)
        pct = getattr(fact.structured_value, "percentage", None)
        num_str = str(int(amt)) if isinstance(amt, (int, float)) and amt == int(amt) else str(amt) if amt is not None else None
        if num_str is None and pct is not None:
            num_str = str(int(pct)) if pct == int(pct) else str(pct)

        if num_str is not None:
            quote_texts = " ".join(ev.exact_text for ev in fact.evidence_references)
            if num_str not in quote_texts:
                issues.append(
                    ValidationIssue(
                        severity="WARNING",
                        entity_type="fact",
                        entity_id=fact.fact_id,
                        message=(
                            f"Structured value number ({num_str}) does not appear in supporting "
                            "evidence quotation."
                        ),
                        field="structured_value",
                    )
                )

    # Invariant 6: Status invariants for conditions and exceptions
    if (fact.conditions or fact.exceptions) and fact.validation_status == FactValidationStatus.SEMANTICALLY_CONFIRMED:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                entity_type="fact",
                entity_id=fact.fact_id,
                message=(
                    f"Fact {fact.fact_id} has conditions or exceptions attached; it cannot be "
                    "marked SEMANTICALLY_CONFIRMED without verified condition resolution."
                ),
                field="validation_status",
            )
        )

    return issues


def validate_relationship(
    rel: FactRelationship,
    facts: Mapping[str, PolicyFact],
) -> list[ValidationIssue]:
    """Validate fact relationship endpoint existence, symmetry, and supersession provenance."""
    issues: list[ValidationIssue] = []

    # Invariant 1: Source and target endpoints must exist
    source_fact = facts.get(rel.source_fact_id)
    if source_fact is None:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                entity_type="relationship",
                entity_id=rel.relationship_id,
                message=f"Relationship source_fact_id {rel.source_fact_id!r} does not exist.",
                field="source_fact_id",
            )
        )

    target_fact = facts.get(rel.target_fact_id)
    if target_fact is None:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                entity_type="relationship",
                entity_id=rel.relationship_id,
                message=f"Relationship target_fact_id {rel.target_fact_id!r} does not exist.",
                field="target_fact_id",
            )
        )

    # Invariant 2: Non-reflexive
    if rel.source_fact_id == rel.target_fact_id:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                entity_type="relationship",
                entity_id=rel.relationship_id,
                message="Self-referential relationships are invalid.",
                field="target_fact_id",
            )
        )

    # Invariant 3: Cross-document relationship check
    if source_fact and target_fact and source_fact.document_id != target_fact.document_id:
        if not source_fact.policy_id or source_fact.policy_id != target_fact.policy_id:
            issues.append(
                ValidationIssue(
                    severity="WARNING",
                    entity_type="relationship",
                    entity_id=rel.relationship_id,
                    message=(
                        f"Relationship links facts across documents ({source_fact.document_id} and "
                        f"{target_fact.document_id}) without established common policy_id."
                    ),
                    field="policy_id",
                )
            )

    # Invariant 4: SUPERSEDES requires explicit evidence to be verified
    if rel.relationship_type == RelationshipType.SUPERSEDES:
        if rel.validation_status == FactValidationStatus.EVIDENCE_VERIFIED and not rel.evidence_ids:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    entity_type="relationship",
                    entity_id=rel.relationship_id,
                    message=(
                        "A SUPERSEDES relationship cannot be EVIDENCE_VERIFIED without "
                        "explicit supporting evidence references. Upload order or dates alone "
                        "never establish supersession."
                    ),
                    field="evidence_ids",
                )
            )

    return issues


def validate_domain_bundle(
    documents: Sequence[SourceDocument],
    facts: Sequence[PolicyFact],
    relationships: Sequence[FactRelationship] = (),
    page_texts: Mapping[tuple[str, int], str] | None = None,
) -> ValidationReport:
    """Validate a complete collection of documents, facts, and relationships deterministically."""
    docs_map = {doc.document_id: doc for doc in documents}
    facts_map = {fact.fact_id: fact for fact in facts}

    all_issues: list[ValidationIssue] = []

    # Check for duplicate document IDs
    doc_ids_seen: set[str] = set()
    for doc in documents:
        if doc.document_id in doc_ids_seen:
            all_issues.append(
                ValidationIssue(
                    severity="ERROR",
                    entity_type="document",
                    entity_id=doc.document_id,
                    message=f"Duplicate document_id {doc.document_id!r} detected.",
                    field="document_id",
                )
            )
        doc_ids_seen.add(doc.document_id)

    # Check for duplicate fact IDs
    fact_ids_seen: set[str] = set()
    for fact in facts:
        if fact.fact_id in fact_ids_seen:
            all_issues.append(
                ValidationIssue(
                    severity="ERROR",
                    entity_type="fact",
                    entity_id=fact.fact_id,
                    message=f"Duplicate fact_id {fact.fact_id!r} detected.",
                    field="fact_id",
                )
            )
        fact_ids_seen.add(fact.fact_id)

    # Validate facts
    for fact in facts:
        all_issues.extend(validate_fact(fact, docs_map, page_texts))

    # Detect conflicting waiting period facts within the same document
    waiting_periods_by_doc: dict[str, list[PolicyFact]] = {}
    for fact in facts:
        if fact.category == FactCategory.WAITING_PERIOD:
            waiting_periods_by_doc.setdefault(fact.document_id, []).append(fact)

    for doc_id, doc_facts in waiting_periods_by_doc.items():
        ped_unconditional = [
            f for f in doc_facts
            if "pre-existing" in f.proposition.lower() and not f.conditions
        ]
        durations = {
            getattr(f.structured_value, "amount", None)
            for f in ped_unconditional
            if f.structured_value is not None
        }
        if len(durations) > 1:
            all_issues.append(
                ValidationIssue(
                    severity="WARNING",
                    entity_type="fact",
                    entity_id=f"doc_{doc_id}",
                    message=(
                        f"Multiple unconditional pre-existing disease waiting periods with conflicting "
                        f"durations detected ({sorted(filter(None, durations))}) in document {doc_id}."
                    ),
                    field="structured_value",
                )
            )

        initial_unconditional = [
            f for f in doc_facts
            if "initial" in f.proposition.lower() and not f.conditions
        ]
        initial_durations = {
            getattr(f.structured_value, "amount", None)
            for f in initial_unconditional
            if f.structured_value is not None
        }
        if len(initial_durations) > 1:
            all_issues.append(
                ValidationIssue(
                    severity="WARNING",
                    entity_type="fact",
                    entity_id=f"doc_{doc_id}",
                    message=(
                        f"Multiple unconditional initial waiting periods with conflicting "
                        f"durations detected ({sorted(filter(None, initial_durations))}) in document {doc_id}."
                    ),
                    field="structured_value",
                )
            )

    # Detect duplicate candidate facts within the same document
    seen_candidate_signatures: set[tuple[str, int, FactCategory, str | None]] = set()
    for fact in facts:
        ev = fact.evidence_references[0] if fact.evidence_references else None
        page_num = ev.page_number if ev else 0
        sv_val = getattr(fact.structured_value, "amount", None) or getattr(fact.structured_value, "percentage", None)
        sig = (fact.document_id, page_num, fact.category, str(sv_val))
        if sig in seen_candidate_signatures:
            all_issues.append(
                ValidationIssue(
                    severity="WARNING",
                    entity_type="fact",
                    entity_id=fact.fact_id,
                    message=(
                        f"Duplicate candidate fact detected on page {page_num} for category "
                        f"{fact.category.value} with value {sv_val} in document {fact.document_id}."
                    ),
                    field="structured_value",
                )
            )
        else:
            seen_candidate_signatures.add(sig)

    # Validate relationships
    rel_ids_seen: set[str] = set()
    for rel in relationships:
        if rel.relationship_id in rel_ids_seen:
            all_issues.append(
                ValidationIssue(
                    severity="ERROR",
                    entity_type="relationship",
                    entity_id=rel.relationship_id,
                    message=f"Duplicate relationship_id {rel.relationship_id!r} detected.",
                    field="relationship_id",
                )
            )
        rel_ids_seen.add(rel.relationship_id)
        all_issues.extend(validate_relationship(rel, facts_map))

    errors = tuple(i for i in all_issues if i.severity == "ERROR")
    warnings = tuple(i for i in all_issues if i.severity == "WARNING")
    return ValidationReport(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
