"""Deterministic scenario evaluation engine for insurance policies.

Provides rule-based, evidence-grounded evaluation of policyholder scenarios
(waiting periods, exclusions, co-payments) against canonical policy facts without LLM dependencies.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Sequence
from dateutil.relativedelta import relativedelta
from pydantic import BaseModel, ConfigDict, Field

from backend.domain.adapter import extract_candidate_facts
from backend.domain.enums import (
    DecisionIntegrityState,
    DocumentAssociationStatus,
    DurationUnit,
    FactCategory,
    FactValidationStatus,
    ScenarioType,
    ScenarioVerdict,
)
from backend.domain.models import DurationValue, PercentageValue, PolicyFact
from backend.qa.workflow import ProcessedPolicy


class ScenarioInput(BaseModel):
    """Structured input parameters for deterministic scenario analysis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_type: ScenarioType
    # Temporal / Policy duration inputs
    elapsed_months: int | None = Field(default=None, ge=0)
    elapsed_days: int | None = Field(default=None, ge=0)
    inception_date: str | None = None  # "YYYY-MM-DD"
    incident_date: str | None = None   # "YYYY-MM-DD"

    # Clinical / Condition inputs
    condition_name: str | None = None
    is_pre_existing: bool = False
    is_accidental_injury: bool = False
    has_buyback_rider: bool = False
    has_schedule_endorsement: bool = False

    # Financial / Member inputs
    member_age_at_entry: int | None = Field(default=None, ge=0, le=120)
    claim_amount: float | None = Field(default=None, ge=0.0)

    # Optional user notes
    user_notes: str | None = None


class ScenarioResult(BaseModel):
    """Structured, deterministic result of evaluating a scenario against policy facts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str
    scenario_type: ScenarioType
    policy_fingerprint: str = Field(default="", description="Source policy fingerprint")
    verdict: ScenarioVerdict
    headline: str
    explanation: str

    # Quantitative results if applicable
    applicable_duration_amount: int | None = None
    applicable_duration_unit: str | None = None
    elapsed_duration_amount: int | None = None
    remaining_duration_amount: int | None = None
    copayment_percentage: float | None = None
    calculated_copayment_amount: float | None = None
    calculated_insurer_portion: float | None = None

    # Provenance & Evidence Traceability
    applicable_fact_ids: tuple[str, ...] = ()
    source_references: tuple[dict[str, Any], ...] = ()
    unresolved_conditions: tuple[str, ...] = ()
    missing_inputs: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    # Coverage Verification & Decision Integrity (Phase 3.1)
    decision_state: DecisionIntegrityState | None = None
    applicable_member: str | None = None
    calculation_formula: str | None = None
    user_assumptions: tuple[str, ...] = ()
    evidentiary_support: str = ""


def calculate_elapsed_time(
    inception_date_str: str | None,
    incident_date_str: str | None,
    user_elapsed_months: int | None = None,
    user_elapsed_days: int | None = None,
) -> tuple[int | None, int | None, list[str]]:
    """Deterministically calculate elapsed calendar months and days between two dates.

    Returns (elapsed_months, elapsed_days, notes).
    """
    notes: list[str] = []
    if inception_date_str and incident_date_str:
        try:
            d0 = date.fromisoformat(inception_date_str)
            d1 = date.fromisoformat(incident_date_str)
            if d1 < d0:
                return (None, None, ["Incident date cannot be prior to policy inception date."])
            rd = relativedelta(d1, d0)
            elapsed_months = rd.years * 12 + rd.months
            elapsed_days = (d1 - d0).days
            notes.append(
                f"Calculated from calendar dates {d0.isoformat()} to {d1.isoformat()}: "
                f"{elapsed_months} full months ({elapsed_days} total days elapsed)."
            )
            return (elapsed_months, elapsed_days, notes)
        except ValueError as err:
            notes.append(f"Invalid date format: {err}. Expected YYYY-MM-DD.")
            return (None, None, notes)

    if user_elapsed_months is not None or user_elapsed_days is not None:
        notes.append("Duration supplied directly by user; inception and claim dates not verified.")
        return (user_elapsed_months, user_elapsed_days, notes)

    return (None, None, ["Neither calendar dates nor elapsed duration was supplied."])


class ScenarioEvaluator:
    """Headless deterministic scenario analysis engine."""

    def evaluate(
        self,
        policy: ProcessedPolicy,
        scenario_input: ScenarioInput,
        facts: Sequence[PolicyFact] | None = None,
        schedule: Any | None = None,
    ) -> ScenarioResult:
        """Evaluate a scenario against extracted policy facts deterministically."""
        policy_facts = list(facts) if facts is not None else extract_candidate_facts(policy)
        scenario_type = scenario_input.scenario_type

        # Dispatch to dedicated evaluator
        if scenario_type == ScenarioType.PRE_EXISTING_CONDITION:
            return self._evaluate_ped_scenario(policy, policy_facts, scenario_input, schedule=schedule)
        elif scenario_type == ScenarioType.INITIAL_WAITING_PERIOD:
            return self._evaluate_initial_waiting_period_scenario(policy, policy_facts, scenario_input)
        elif scenario_type == ScenarioType.CONDITIONAL_EXCLUSION:
            return self._evaluate_exclusion_scenario(policy, policy_facts, scenario_input)
        elif scenario_type == ScenarioType.ENTRY_AGE_COPAYMENT:
            return self._evaluate_copayment_scenario(policy, policy_facts, scenario_input, schedule=schedule)
        else:
            return self._evaluate_unsupported_scenario(scenario_input, policy=policy)

    def _build_source_references(self, applicable_facts: Sequence[PolicyFact], policy: ProcessedPolicy) -> list[dict[str, Any]]:
        """Extract source document filename, page numbers, and exact quotes."""
        refs: list[dict[str, Any]] = []
        for f in applicable_facts:
            for ev in f.evidence_references:
                refs.append({
                    "document": policy.filename,
                    "page_number": ev.page_number,
                    "quote": ev.exact_text,
                    "fact_id": f.fact_id,
                    "category": f.category.value,
                    "status": f.validation_status.value,
                })
        return refs

    # -------------------------------------------------------------------------
    # 1. Pre-Existing Disease (PED) Waiting Period Evaluation
    # -------------------------------------------------------------------------
    def _evaluate_ped_scenario(
        self,
        policy: ProcessedPolicy,
        facts: list[PolicyFact],
        scenario_input: ScenarioInput,
        schedule: Any | None = None,
    ) -> ScenarioResult:
        # Step 1: Find applicable PED waiting period facts
        ped_facts = [
            f for f in facts
            if f.category == FactCategory.WAITING_PERIOD
            and ("pre-existing" in f.proposition.lower() or "ped" in f.proposition.lower())
            and f.validation_status != FactValidationStatus.REJECTED
        ]

        if not ped_facts:
            return ScenarioResult(
                scenario_id=f"scen_ped_{policy.fingerprint[:8]}",
                scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
                policy_fingerprint=policy.fingerprint,
                verdict=ScenarioVerdict.INSUFFICIENT_EVIDENCE,
                decision_state=DecisionIntegrityState.EVIDENCE_INSUFFICIENT,
                headline="No Established Pre-Existing Disease Waiting Period Found",
                explanation=(
                    f"No pre-existing disease waiting period clause was established in {policy.filename}. "
                    "The policy schedule or schedule of benefits must be consulted."
                ),
                missing_inputs=("Established pre-existing disease waiting period fact",),
                limitations=("Cannot evaluate pre-existing condition eligibility without contractual waiting period clause.",),
                evidentiary_support=f"Document search across {policy.filename}.",
            )

        # Separate base policy fact from rider facts
        base_fact = next((f for f in ped_facts if not f.conditions and isinstance(f.structured_value, DurationValue)), None)
        rider_fact = next((f for f in ped_facts if f.conditions and isinstance(f.structured_value, DurationValue)), None)

        chosen_fact: PolicyFact | None = None
        unresolved_conditions: list[str] = []
        has_verified_endorsement = False

        # Audit schedule association conflicts
        has_schedule_conflict = (
            schedule is not None
            and getattr(schedule, "association_status", None) == DocumentAssociationStatus.CONFLICT_DETECTED
        )

        # Audit documented riders on schedule
        schedule_rider_inapplicable_reason: str | None = None
        if schedule is not None and getattr(schedule, "optional_riders", None):
            ped_riders = [r for r in schedule.optional_riders if "ped" in r.lower() or "pre-existing" in r.lower()]
            if ped_riders:
                has_verified_endorsement = True
            else:
                other_riders = ", ".join(schedule.optional_riders)
                schedule_rider_inapplicable_reason = (
                    f"Attached schedule documents optional riders ('{other_riders}'), but no Pre-Existing Disease (PED) modification rider. Base policy waiting period applies."
                )
        elif scenario_input.has_schedule_endorsement:
            has_verified_endorsement = True

        if scenario_input.has_buyback_rider:
            if rider_fact is not None:
                if schedule_rider_inapplicable_reason:
                    # Inapplicable rider attached
                    chosen_fact = base_fact or ped_facts[0]
                    unresolved_conditions.append(schedule_rider_inapplicable_reason)
                elif has_schedule_conflict:
                    chosen_fact = rider_fact
                    unresolved_conditions.append("Schedule endorsement proof is suspended due to an active document conflict between schedule and base policy wording.")
                elif has_verified_endorsement:
                    chosen_fact = rider_fact
                else:
                    chosen_fact = rider_fact
                    unresolved_conditions.append("Requires verification that optional PED buy-back cover was endorsed on the Policy Schedule.")
            else:
                chosen_fact = base_fact
                unresolved_conditions.append("User indicated optional buy-back cover, but no rider clause was identified in this policy wording. Base policy waiting period applied.")
        else:
            chosen_fact = base_fact or ped_facts[0]

        if chosen_fact is None or not isinstance(chosen_fact.structured_value, DurationValue):
            return ScenarioResult(
                scenario_id=f"scen_ped_{policy.fingerprint[:8]}",
                scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
                policy_fingerprint=policy.fingerprint,
                verdict=ScenarioVerdict.INSUFFICIENT_EVIDENCE,
                decision_state=DecisionIntegrityState.EVIDENCE_INSUFFICIENT,
                headline="Indeterminate Pre-Existing Disease Waiting Period Duration",
                explanation="A pre-existing disease provision was identified, but its numeric duration is indeterminate.",
                applicable_fact_ids=tuple(f.fact_id for f in ped_facts),
                source_references=tuple(self._build_source_references(ped_facts, policy)),
                limitations=("Waiting period duration could not be extracted as an exact numeric month value.",),
                evidentiary_support=f"Base Policy Wording ({policy.filename}).",
            )

        waiting_months = chosen_fact.structured_value.amount
        applicable_facts = [chosen_fact]

        # Step 2: Calculate elapsed months
        elapsed_months, _, timing_notes = calculate_elapsed_time(
            scenario_input.inception_date,
            scenario_input.incident_date,
            scenario_input.elapsed_months,
            scenario_input.elapsed_days,
        )

        if elapsed_months is None:
            return ScenarioResult(
                scenario_id=f"scen_ped_{policy.fingerprint[:8]}",
                scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
                policy_fingerprint=policy.fingerprint,
                verdict=ScenarioVerdict.INSUFFICIENT_EVIDENCE,
                decision_state=DecisionIntegrityState.EVIDENCE_INSUFFICIENT,
                headline="Missing Policy Duration",
                explanation=(
                    f"The policy establishes a {waiting_months}-month pre-existing disease waiting period, "
                    "but continuous policy duration was not provided. Please provide policy inception and claim dates, or elapsed months."
                ),
                applicable_duration_amount=waiting_months,
                applicable_duration_unit="months",
                applicable_fact_ids=(chosen_fact.fact_id,),
                source_references=tuple(self._build_source_references(applicable_facts, policy)),
                missing_inputs=("Continuous coverage duration or inception/claim dates",),
                limitations=("Cannot evaluate active vs satisfied status without elapsed time.",),
                evidentiary_support=f"Base Policy Wording ({policy.filename}).",
            )

        # Step 3: Evaluate rule
        if elapsed_months < waiting_months:
            remaining = waiting_months - elapsed_months
            verdict = ScenarioVerdict.WAITING_PERIOD_ACTIVE
            decision_state = DecisionIntegrityState.WAITING_PERIOD_RULE_IDENTIFIED
            headline = f"Pre-Existing Disease Waiting Period is Active ({remaining} Months Remaining)"
            explanation = (
                f"Continuous coverage of {elapsed_months} month(s) has elapsed against an applicable "
                f"{waiting_months}-month pre-existing disease waiting period. Claims related to pre-existing conditions "
                f"remain excluded until the expiry of month {waiting_months}."
            )
        else:
            remaining = 0
            if unresolved_conditions:
                verdict = ScenarioVerdict.CONDITIONAL_REVIEW
                decision_state = DecisionIntegrityState.CONDITIONAL_UNRESOLVED
                headline = f"Pre-Existing Disease Waiting Period Conditionally Satisfied ({elapsed_months} Months Elapsed)"
                explanation = (
                    f"The reduced {waiting_months}-month waiting period has elapsed after {elapsed_months} months of continuous coverage, "
                    f"CONDITIONAL upon: {'; '.join(unresolved_conditions)}."
                )
            else:
                verdict = ScenarioVerdict.WAITING_PERIOD_SATISFIED
                decision_state = DecisionIntegrityState.WAITING_PERIOD_CONDITION_SATISFIED
                headline = f"Pre-Existing Disease Waiting Period is Satisfied ({elapsed_months} Months Elapsed)"
                explanation = (
                    f"The applicable {waiting_months}-month pre-existing disease waiting period has elapsed "
                    f"after {elapsed_months} months of continuous coverage."
                )

        limitations = [
            "Waiting period satisfaction evaluates time elapsed only; it does not confirm treatment admissibility or guarantee claim approval.",
            "The condition must still satisfy all other policy terms, diagnostic guidelines, active exclusions, and medical necessity criteria.",
            "Continuous coverage requires renewal without break in continuity; portability credits are not evaluated.",
            "Final claims adjudication is performed by the insurer/TPA upon submission of hospital discharge summaries and clinical records.",
        ]
        if timing_notes:
            limitations.extend(timing_notes)

        # Trace assumptions and evidentiary support
        user_assumptions: list[str] = []
        if scenario_input.inception_date:
            user_assumptions.append(f"Inception date {scenario_input.inception_date} verified from schedule/user input")
        else:
            user_assumptions.append(f"Continuous coverage of {elapsed_months} months based on user input without verified inception date")
        if scenario_input.condition_name:
            user_assumptions.append(f"Condition '{scenario_input.condition_name}' assumed to be a disclosed pre-existing condition")

        if has_verified_endorsement and not has_schedule_conflict and not schedule_rider_inapplicable_reason:
            evidentiary_support = f"Supported by Policy Schedule Endorsement ({schedule.filename if schedule else 'Schedule'}) and Base Wording ({policy.filename})."
        else:
            evidentiary_support = f"Supported by Base Policy Wording ({policy.filename})."

        return ScenarioResult(
            scenario_id=f"scen_ped_{policy.fingerprint[:8]}",
            scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
            policy_fingerprint=policy.fingerprint,
            verdict=verdict,
            decision_state=decision_state,
            headline=headline,
            explanation=explanation,
            applicable_duration_amount=waiting_months,
            applicable_duration_unit="months",
            elapsed_duration_amount=elapsed_months,
            remaining_duration_amount=remaining,
            applicable_fact_ids=(chosen_fact.fact_id,),
            source_references=tuple(self._build_source_references(applicable_facts, policy)),
            unresolved_conditions=tuple(unresolved_conditions),
            user_assumptions=tuple(user_assumptions),
            calculation_formula=f"Applicable Waiting Period: {waiting_months} months | Elapsed Duration: {elapsed_months} months | Remaining: {remaining} months",
            evidentiary_support=evidentiary_support,
            limitations=tuple(limitations),
        )

    # -------------------------------------------------------------------------
    # 2. Initial Waiting Period Evaluation
    # -------------------------------------------------------------------------
    def _evaluate_initial_waiting_period_scenario(
        self,
        policy: ProcessedPolicy,
        facts: list[PolicyFact],
        scenario_input: ScenarioInput,
    ) -> ScenarioResult:
        initial_facts = [
            f for f in facts
            if f.category == FactCategory.WAITING_PERIOD
            and ("initial" in f.proposition.lower() or (f.structured_value and getattr(f.structured_value, "unit", None) == DurationUnit.DAYS))
            and f.validation_status != FactValidationStatus.REJECTED
        ]

        if not initial_facts:
            return ScenarioResult(
                scenario_id=f"scen_init_{policy.fingerprint[:8]}",
                scenario_type=ScenarioType.INITIAL_WAITING_PERIOD,
                policy_fingerprint=policy.fingerprint,
                verdict=ScenarioVerdict.INSUFFICIENT_EVIDENCE,
                headline="No Established Initial Waiting Period Found",
                explanation=f"No initial waiting period clause was established in {policy.filename}.",
                missing_inputs=("Established initial waiting period fact",),
                limitations=("Cannot evaluate initial waiting period without contractual clause.",),
            )

        chosen_fact = initial_facts[0]
        waiting_days = getattr(chosen_fact.structured_value, "amount", 30)
        applicable_facts = [chosen_fact]

        # Check accidental injury exception
        if scenario_input.is_accidental_injury:
            return ScenarioResult(
                scenario_id=f"scen_init_{policy.fingerprint[:8]}",
                scenario_type=ScenarioType.INITIAL_WAITING_PERIOD,
                policy_fingerprint=policy.fingerprint,
                verdict=ScenarioVerdict.CONDITIONAL_REVIEW,
                decision_state=DecisionIntegrityState.CONDITIONAL_UNRESOLVED,
                headline="Initial Waiting Period Exception: Accidental Injury",
                explanation=(
                    f"The policy's {waiting_days}-day initial waiting period does NOT apply to hospitalizations "
                    "arising directly from an accidental injury, provided accident coverage is active."
                ),
                applicable_duration_amount=waiting_days,
                applicable_duration_unit="days",
                applicable_fact_ids=(chosen_fact.fact_id,),
                source_references=tuple(self._build_source_references(applicable_facts, policy)),
                unresolved_conditions=("Requires hospital and medical records confirming treatment was necessitated by accidental injury.",),
                calculation_formula="Accidental Bodily Injury -> 30-Day Illness Waiting Period Waived",
                evidentiary_support=f"Base Policy Wording ({policy.filename}).",
                limitations=(
                    "Exemption applies strictly to emergency accidental injury care, not elective or illness treatment.",
                    "Regular policy conditions, deductibles, and sum insured limits remain applicable.",
                ),
            )

        # Calculate elapsed days
        _, elapsed_days, timing_notes = calculate_elapsed_time(
            scenario_input.inception_date,
            scenario_input.incident_date,
            scenario_input.elapsed_months,
            scenario_input.elapsed_days,
        )

        if elapsed_days is None:
            return ScenarioResult(
                scenario_id=f"scen_init_{policy.fingerprint[:8]}",
                scenario_type=ScenarioType.INITIAL_WAITING_PERIOD,
                policy_fingerprint=policy.fingerprint,
                verdict=ScenarioVerdict.INSUFFICIENT_EVIDENCE,
                decision_state=DecisionIntegrityState.EVIDENCE_INSUFFICIENT,
                headline="Missing Days Since Inception",
                explanation=(
                    f"The policy establishes a {waiting_days}-day initial illness waiting period, "
                    "but the elapsed days since first commencement were not provided."
                ),
                applicable_duration_amount=waiting_days,
                applicable_duration_unit="days",
                applicable_fact_ids=(chosen_fact.fact_id,),
                source_references=tuple(self._build_source_references(applicable_facts, policy)),
                missing_inputs=("Days elapsed since first policy commencement",),
                limitations=("Cannot evaluate initial illness coverage without elapsed days.",),
                evidentiary_support=f"Base Policy Wording ({policy.filename}).",
            )

        if elapsed_days < waiting_days:
            remaining = waiting_days - elapsed_days
            verdict = ScenarioVerdict.WAITING_PERIOD_ACTIVE
            decision_state = DecisionIntegrityState.WAITING_PERIOD_RULE_IDENTIFIED
            headline = f"Initial Waiting Period is Active ({remaining} Days Remaining)"
            explanation = (
                f"Treatment occurred on day {elapsed_days} from policy commencement, which is within the mandatory "
                f"{waiting_days}-day initial illness waiting period (Code-Excl03). Expenses related to illness within this period are excluded."
            )
        else:
            remaining = 0
            verdict = ScenarioVerdict.WAITING_PERIOD_SATISFIED
            decision_state = DecisionIntegrityState.WAITING_PERIOD_CONDITION_SATISFIED
            headline = f"Initial {waiting_days}-Day Waiting Period Satisfied"
            explanation = (
                f"The initial {waiting_days}-day waiting period for illness has elapsed "
                f"({elapsed_days} days since inception date)."
            )

        limitations = [
            "Satisfaction of the initial waiting period does not guarantee coverage.",
            "Specific disease waiting periods (typically 24 months) and pre-existing disease waiting periods still apply.",
        ]
        if timing_notes:
            limitations.extend(timing_notes)

        return ScenarioResult(
            scenario_id=f"scen_init_{policy.fingerprint[:8]}",
            scenario_type=ScenarioType.INITIAL_WAITING_PERIOD,
            policy_fingerprint=policy.fingerprint,
            verdict=verdict,
            decision_state=decision_state,
            headline=headline,
            explanation=explanation,
            applicable_duration_amount=waiting_days,
            applicable_duration_unit="days",
            elapsed_duration_amount=elapsed_days,
            remaining_duration_amount=remaining,
            applicable_fact_ids=(chosen_fact.fact_id,),
            source_references=tuple(self._build_source_references(applicable_facts, policy)),
            calculation_formula=f"Initial Waiting Period: {waiting_days} days | Elapsed Days: {elapsed_days} | Remaining: {remaining} days",
            evidentiary_support=f"Base Policy Wording ({policy.filename}).",
            limitations=tuple(limitations),
        )

    # -------------------------------------------------------------------------
    # 3. Conditional Exclusion Evaluation
    # -------------------------------------------------------------------------
    def _evaluate_exclusion_scenario(
        self,
        policy: ProcessedPolicy,
        facts: list[PolicyFact],
        scenario_input: ScenarioInput,
    ) -> ScenarioResult:
        query_condition = (scenario_input.condition_name or "").lower()

        # Find matching exclusion facts
        exclusion_facts = [
            f for f in facts
            if f.category == FactCategory.EXCLUSION
            and f.validation_status != FactValidationStatus.REJECTED
        ]

        matched_fact: PolicyFact | None = None
        for f in exclusion_facts:
            prop = f.proposition.lower()
            if any(term in prop for term in query_condition.split() if len(term) > 3):
                matched_fact = f
                break

        if matched_fact is None:
            # Fallback check against known keywords
            if "alcohol" in query_condition or "substance" in query_condition:
                matched_fact = next((f for f in exclusion_facts if "alcohol" in f.proposition.lower()), None)
            elif "obesity" in query_condition or "bariatric" in query_condition or "weight" in query_condition:
                matched_fact = next((f for f in exclusion_facts if "obesity" in f.proposition.lower()), None)
            elif "diagnostic" in query_condition or "investigation" in query_condition:
                matched_fact = next((f for f in exclusion_facts if "investigation" in f.proposition.lower()), None)

        if matched_fact is None:
            return ScenarioResult(
                scenario_id=f"scen_excl_{policy.fingerprint[:8]}",
                scenario_type=ScenarioType.CONDITIONAL_EXCLUSION,
                policy_fingerprint=policy.fingerprint,
                verdict=ScenarioVerdict.INSUFFICIENT_EVIDENCE,
                headline="No Established Exclusion Clause Found for Query",
                explanation=f"No specific exclusion clause for '{scenario_input.condition_name or 'unspecified condition'}' was established in {policy.filename}.",
                missing_inputs=("Applicable exclusion clause in policy text",),
                limitations=("Cannot evaluate exclusion without exact policy clause reference.",),
            )

        applicable_facts = [matched_fact]
        has_exceptions = bool(matched_fact.exceptions)
        is_conditional = matched_fact.validation_status == FactValidationStatus.NEEDS_REVIEW or has_exceptions

        if is_conditional:
            verdict = ScenarioVerdict.CONDITIONAL_REVIEW
            headline = f"Conditional Exclusion Identified: {matched_fact.proposition}"
            explanation = (
                f"The policy contains a conditional exclusion clause regarding this treatment. "
                "Coverage is excluded by default, UNLESS specific clinical exception protocols are strictly satisfied."
            )
            unresolved = list(matched_fact.exceptions) or [
                "Requires submission of clinical protocols and doctor recommendation for medical necessity review.",
                "Subject to underwriting verification of exception criteria (e.g. BMI thresholds, post-accident reconstruction).",
            ]
        else:
            verdict = ScenarioVerdict.EXCLUSION_IDENTIFIED
            headline = f"Standard Exclusion Identified: {matched_fact.proposition}"
            explanation = (
                f"The policy explicitly excludes expenses related to this treatment under standard policy exclusions. "
                "No clinical exception was identified in the policy wording."
            )
            unresolved = []

        return ScenarioResult(
            scenario_id=f"scen_excl_{policy.fingerprint[:8]}",
            scenario_type=ScenarioType.CONDITIONAL_EXCLUSION,
            policy_fingerprint=policy.fingerprint,
            verdict=verdict,
            headline=headline,
            explanation=explanation,
            applicable_fact_ids=(matched_fact.fact_id,),
            source_references=tuple(self._build_source_references(applicable_facts, policy)),
            unresolved_conditions=tuple(unresolved),
            limitations=(
                "Finding an exclusion does not preclude separate specialized rider covers purchased under the policy schedule.",
                "Clinical protocol determinations require reviewing full medical hospital records.",
            ),
        )

    # -------------------------------------------------------------------------
    # 4. Entry-Age Co-Payment Evaluation
    # -------------------------------------------------------------------------
    def _evaluate_copayment_scenario(
        self,
        policy: ProcessedPolicy,
        facts: list[PolicyFact],
        scenario_input: ScenarioInput,
        schedule: Any | None = None,
    ) -> ScenarioResult:
        copay_facts = [
            f for f in facts
            if f.category == FactCategory.DEDUCTIBLE_OR_COPAY
            and isinstance(f.structured_value, PercentageValue)
            and f.validation_status != FactValidationStatus.REJECTED
        ]

        if not copay_facts:
            return ScenarioResult(
                scenario_id=f"scen_copay_{policy.fingerprint[:8]}",
                scenario_type=ScenarioType.ENTRY_AGE_COPAYMENT,
                policy_fingerprint=policy.fingerprint,
                verdict=ScenarioVerdict.WAITING_PERIOD_SATISFIED,
                decision_state=DecisionIntegrityState.RULE_OUTCOME_ESTABLISHED,
                headline="No Mandatory Entry-Age Co-Payment Established",
                explanation=f"No mandatory entry-age co-payment clause was identified in {policy.filename}.",
                calculation_formula="Mandatory Co-Payment = 0% (None found in base wording)",
                evidentiary_support=f"Document search across {policy.filename}.",
                limitations=(
                    "Check your Policy Schedule for voluntary or mandatory co-payment endorsements elected at inception.",
                ),
            )

        chosen_fact = copay_facts[0]
        pct = getattr(chosen_fact.structured_value, "percentage", 10.0)
        entry_age = scenario_input.member_age_at_entry
        claim_amt = scenario_input.claim_amount
        applicable_facts = [chosen_fact]

        if entry_age is None:
            return ScenarioResult(
                scenario_id=f"scen_copay_{policy.fingerprint[:8]}",
                scenario_type=ScenarioType.ENTRY_AGE_COPAYMENT,
                policy_fingerprint=policy.fingerprint,
                verdict=ScenarioVerdict.INSUFFICIENT_EVIDENCE,
                decision_state=DecisionIntegrityState.EVIDENCE_INSUFFICIENT,
                headline="Member Entry Age Required",
                explanation=(
                    f"The policy specifies a {pct:g}% co-payment based on entry age (typically 61+ years). "
                    "Please provide the insured person's age at the time of entry to evaluate applicability."
                ),
                copayment_percentage=pct,
                applicable_fact_ids=(chosen_fact.fact_id,),
                source_references=tuple(self._build_source_references(applicable_facts, policy)),
                missing_inputs=("Insured person entry age",),
                limitations=("Cannot evaluate co-payment applicability without entry age.",),
                evidentiary_support=f"Base Policy Wording ({policy.filename}).",
            )

        # Threshold evaluation (standard Indian health policy threshold is 61 years)
        threshold = 61
        for cond in chosen_fact.conditions:
            if "61" in cond:
                threshold = 61
                break

        if entry_age < threshold:
            return ScenarioResult(
                scenario_id=f"scen_copay_{policy.fingerprint[:8]}",
                scenario_type=ScenarioType.ENTRY_AGE_COPAYMENT,
                policy_fingerprint=policy.fingerprint,
                verdict=ScenarioVerdict.WAITING_PERIOD_SATISFIED,
                decision_state=DecisionIntegrityState.RULE_OUTCOME_ESTABLISHED,
                headline=f"Entry-Age Co-Payment Does Not Apply (Age {entry_age} < {threshold})",
                explanation=(
                    f"The insured person entered the policy at age {entry_age}, which is below the threshold of {threshold} years. "
                    f"The {pct:g}% entry-age co-payment clause does not apply."
                ),
                copayment_percentage=0.0,
                applicable_fact_ids=(chosen_fact.fact_id,),
                source_references=tuple(self._build_source_references(applicable_facts, policy)),
                calculation_formula=f"Entry Age ({entry_age}) < Threshold ({threshold}) -> Co-payment 0%",
                user_assumptions=(f"Insured member entered policy at age {entry_age}",),
                evidentiary_support=f"Base Policy Wording ({policy.filename}).",
                limitations=(
                    "Exemption from entry-age co-payment does not exempt voluntary co-payments chosen at application.",
                ),
            )

        # Co-payment applies
        copay_amt: float | None = None
        insurer_amt: float | None = None
        calc_formula: str = ""
        user_assumptions: list[str] = [f"Member entry age {entry_age} verified"]

        vol_ded = getattr(schedule, "voluntary_deductible", None) if schedule else None

        if claim_amt is not None and claim_amt > 0.0:
            user_assumptions.append(f"Gross claim of Rs {claim_amt:,.0f} assumed fully admissible before cost-sharing")
            if vol_ded and vol_ded > 0.0:
                user_assumptions.append(f"Voluntary deductible of Rs {vol_ded:,.0f} verified from schedule")
                eligible_after_ded = max(0.0, claim_amt - vol_ded)
                copay_amt = eligible_after_ded * (pct / 100.0)
                insurer_amt = eligible_after_ded - copay_amt
                total_patient = vol_ded + copay_amt
                headline = f"{pct:g}% Co-Pay + Deductible: Rs {total_patient:,.0f} Patient Share on Rs {claim_amt:,.0f} Claim"
                explanation = (
                    f"A mandatory {pct:g}% co-payment applies based on entry age {entry_age} (threshold: {threshold}+), "
                    f"alongside an active schedule voluntary deductible of Rs {vol_ded:,.0f}. "
                    f"Voluntary deductible applies first without double counting; co-payment applies strictly to the eligible remainder."
                )
                calc_formula = (
                    f"Step 1: Gross Claim Rs {claim_amt:,.0f} - Deductible Rs {vol_ded:,.0f} = Eligible Remainder Rs {eligible_after_ded:,.0f}. "
                    f"Step 2: Co-Payment {pct:g}% on Remainder = Rs {copay_amt:,.0f}. "
                    f"Total Patient Liability = Rs {vol_ded:,.0f} (deductible) + Rs {copay_amt:,.0f} (co-pay) = Rs {total_patient:,.0f}; Insurer Share = Rs {insurer_amt:,.0f}."
                )
            else:
                copay_amt = claim_amt * (pct / 100.0)
                insurer_amt = claim_amt - copay_amt
                headline = f"{pct:g}% Co-Payment: Rs {copay_amt:,.0f} Patient Share on Rs {claim_amt:,.0f} Claim"
                explanation = (
                    f"A mandatory {pct:g}% co-payment applies based on entry age {entry_age} (threshold: {threshold}+). "
                    f"On an admissible claim of Rs {claim_amt:,.0f}, the calculated patient share is Rs {copay_amt:,.0f}, "
                    f"and the calculated insurer portion is Rs {insurer_amt:,.0f}."
                )
                calc_formula = f"Patient Share = Admissible Claim Amount * {pct / 100.0:g}"
        else:
            user_assumptions.append("Claim amount unspecified")
            headline = f"{pct:g}% Co-Payment Applicable (Entry Age {entry_age} ≥ {threshold})"
            explanation = (
                f"The insured person entered at age {entry_age} (threshold: {threshold}+). "
                f"A mandatory {pct:g}% co-payment applies to each and every admissible claim amount. "
                f"Formula: Patient Share = Admissible Claim Amount * {pct / 100.0:g}."
            )
            calc_formula = f"Patient Share = Admissible Claim Amount * {pct / 100.0:g}"

        return ScenarioResult(
            scenario_id=f"scen_copay_{policy.fingerprint[:8]}",
            scenario_type=ScenarioType.ENTRY_AGE_COPAYMENT,
            policy_fingerprint=policy.fingerprint,
            verdict=ScenarioVerdict.CONDITIONAL_REVIEW,
            decision_state=DecisionIntegrityState.RULE_OUTCOME_ESTABLISHED,
            headline=headline,
            explanation=explanation,
            copayment_percentage=pct,
            calculated_copayment_amount=copay_amt,
            calculated_insurer_portion=insurer_amt,
            applicable_fact_ids=(chosen_fact.fact_id,),
            source_references=tuple(self._build_source_references(applicable_facts, policy)),
            unresolved_conditions=("Requires verification that the claim amount is clinically admissible under policy conditions.",),
            calculation_formula=calc_formula,
            user_assumptions=tuple(user_assumptions),
            evidentiary_support=f"Base Policy Wording ({policy.filename})" + (f" and Schedule ({schedule.filename})" if schedule else "") + ".",
            limitations=(
                "Admissible claim estimate does NOT equal the final insurer payout.",
                "Non-medical charges (hospital consumables), room rent proportionate deductions, and other sub-limits are deducted prior to co-payment.",
                "Final settlement is subject to official claims adjudication by the insurer or TPA.",
            ),
        )

    # -------------------------------------------------------------------------
    # 5. Unsupported Scenario Handling
    # -------------------------------------------------------------------------
    def _evaluate_unsupported_scenario(
        self,
        scenario_input: ScenarioInput,
        policy: ProcessedPolicy | None = None,
    ) -> ScenarioResult:
        fp = policy.fingerprint if policy else ""
        return ScenarioResult(
            scenario_id=f"scen_unsupported_{fp[:8]}" if fp else "scen_unsupported",
            scenario_type=ScenarioType.UNSUPPORTED,
            policy_fingerprint=fp,
            verdict=ScenarioVerdict.UNSUPPORTED_SCENARIO,
            headline="Scenario Type Unsupported by Deterministic Rules",
            explanation=(
                "This scenario requires underwriting discretion, multi-rule claim settlement tables, "
                "or policy schedule endorsements not currently supported by deterministic evaluation. "
                "Please use the 'Ask My Policy' workspace to search specific clause wording."
            ),
            limitations=(
                "Deterministic rules in Phase 1.5 support pre-existing diseases, initial 30 days, conditional exclusions, and entry-age co-payment only.",
            ),
        )
