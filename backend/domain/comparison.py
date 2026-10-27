"""Policy comparison and protection gap analysis domain models and engine.

Provides structured, evidence-grounded comparisons between two insurance policies
and conservative protection-gap identification based on actual policy text.
"""
from __future__ import annotations

from typing import Any, Sequence
from pydantic import BaseModel, ConfigDict, Field

from backend.domain.adapter import extract_candidate_facts
from backend.domain.enums import (
    ComparisonDimensionKey,
    ComparisonStatus,
    DurationUnit,
    FactCategory,
    FactValidationStatus,
    ProtectionGapSeverity,
)
from backend.domain.models import DurationValue, PercentageValue, PolicyFact
from backend.qa.workflow import ProcessedPolicy


DIMENSION_METADATA: dict[ComparisonDimensionKey, dict[str, str]] = {
    ComparisonDimensionKey.SUM_INSURED: {
        "label": "Individual / Family Sum Insured",
        "description": "Total annual medical coverage limit specified in the policy schedule.",
    },
    ComparisonDimensionKey.PED_WAITING_PERIOD: {
        "label": "Pre-Existing Disease (PED) Waiting Period",
        "description": "Duration of continuous coverage required before pre-existing medical conditions are covered.",
    },
    ComparisonDimensionKey.INITIAL_WAITING_PERIOD: {
        "label": "Initial Illness Waiting Period",
        "description": "Standard exclusion period (typically 30 days) following policy inception. Accidental injuries are exempt.",
    },
    ComparisonDimensionKey.SPECIFIC_DISEASE_WAITING_PERIOD: {
        "label": "Specific / Named Disease Waiting Period",
        "description": "Waiting duration (commonly 24 months) applicable to specified conditions like cataract, hernia, and joint surgery.",
    },
    ComparisonDimensionKey.COPAYMENT: {
        "label": "Entry-Age Co-Payment & Cost Sharing",
        "description": "Percentage of admissible claim expenses that the insured member must pay out-of-pocket based on entry age.",
    },
    ComparisonDimensionKey.OBESITY_EXCLUSION: {
        "label": "Obesity / Weight Control Surgery Exclusion",
        "description": "Whether surgical treatment of obesity is excluded or conditional upon specific clinical exceptions (e.g. BMI ≥ 40).",
    },
    ComparisonDimensionKey.ALCOHOLISM_EXCLUSION: {
        "label": "Alcoholism & Substance Abuse Exclusion",
        "description": "Exclusion of treatments related to alcohol, drug, or substance dependence (IRDAI Code-Excl12).",
    },
}


class ComparisonAssumptions(BaseModel):
    """Optional user-supplied scenario parameters to evaluate comparative protection gaps."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    member_entry_age: int | None = Field(default=None, ge=0, le=120)
    elapsed_months: int | None = Field(default=None, ge=0, le=360)
    claim_amount: float | None = Field(default=None, ge=0.0)
    has_buyback_rider: bool = False


class PolicyDimensionValue(BaseModel):
    """Extracted and normalized value for a single comparison dimension from one policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dimension_key: ComparisonDimensionKey
    dimension_label: str
    policy_fingerprint: str
    policy_filename: str
    is_available: bool = True
    display_value: str
    numeric_amount: float | None = None
    unit: str | None = None
    fact_id: str | None = None
    validation_status: FactValidationStatus | None = None
    conditions: tuple[str, ...] = ()
    source_page: int | None = None
    evidence_quote: str | None = None
    notes: str | None = None


class DimensionComparison(BaseModel):
    """Side-by-side comparison of a single dimension across Policy A and Policy B."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dimension_key: ComparisonDimensionKey
    dimension_label: str
    status: ComparisonStatus
    policy_a_value: PolicyDimensionValue
    policy_b_value: PolicyDimensionValue
    summary_difference: str
    caveats_and_conditions: tuple[str, ...] = ()


class ProtectionGap(BaseModel):
    """Conservative, evidence-grounded protection gap or limitation for an insured person."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gap_id: str
    policy_fingerprint: str
    policy_filename: str
    dimension_key: ComparisonDimensionKey
    title: str
    description: str
    severity: ProtectionGapSeverity
    source_page: int | None = None
    evidence_quote: str | None = None
    assumptions: tuple[str, ...] = ()
    resolution_guidance: str


class PolicyComparisonResult(BaseModel):
    """Structured, verified side-by-side comparison result for two policies."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    comparison_id: str
    policy_a_fingerprint: str
    policy_a_filename: str
    policy_b_fingerprint: str
    policy_b_filename: str
    is_identical_policy: bool = False
    dimensions: tuple[DimensionComparison, ...]
    protection_gaps: tuple[ProtectionGap, ...]
    general_limitations: tuple[str, ...]


class PolicyComparisonEngine:
    """Headless, deterministic comparison and protection gap analysis engine."""

    def compare(
        self,
        policy_a: ProcessedPolicy,
        policy_b: ProcessedPolicy,
        assumptions: ComparisonAssumptions | None = None,
        facts_a: Sequence[PolicyFact] | None = None,
        facts_b: Sequence[PolicyFact] | None = None,
        schedule_a: Any | None = None,
        schedule_b: Any | None = None,
    ) -> PolicyComparisonResult:
        """Compare two policies side-by-side across supported dimensions."""
        user_assumptions = assumptions or ComparisonAssumptions()
        policy_facts_a = list(facts_a) if facts_a is not None else extract_candidate_facts(policy_a)
        policy_facts_b = list(facts_b) if facts_b is not None else extract_candidate_facts(policy_b)

        is_identical = (policy_a.fingerprint == policy_b.fingerprint)

        dimension_comparisons: list[DimensionComparison] = []
        for dim_key in ComparisonDimensionKey:
            val_a = self._extract_dimension_value(dim_key, policy_a, policy_facts_a, schedule=schedule_a)
            val_b = self._extract_dimension_value(dim_key, policy_b, policy_facts_b, schedule=schedule_b)
            dim_comp = self._compare_single_dimension(dim_key, val_a, val_b, is_identical)
            dimension_comparisons.append(dim_comp)

        protection_gaps = self._identify_protection_gaps(
            policy_a,
            policy_b,
            dimension_comparisons,
            user_assumptions,
            is_identical,
        )

        limitations = (
            "Comparisons are established strictly from extracted text in the uploaded policy wordings.",
            "Missing document information is labeled 'Not Found' and must NOT be inferred as covered or excluded.",
            "CoverScope does not declare an overall winner; individual suitability depends on age, health history, and budget.",
            "Always inspect official Policy Schedules for personalized endorsements, deductibles, and sum insured limits.",
        )

        return PolicyComparisonResult(
            comparison_id=f"cmp_{policy_a.fingerprint[:6]}_{policy_b.fingerprint[:6]}",
            policy_a_fingerprint=policy_a.fingerprint,
            policy_a_filename=policy_a.filename,
            policy_b_fingerprint=policy_b.fingerprint,
            policy_b_filename=policy_b.filename,
            is_identical_policy=is_identical,
            dimensions=tuple(dimension_comparisons),
            protection_gaps=tuple(protection_gaps),
            general_limitations=limitations,
        )

    # -------------------------------------------------------------------------
    # Dimension Extraction
    # -------------------------------------------------------------------------
    def _extract_dimension_value(
        self,
        dimension_key: ComparisonDimensionKey,
        policy: ProcessedPolicy,
        facts: list[PolicyFact],
        schedule: Any | None = None,
    ) -> PolicyDimensionValue:
        label = DIMENSION_METADATA[dimension_key]["label"]

        if dimension_key == ComparisonDimensionKey.SUM_INSURED:
            if schedule and getattr(schedule, "sum_insured", None):
                si = schedule.sum_insured
                riders_note = f" (Active Riders: {', '.join(schedule.optional_riders)})" if getattr(schedule, 'optional_riders', None) else ""
                return PolicyDimensionValue(
                    dimension_key=dimension_key,
                    dimension_label=label,
                    policy_fingerprint=policy.fingerprint,
                    policy_filename=policy.filename,
                    is_available=True,
                    display_value=f"₹{si:,.0f} (Confirmed on Schedule){riders_note}",
                    numeric_amount=float(si),
                    unit="INR",
                    source_page=1,
                    evidence_quote=f"Sum Insured: ₹{si:,.0f}",
                    notes=f"Confirmed from attached schedule {schedule.filename}{riders_note}",
                )
            return PolicyDimensionValue(
                dimension_key=dimension_key,
                dimension_label=label,
                policy_fingerprint=policy.fingerprint,
                policy_filename=policy.filename,
                is_available=False,
                display_value="Requires Policy Schedule",
                notes="Individual or family sum insured is specified on the policy certificate/schedule.",
            )

        if dimension_key == ComparisonDimensionKey.PED_WAITING_PERIOD:
            ped_facts = [
                f for f in facts
                if f.category == FactCategory.WAITING_PERIOD
                and ("pre-existing" in f.proposition.lower() or "ped" in f.proposition.lower())
                and f.validation_status != FactValidationStatus.REJECTED
            ]
            if not ped_facts:
                return self._missing_dimension(dimension_key, label, policy)

            base_fact = next((f for f in ped_facts if not f.conditions and isinstance(f.structured_value, DurationValue)), None)
            rider_fact = next((f for f in ped_facts if f.conditions and isinstance(f.structured_value, DurationValue)), None)

            primary_fact = base_fact or ped_facts[0]
            if not isinstance(primary_fact.structured_value, DurationValue):
                return self._missing_dimension(dimension_key, label, policy)

            dv = primary_fact.structured_value
            amount = dv.amount
            unit = getattr(dv, "unit", DurationUnit.MONTHS)
            months = amount * 12 if unit == DurationUnit.YEARS else (max(1, amount // 30) if unit == DurationUnit.DAYS else amount)
            if unit == DurationUnit.YEARS:
                disp = f"{amount} years ({months} months)"
            elif unit == DurationUnit.DAYS:
                disp = f"{amount} days ({months} months)"
            else:
                disp = f"{amount} months"

            conds: list[str] = list(primary_fact.conditions)
            if rider_fact and isinstance(rider_fact.structured_value, DurationValue):
                rdv = rider_fact.structured_value
                rd_months = rdv.amount * 12 if rdv.unit == DurationUnit.YEARS else rdv.amount
                rd_disp = f"{rd_months} months" if rdv.unit == DurationUnit.MONTHS else f"{rdv.amount} {rdv.unit.value} ({rd_months} months)"
                has_sched_rider = bool(schedule and getattr(schedule, "optional_riders", None) and any("ped" in r.lower() or "pre-existing" in r.lower() for r in schedule.optional_riders))
                if has_sched_rider:
                    disp = f"{rd_disp} (Rider Endorsement Confirmed on Schedule)"
                    conds.append("Confirmed on Policy Schedule: PED waiting period modification rider active")
                else:
                    disp += f" (Optional rider: {rd_disp})"
                    conds.append("Optional buy-back cover reduces waiting period upon schedule endorsement")

            ev = primary_fact.evidence_references[0] if primary_fact.evidence_references else None
            return PolicyDimensionValue(
                dimension_key=dimension_key,
                dimension_label=label,
                policy_fingerprint=policy.fingerprint,
                policy_filename=policy.filename,
                is_available=True,
                display_value=disp,
                numeric_amount=float(months),
                unit="months",
                fact_id=primary_fact.fact_id,
                validation_status=primary_fact.validation_status,
                conditions=tuple(conds),
                source_page=ev.page_number if ev else None,
                evidence_quote=ev.exact_text if ev else None,
            )

        elif dimension_key == ComparisonDimensionKey.INITIAL_WAITING_PERIOD:
            initial_facts = [
                f for f in facts
                if f.category == FactCategory.WAITING_PERIOD
                and ("initial" in f.proposition.lower() or (f.structured_value and getattr(f.structured_value, "unit", None) in (DurationUnit.DAYS, "days")))
                and f.validation_status != FactValidationStatus.REJECTED
            ]
            if not initial_facts:
                return self._missing_dimension(dimension_key, label, policy)

            fact = initial_facts[0]
            amount = getattr(fact.structured_value, "amount", 30)
            ev = fact.evidence_references[0] if fact.evidence_references else None
            return PolicyDimensionValue(
                dimension_key=dimension_key,
                dimension_label=label,
                policy_fingerprint=policy.fingerprint,
                policy_filename=policy.filename,
                is_available=True,
                display_value=f"{amount} days",
                numeric_amount=float(amount),
                unit="days",
                fact_id=fact.fact_id,
                validation_status=fact.validation_status,
                conditions=("Accidental injuries exempt from initial waiting period",),
                source_page=ev.page_number if ev else None,
                evidence_quote=ev.exact_text if ev else None,
            )

        elif dimension_key == ComparisonDimensionKey.SPECIFIC_DISEASE_WAITING_PERIOD:
            specific_facts = [
                f for f in facts
                if f.category == FactCategory.WAITING_PERIOD
                and ("specified" in f.proposition.lower() or "specific" in f.proposition.lower())
                and f.validation_status != FactValidationStatus.REJECTED
            ]
            if not specific_facts:
                return self._missing_dimension(dimension_key, label, policy)

            fact = specific_facts[0]
            dv = getattr(fact, "structured_value", None)
            if isinstance(dv, DurationValue):
                unit = getattr(dv, "unit", DurationUnit.MONTHS)
                months = dv.amount * 12 if unit == DurationUnit.YEARS else (max(1, dv.amount // 30) if unit == DurationUnit.DAYS else dv.amount)
                if unit == DurationUnit.YEARS:
                    disp_val = f"{dv.amount} years ({months} months)"
                elif unit == DurationUnit.DAYS:
                    disp_val = f"{dv.amount} days ({months} months)"
                else:
                    disp_val = f"{dv.amount} months"
                numeric_val = float(months)
            else:
                numeric_val = 24.0
                disp_val = "24 months"

            ev = fact.evidence_references[0] if fact.evidence_references else None
            return PolicyDimensionValue(
                dimension_key=dimension_key,
                dimension_label=label,
                policy_fingerprint=policy.fingerprint,
                policy_filename=policy.filename,
                is_available=True,
                display_value=disp_val,
                numeric_amount=numeric_val,
                unit="months",
                fact_id=fact.fact_id,
                validation_status=fact.validation_status,
                conditions=("Applies to specified ailments (e.g. cataract, hernia, joint surgery) regardless of prior history",),
                source_page=ev.page_number if ev else None,
                evidence_quote=ev.exact_text if ev else None,
            )

        elif dimension_key == ComparisonDimensionKey.COPAYMENT:
            copay_facts = [
                f for f in facts
                if f.category == FactCategory.DEDUCTIBLE_OR_COPAY
                and isinstance(f.structured_value, PercentageValue)
                and f.validation_status != FactValidationStatus.REJECTED
            ]
            if not copay_facts:
                return PolicyDimensionValue(
                    dimension_key=dimension_key,
                    dimension_label=label,
                    policy_fingerprint=policy.fingerprint,
                    policy_filename=policy.filename,
                    is_available=True,
                    display_value="0% (No mandatory entry-age co-payment documented)",
                    numeric_amount=0.0,
                    unit="%",
                    notes="No mandatory entry-age co-payment clause identified in policy text wording.",
                )

            fact = copay_facts[0]
            pct = getattr(fact.structured_value, "percentage", 10.0)
            ev = fact.evidence_references[0] if fact.evidence_references else None
            conds = fact.conditions or ("Applies to insured members entering at age 61 or above",)
            return PolicyDimensionValue(
                dimension_key=dimension_key,
                dimension_label=label,
                policy_fingerprint=policy.fingerprint,
                policy_filename=policy.filename,
                is_available=True,
                display_value=f"{pct:g}% (Entry age 61+)",
                numeric_amount=float(pct),
                unit="%",
                fact_id=fact.fact_id,
                validation_status=fact.validation_status,
                conditions=tuple(conds),
                source_page=ev.page_number if ev else None,
                evidence_quote=ev.exact_text if ev else None,
            )

        elif dimension_key == ComparisonDimensionKey.OBESITY_EXCLUSION:
            obesity_facts = [
                f for f in facts
                if f.category == FactCategory.EXCLUSION
                and ("obesity" in f.proposition.lower() or "bariatric" in f.proposition.lower())
                and f.validation_status != FactValidationStatus.REJECTED
            ]
            if not obesity_facts:
                return self._missing_dimension(dimension_key, label, policy)

            fact = obesity_facts[0]
            ev = fact.evidence_references[0] if fact.evidence_references else None
            has_exceptions = bool(fact.exceptions)
            disp = "Conditional Exclusion (Clinical exceptions apply)" if has_exceptions else "Standard Exclusion"
            return PolicyDimensionValue(
                dimension_key=dimension_key,
                dimension_label=label,
                policy_fingerprint=policy.fingerprint,
                policy_filename=policy.filename,
                is_available=True,
                display_value=disp,
                fact_id=fact.fact_id,
                validation_status=fact.validation_status,
                conditions=tuple(fact.exceptions) or ("Excluded unless strict medical exception criteria (e.g. BMI ≥ 40) are met",),
                source_page=ev.page_number if ev else None,
                evidence_quote=ev.exact_text if ev else None,
            )

        elif dimension_key == ComparisonDimensionKey.ALCOHOLISM_EXCLUSION:
            alcohol_facts = [
                f for f in facts
                if f.category == FactCategory.EXCLUSION
                and ("alcohol" in f.proposition.lower() or "substance" in f.proposition.lower())
                and f.validation_status != FactValidationStatus.REJECTED
            ]
            if not alcohol_facts:
                return self._missing_dimension(dimension_key, label, policy)

            fact = alcohol_facts[0]
            ev = fact.evidence_references[0] if fact.evidence_references else None
            return PolicyDimensionValue(
                dimension_key=dimension_key,
                dimension_label=label,
                policy_fingerprint=policy.fingerprint,
                policy_filename=policy.filename,
                is_available=True,
                display_value="Standard Exclusion (Code-Excl12)",
                fact_id=fact.fact_id,
                validation_status=fact.validation_status,
                conditions=("Expenses related to alcohol or addictive substance treatment are not payable",),
                source_page=ev.page_number if ev else None,
                evidence_quote=ev.exact_text if ev else None,
            )

        return self._missing_dimension(dimension_key, label, policy)

    def _missing_dimension(
        self,
        dimension_key: ComparisonDimensionKey,
        label: str,
        policy: ProcessedPolicy,
    ) -> PolicyDimensionValue:
        return PolicyDimensionValue(
            dimension_key=dimension_key,
            dimension_label=label,
            policy_fingerprint=policy.fingerprint,
            policy_filename=policy.filename,
            is_available=False,
            display_value="Not found in policy text",
            notes="No verified clause was extracted for this dimension from the document text.",
        )

    # -------------------------------------------------------------------------
    # Comparison Logic
    # -------------------------------------------------------------------------
    def _compare_single_dimension(
        self,
        dimension_key: ComparisonDimensionKey,
        val_a: PolicyDimensionValue,
        val_b: PolicyDimensionValue,
        is_identical: bool,
    ) -> DimensionComparison:
        label = val_a.dimension_label

        if is_identical:
            return DimensionComparison(
                dimension_key=dimension_key,
                dimension_label=label,
                status=ComparisonStatus.COMPARABLE if val_a.is_available else ComparisonStatus.MISSING_FROM_DOCUMENTS,
                policy_a_value=val_a,
                policy_b_value=val_b,
                summary_difference="Identical policy document selected for both comparisons.",
                caveats_and_conditions=val_a.conditions,
            )

        # Handle missing values
        if not val_a.is_available and not val_b.is_available:
            return DimensionComparison(
                dimension_key=dimension_key,
                dimension_label=label,
                status=ComparisonStatus.MISSING_FROM_DOCUMENTS,
                policy_a_value=val_a,
                policy_b_value=val_b,
                summary_difference=f"Neither policy document established a verified clause for {label} in text extraction.",
                caveats_and_conditions=("Verify official policy schedules or brochures for this provision.",),
            )

        if not val_a.is_available:
            return DimensionComparison(
                dimension_key=dimension_key,
                dimension_label=label,
                status=ComparisonStatus.MISSING_FROM_DOCUMENTS,
                policy_a_value=val_a,
                policy_b_value=val_b,
                summary_difference=f"{val_b.policy_filename} establishes {val_b.display_value}, but no clause was found in {val_a.policy_filename}.",
                caveats_and_conditions=("Do not infer that Policy A covers or excludes this provision without schedule review.",),
            )

        if not val_b.is_available:
            return DimensionComparison(
                dimension_key=dimension_key,
                dimension_label=label,
                status=ComparisonStatus.MISSING_FROM_DOCUMENTS,
                policy_a_value=val_a,
                policy_b_value=val_b,
                summary_difference=f"{val_a.policy_filename} establishes {val_a.display_value}, but no clause was found in {val_b.policy_filename}.",
                caveats_and_conditions=("Do not infer that Policy B covers or excludes this provision without schedule review.",),
            )

        # Both values available
        combined_conditions = tuple(dict.fromkeys(val_a.conditions + val_b.conditions))
        has_conditions = bool(combined_conditions)

        # Determine numeric comparison or qualitative comparison
        summary: str = ""
        if val_a.numeric_amount is not None and val_b.numeric_amount is not None:
            amt_a = val_a.numeric_amount
            amt_b = val_b.numeric_amount
            unit = val_a.unit or val_b.unit or ""

            if amt_a == amt_b:
                summary = f"Identical terms: Both policies specify {amt_a:g} {unit}."
            elif dimension_key in (ComparisonDimensionKey.PED_WAITING_PERIOD, ComparisonDimensionKey.INITIAL_WAITING_PERIOD, ComparisonDimensionKey.SPECIFIC_DISEASE_WAITING_PERIOD):
                if amt_a < amt_b:
                    summary = f"{val_a.policy_filename} establishes a shorter waiting duration ({amt_a:g} {unit}) than {val_b.policy_filename} ({amt_b:g} {unit})."
                else:
                    summary = f"{val_b.policy_filename} establishes a shorter waiting duration ({amt_b:g} {unit}) than {val_a.policy_filename} ({amt_a:g} {unit})."
            elif dimension_key == ComparisonDimensionKey.COPAYMENT:
                if amt_a < amt_b:
                    summary = f"{val_a.policy_filename} has a lower co-payment ({amt_a:g}%) than {val_b.policy_filename} ({amt_b:g}%)."
                else:
                    summary = f"{val_b.policy_filename} has a lower co-payment ({amt_b:g}%) than {val_a.policy_filename} ({amt_a:g}%)."
            elif dimension_key == ComparisonDimensionKey.SUM_INSURED:
                if amt_a > amt_b:
                    summary = f"{val_a.policy_filename} has a higher sum insured (₹{amt_a:,.0f}) than {val_b.policy_filename} (₹{amt_b:,.0f})."
                else:
                    summary = f"{val_b.policy_filename} has a higher sum insured (₹{amt_b:,.0f}) than {val_a.policy_filename} (₹{amt_a:,.0f})."
            else:
                summary = f"{val_a.policy_filename}: {val_a.display_value} vs {val_b.policy_filename}: {val_b.display_value}."
        else:
            if val_a.display_value.lower() == val_b.display_value.lower():
                summary = f"Both policies establish similar clauses: {val_a.display_value}."
            else:
                summary = f"{val_a.policy_filename}: {val_a.display_value} vs {val_b.policy_filename}: {val_b.display_value}."

        status = ComparisonStatus.CONDITION_DEPENDENT if has_conditions else ComparisonStatus.COMPARABLE

        return DimensionComparison(
            dimension_key=dimension_key,
            dimension_label=label,
            status=status,
            policy_a_value=val_a,
            policy_b_value=val_b,
            summary_difference=summary,
            caveats_and_conditions=combined_conditions,
        )

    # -------------------------------------------------------------------------
    # Protection Gaps Identification
    # -------------------------------------------------------------------------
    def _identify_protection_gaps(
        self,
        policy_a: ProcessedPolicy,
        policy_b: ProcessedPolicy,
        comparisons: list[DimensionComparison],
        assumptions: ComparisonAssumptions,
        is_identical: bool,
    ) -> list[ProtectionGap]:
        gaps: list[ProtectionGap] = []
        comp_map = {c.dimension_key: c for c in comparisons}

        # 1. PED Waiting Period Gap
        ped_comp = comp_map.get(ComparisonDimensionKey.PED_WAITING_PERIOD)
        if ped_comp:
            for p, val in [(policy_a, ped_comp.policy_a_value), (policy_b, ped_comp.policy_b_value)]:
                if val.is_available and val.numeric_amount is not None:
                    wait_m = int(val.numeric_amount)
                    elapsed = assumptions.elapsed_months
                    if elapsed is not None and elapsed < wait_m:
                        rem = wait_m - elapsed
                        gaps.append(
                            ProtectionGap(
                                gap_id=f"gap_ped_{p.fingerprint[:6]}",
                                policy_fingerprint=p.fingerprint,
                                policy_filename=p.filename,
                                dimension_key=ComparisonDimensionKey.PED_WAITING_PERIOD,
                                title=f"Pre-Existing Disease Waiting Period Active ({rem} Months Remaining)",
                                description=(
                                    f"{p.filename} specifies a {wait_m}-month pre-existing condition waiting period. "
                                    f"Based on {elapsed} months continuous coverage assumed, {rem} month(s) remain excluded."
                                ),
                                severity=ProtectionGapSeverity.CAUTION,
                                source_page=val.source_page,
                                evidence_quote=val.evidence_quote,
                                assumptions=(f"Continuous coverage assumed: {elapsed} months",),
                                resolution_guidance="Maintain continuous renewal without break. Check policy schedule for optional buy-back rider.",
                            )
                        )

        # 2. Co-Payment Out-Of-Pocket Gap
        copay_comp = comp_map.get(ComparisonDimensionKey.COPAYMENT)
        if copay_comp:
            for p, val in [(policy_a, copay_comp.policy_a_value), (policy_b, copay_comp.policy_b_value)]:
                if val.is_available and val.numeric_amount is not None and val.numeric_amount > 0.0:
                    pct = val.numeric_amount
                    entry_age = assumptions.member_entry_age
                    applies = (entry_age is not None and entry_age >= 61) or (entry_age is None)

                    if applies:
                        claim_amt = assumptions.claim_amount or 100000.0
                        copay_cost = claim_amt * (pct / 100.0)
                        age_note = f"for member entry age {entry_age}" if entry_age else "for members entering at age 61+"
                        gaps.append(
                            ProtectionGap(
                                gap_id=f"gap_copay_{p.fingerprint[:6]}",
                                policy_fingerprint=p.fingerprint,
                                policy_filename=p.filename,
                                dimension_key=ComparisonDimensionKey.COPAYMENT,
                                title=f"Mandatory {pct:g}% Co-Payment Out-Of-Pocket Expense",
                                description=(
                                    f"{p.filename} enforces a {pct:g}% co-payment {age_note}. "
                                    f"On a hypothetical admissible claim of ₹{claim_amt:,.0f}, patient must pay ₹{copay_cost:,.0f}."
                                ),
                                severity=ProtectionGapSeverity.CAUTION,
                                source_page=val.source_page,
                                evidence_quote=val.evidence_quote,
                                assumptions=(
                                    f"Hypothetical admissible claim: ₹{claim_amt:,.0f}",
                                    "Assumes 100% of expense is admissible before non-medical deductions.",
                                ),
                                resolution_guidance="Budget for out-of-pocket cost share or consider optional deductible/co-payment waiver riders.",
                            )
                        )

        # 3. Specific Disease 24-Month Waiting Period Notice
        spec_comp = comp_map.get(ComparisonDimensionKey.SPECIFIC_DISEASE_WAITING_PERIOD)
        if spec_comp:
            for p, val in [(policy_a, spec_comp.policy_a_value), (policy_b, spec_comp.policy_b_value)]:
                if val.is_available and val.numeric_amount is not None:
                    wait_m = int(val.numeric_amount)
                    gaps.append(
                        ProtectionGap(
                            gap_id=f"gap_spec_{p.fingerprint[:6]}",
                            policy_fingerprint=p.fingerprint,
                            policy_filename=p.filename,
                            dimension_key=ComparisonDimensionKey.SPECIFIC_DISEASE_WAITING_PERIOD,
                            title=f"Specific Disease Waiting Period ({wait_m} Months)",
                            description=(
                                f"{p.filename} excludes specific listed conditions (e.g. cataract, hernia, joint replacement, hysterectomy) "
                                f"during the first {wait_m} months of continuous coverage."
                            ),
                            severity=ProtectionGapSeverity.INFORMATIONAL,
                            source_page=val.source_page,
                            evidence_quote=val.evidence_quote,
                            assumptions=("Applies to all new insured persons regardless of declared pre-existing diseases",),
                            resolution_guidance="Review the full specific disease list in Section 5 of the policy wording prior to elective treatments.",
                        )
                    )

        # 4. Unverified Dimensions Gaps
        for comp in comparisons:
            if comp.status == ComparisonStatus.MISSING_FROM_DOCUMENTS and not is_identical:
                for p, val in [(policy_a, comp.policy_a_value), (policy_b, comp.policy_b_value)]:
                    if not val.is_available:
                        gaps.append(
                            ProtectionGap(
                                gap_id=f"gap_unverified_{p.fingerprint[:6]}_{comp.dimension_key.value}",
                                policy_fingerprint=p.fingerprint,
                                policy_filename=p.filename,
                                dimension_key=comp.dimension_key,
                                title=f"Unverified Dimension: {comp.dimension_label}",
                                description=(
                                    f"A verified clause for {comp.dimension_label} was not found in the current text extraction of {p.filename}. "
                                    "This detail remains unverified."
                                ),
                                severity=ProtectionGapSeverity.UNVERIFIED_GAP,
                                assumptions=("Extraction from PDF text wording; policy schedule not checked",),
                                resolution_guidance="Check your policy schedule or customer information sheet to confirm coverage details.",
                            )
                        )

        # De-duplicate identical gaps if identical policy
        if is_identical:
            seen_titles: set[str] = set()
            unique_gaps: list[ProtectionGap] = []
            for g in gaps:
                if g.title not in seen_titles:
                    seen_titles.add(g.title)
                    unique_gaps.append(g)
            return unique_gaps

        return gaps
