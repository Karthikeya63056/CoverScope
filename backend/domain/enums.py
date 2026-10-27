"""Domain enumerations for insurance policy intelligence."""
from __future__ import annotations

from enum import Enum


class DocumentType(str, Enum):
    """Categorization of insurance source documents."""

    POLICY_WORDING = "policy_wording"
    CUSTOMER_INFORMATION_SHEET = "customer_information_sheet"
    POLICY_SCHEDULE = "policy_schedule"
    BROCHURE = "brochure"
    ENDORSEMENT = "endorsement"
    UNKNOWN = "unknown"


class FactCategory(str, Enum):
    """Controlled taxonomy of insurance policy facts and clause types."""

    DEFINITION = "definition"
    BENEFIT = "benefit"
    EXCLUSION = "exclusion"
    WAITING_PERIOD = "waiting_period"
    COVERAGE_CONDITION = "coverage_condition"
    LIMIT_OR_SUBLIMIT = "limit_or_sublimit"
    DEDUCTIBLE_OR_COPAY = "deductible_or_copay"
    ELIGIBILITY_CONDITION = "eligibility_condition"
    EXCEPTION = "exception"
    RENEWAL_CONDITION = "renewal_condition"
    CLAIM_PROCEDURE = "claim_procedure"
    DISCLOSURE_REQUIREMENT = "disclosure_requirement"
    OTHER = "other"
    UNRESOLVED_CANDIDATE = "unresolved_candidate"


class FactValidationStatus(str, Enum):
    """Lifecycle and verification state of an extracted policy fact or relationship.

    Distinguishes structural validity, evidence grounding, and semantic confirmation:
    - CANDIDATE: Extracted or proposed fact conforming to schema.
    - EVIDENCE_GROUNDED: Quotation verified to exist verbatim on the cited source page.
    - EVIDENCE_VERIFIED: Alias for EVIDENCE_GROUNDED for backwards compatibility.
    - SEMANTICALLY_CONFIRMED: Confirmed against expert-reviewed ground truth.
    - NEEDS_REVIEW: Ambiguity, conditionality, conflict, or extraction limitation present.
    - REJECTED: Fails evidence verification, is contradicted, or invalid.
    """

    CANDIDATE = "candidate"
    EVIDENCE_GROUNDED = "evidence_grounded"
    EVIDENCE_VERIFIED = "evidence_verified"
    SEMANTICALLY_CONFIRMED = "semantically_confirmed"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class RelationshipType(str, Enum):
    """Semantic connection between two policy facts or clauses."""

    QUALIFIES = "qualifies"
    APPLIES_TO = "applies_to"
    EXCEPTION_TO = "exception_to"
    DEFINED_BY = "defined_by"
    LIMITED_BY = "limited_by"
    CONDITIONAL_ON = "conditional_on"
    SUPERSEDES = "supersedes"
    RELATED_TO = "related_to"


class ExtractionMethod(str, Enum):
    """Method used to extract or construct a policy fact."""

    HEURISTIC = "heuristic"
    LLM_EXTRACTED = "llm_extracted"
    MANUAL_CURATED = "manual_curated"
    UNKNOWN = "unknown"


class DurationUnit(str, Enum):
    """Supported time units for waiting periods and policy durations."""

    DAYS = "days"
    MONTHS = "months"
    YEARS = "years"


class ScenarioType(str, Enum):
    """Categorization of deterministic insurance analysis scenarios."""

    PRE_EXISTING_CONDITION = "pre_existing_condition"
    INITIAL_WAITING_PERIOD = "initial_waiting_period"
    CONDITIONAL_EXCLUSION = "conditional_exclusion"
    ENTRY_AGE_COPAYMENT = "entry_age_copayment"
    UNSUPPORTED = "unsupported"


class ScenarioVerdict(str, Enum):
    """Explicit, safe result states for deterministic scenario evaluation."""

    WAITING_PERIOD_ACTIVE = "waiting_period_active"
    WAITING_PERIOD_SATISFIED = "waiting_period_satisfied"
    CONDITIONAL_REVIEW = "conditional_review"
    EXCLUSION_IDENTIFIED = "exclusion_identified"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNSUPPORTED_SCENARIO = "unsupported_scenario"


class ComparisonStatus(str, Enum):
    """Explicit comparison outcomes across two insurance policies."""

    COMPARABLE = "comparable"
    CONDITION_DEPENDENT = "condition_dependent"
    MISSING_FROM_DOCUMENTS = "missing_from_documents"
    NEEDS_REVIEW = "needs_review"
    NOT_APPLICABLE = "not_applicable"


class ComparisonDimensionKey(str, Enum):
    """Controlled identifiers for supported policy comparison dimensions."""

    SUM_INSURED = "sum_insured"
    PED_WAITING_PERIOD = "ped_waiting_period"
    INITIAL_WAITING_PERIOD = "initial_waiting_period"
    SPECIFIC_DISEASE_WAITING_PERIOD = "specific_disease_waiting_period"
    COPAYMENT = "copayment"
    OBESITY_EXCLUSION = "obesity_exclusion"
    ALCOHOLISM_EXCLUSION = "alcoholism_exclusion"


class ProtectionGapSeverity(str, Enum):
    """Severity classification for conservative protection gaps."""

    CAUTION = "caution"
    CONDITIONAL_GAP = "conditional_gap"
    UNVERIFIED_GAP = "unverified_gap"
    INFORMATIONAL = "informational"


class ScheduleFieldStatus(str, Enum):
    """Explicit verification lifecycle states for fields extracted from a Policy Schedule."""

    NOT_FOUND_IN_TEXT = "not_found_in_text"
    NOT_PRESENT_IN_DOCUMENT = "not_present_in_document"
    PRESENT_BUT_AMBIGUOUS = "present_but_ambiguous"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    EXTRACTED = "extracted"
    EVIDENCE_GROUNDED = "evidence_grounded"
    USER_CONFIRMED = "user_confirmed"
    APPLICABILITY_VERIFIED = "applicability_verified"
    VERIFIED = "verified"
    SEMANTICALLY_REVIEWED = "semantically_reviewed"
    RULE_OUTCOME_ESTABLISHED = "rule_outcome_established"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class DocumentAssociationStatus(str, Enum):
    """Association state between a Policy Schedule and a Policy Wording document."""

    UNASSOCIATED = "unassociated"
    SUGGESTED_MATCH = "suggested_match"
    USER_CONFIRMED = "user_confirmed"
    VERIFIED_COMPATIBILITY = "verified_compatibility"
    CONFLICT_DETECTED = "conflict_detected"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class DecisionIntegrityState(str, Enum):
    """Granular verification and evidentiary status of material insurance conclusions."""

    RIDER_DOCUMENTED = "rider_documented"
    RIDER_APPLICABILITY_VERIFIED = "rider_applicability_verified"
    WAITING_PERIOD_RULE_IDENTIFIED = "waiting_period_rule_identified"
    ELAPSED_DURATION_ESTABLISHED = "elapsed_duration_established"
    WAITING_PERIOD_CONDITION_SATISFIED = "waiting_period_condition_satisfied"
    CONDITIONAL_UNRESOLVED = "conditional_unresolved"
    EVIDENCE_INSUFFICIENT = "evidence_insufficient"
    CLAIM_ELIGIBILITY_UNDETERMINED = "claim_eligibility_undetermined"
    RULE_OUTCOME_ESTABLISHED = "rule_outcome_established"
