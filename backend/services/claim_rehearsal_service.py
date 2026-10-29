"""Claim Rehearsal evaluation service.

Performs deterministic, evidence-grounded evaluation of planned hospitalizations
and medical claims against extracted policy facts, waiting periods, room-rent limits,
and co-payment clauses.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
from typing import Any, Sequence
import uuid

from backend.api.schemas import (
    ClaimRehearsalRequest,
    ClaimRehearsalResponse,
    FinancialBreakdown,
    RehearsalChecklistItem,
)
from backend.domain.adapter import extract_candidate_facts
from backend.domain.enums import FactCategory, FactValidationStatus
from backend.domain.models import DurationUnit, DurationValue, PercentageValue, PolicyFact
from backend.qa.retrieval import retrieve_chunks
from backend.qa.workflow import ProcessedPolicy

logger = logging.getLogger(__name__)

# Common specific ailments with statutory or standard policy waiting periods (usually 24 months in India).
# Keys are sorted with longer, more specific phrases first so "kidney stone" matches before "stone".
_RAW_SPECIFIC_AILMENT_PATTERNS = {
    "kidney stone": "Renal / Kidney stone treatment",
    "gallbladder": "Gallbladder stones (Cholecystectomy)",
    "cholecystectomy": "Gallbladder stones (Cholecystectomy)",
    "joint replacement": "Joint replacement surgery",
    "knee replacement": "Joint replacement / Knee surgery",
    "hip replacement": "Joint replacement / Hip surgery",
    "cataract": "Cataract surgery",
    "knee": "Joint replacement / Knee surgery",
    "joint": "Joint replacement surgery",
    "hip": "Joint replacement / Hip surgery",
    "hernia": "Hernia repair",
    "hydrocele": "Hydrocele surgery",
    "hysterectomy": "Hysterectomy (removal of uterus)",
    "stone": "Calculus / Stones in urinary or biliary system",
    "piles": "Piles / Haemorrhoids / Fistula",
    "fistula": "Fistula-in-ano / Fissure surgery",
    "fissure": "Anal fissure surgery",
    "sinus": "Sinusitis / ENT surgery",
    "tonsil": "Tonsillectomy / Adenoidectomy",
    "prostate": "Benign Prostatic Hypertrophy (BPH)",
    "bariatric": "Bariatric / Metabolic surgery",
    "maternity": "Maternity delivery / Caesarean",
    "delivery": "Maternity delivery",
    "caesarean": "Caesarean section delivery",
}
SPECIFIC_AILMENT_PATTERNS = dict(
    sorted(_RAW_SPECIFIC_AILMENT_PATTERNS.items(), key=lambda x: len(x[0]), reverse=True)
)

EXCLUSION_PATTERNS = {
    "cosmetic": "Cosmetic, aesthetic or plastic surgery (Code-Excl02)",
    "aesthetic": "Aesthetic or beautification treatments (Code-Excl02)",
    "alcohol": "Treatment for alcoholism, drug abuse or addictive substances (Code-Excl12)",
    "substance abuse": "Substance or drug abuse rehabilitation (Code-Excl12)",
    "self-inflicted": "Intentional self-inflicted injury or suicide attempt (Code-Excl08)",
    "suicide": "Intentional self-inflicted harm or suicide attempt (Code-Excl08)",
    "hazardous": "Adventure / hazardous sports without endorsement (Code-Excl09)",
    "unproven": "Unproven or experimental medical treatments (Code-Excl11)",
    "experimental": "Experimental or investigational treatment protocols (Code-Excl11)",
    "rest cure": "Rest cure, rehabilitation, and respite care (Code-Excl05)",
}


def _match_treatment_keyword(pattern: str, text: str) -> bool:
    """Safely match keyword pattern using word boundaries to prevent substring collisions."""
    if not pattern or not text:
        return False

    # If pattern is 'delivery', only match clinical maternity/childbirth phrases
    if pattern == "delivery":
        if re.search(
            r"\b(?:normal|caesarean|cesarean|vaginal|obstetric|childbirth|baby|twin)\s+delivery\b"
            r"|\bdelivery\s+of\s+(?:baby|child|infant|newborn|twins)\b",
            text,
            flags=re.I,
        ):
            return True
        if re.search(r"\bdelivery\s+of\b", text, flags=re.I):
            return False
        if re.search(r"\b(?:home|courier|fast|express|food|packet|parcel)\s+delivery\b", text, flags=re.I):
            return False
        return bool(re.search(r"\b(?:normal\s+|baby\s+|maternity\s+)?delivery\b", text, flags=re.I))

    # Avoid matching 'milestone' or non-clinical usage for 'stone'
    if pattern == "stone":
        if re.search(r"\bmilestone\b", text, flags=re.I):
            return False
        return bool(re.search(r"\b(?:gall|kidney\s+|bladder\s+)?stones?\b", text, flags=re.I))

    # Avoid matching negated terms like 'non-cosmetic'
    if pattern in ("cosmetic", "aesthetic"):
        return bool(re.search(r"(?<!non-)\b" + re.escape(pattern) + r"(?:e?s)?\b", text, flags=re.I))

    escaped = re.escape(pattern)
    plural_suffix = r"(?:e?s)?" if not pattern.endswith("s") else ""
    regex = rf"\b{escaped}{plural_suffix}\b"
    return bool(re.search(regex, text, flags=re.I))


def _find_matching_clauses(
    query: str,
    policy: ProcessedPolicy,
    top_k: int = 4,
) -> list[dict[str, Any]]:
    """Retrieve top relevant evidence chunks from the policy with page numbers."""
    try:
        retrieved = retrieve_chunks(query, policy.chunks, top_k=top_k)
        clauses = []
        for rc in retrieved:
            # Clean snippet for display
            snippet = rc.text.strip().replace("\n", " ")
            if len(snippet) > 300:
                snippet = snippet[:297] + "..."
            clauses.append({
                "chunk_id": rc.chunk_id,
                "page_number": rc.page_number,
                "quote": snippet,
                "relevance_score": round(rc.score, 3),
            })
        return clauses
    except Exception as exc:
        logger.warning("Error retrieving chunks for query '%s': %s", query, exc)
        return []


def evaluate_claim_rehearsal(
    policy: ProcessedPolicy,
    req: ClaimRehearsalRequest,
) -> ClaimRehearsalResponse:
    """Run full evidence-backed claim rehearsal evaluation."""
    treatment_raw = (req.treatment_description or "").strip().lower()
    if not treatment_raw:
        treatment_raw = "hospitalization"

    facts = extract_candidate_facts(policy)
    supporting_clauses: list[dict[str, Any]] = []
    relevant_conditions: list[dict[str, Any]] = []
    missing_info: list[str] = []
    unresolved_assumptions: list[str] = []
    questions_to_ask: list[str] = []
    checklist_items: list[RehearsalChecklistItem] = []

    # Risk level trackers
    has_active_waiting_period = False
    has_copayment = False
    has_room_rent_risk = False
    has_specific_sublimit = False
    has_exclusion = False

    if req.policy_duration_months is None:
        unresolved_assumptions.append("Policy duration defaulted to 12 continuous months.")
    if req.room_category is None:
        unresolved_assumptions.append("Room category defaulted to single private room.")
    if req.member_age is None:
        unresolved_assumptions.append("Member entry age assumed below senior co-payment threshold unless verified.")
    if req.estimated_expense is None or req.estimated_expense <= 0:
        missing_info.append("Estimated claim expenditure not provided; financial cost breakdown omitted.")

    elapsed_months = req.policy_duration_months if req.policy_duration_months is not None else 12

    # -------------------------------------------------------------------------
    # 0. Policy Exclusion Check
    # -------------------------------------------------------------------------
    for pat, desc in EXCLUSION_PATTERNS.items():
        if _match_treatment_keyword(pat, treatment_raw):
            has_exclusion = True
            excl_clauses = _find_matching_clauses(f"{pat} exclusion not covered", policy, top_k=2)
            relevant_conditions.append({
                "category": "Policy Exclusion",
                "status": "excluded",
                "severity": "high",
                "title": f"Potential Exclusion: {desc.split('(')[0].strip()}",
                "details": (
                    f"Treatment involves '{treatment_raw}', which may fall under standard policy exclusions: "
                    f"{desc}. Expenses related to excluded procedures are typically inadmissible."
                ),
            })
            for cl in excl_clauses:
                cl["topic"] = f"Exclusion Clause: {pat}"
                supporting_clauses.append(cl)
            break

    # -------------------------------------------------------------------------
    # 1. Initial 30-Day Waiting Period Check
    # -------------------------------------------------------------------------
    is_accident_or_emergency = req.is_emergency or any(w in treatment_raw for w in ["accident", "trauma", "fracture", "emergency"])
    initial_wp_clauses = _find_matching_clauses("30 days waiting period accidental injury", policy, top_k=2)

    if elapsed_months < 1 and not is_accident_or_emergency:
        has_active_waiting_period = True
        relevant_conditions.append({
            "category": "Initial Waiting Period",
            "status": "active_risk",
            "severity": "high",
            "title": "Initial 30-Day Waiting Period Active",
            "details": (
                f"Policy duration is {elapsed_months} month(s). Most health insurance policies "
                "exclude non-emergency planned hospitalizations during the first 30 days from inception. "
                "Only accidental injuries are typically covered immediately."
            ),
        })
        questions_to_ask.append("Does my policy schedule waive the 30-day initial waiting period via portability or continuity credit?")
        for cl in initial_wp_clauses:
            cl["topic"] = "Initial Waiting Period"
            supporting_clauses.append(cl)
    else:
        if is_accident_or_emergency:
            relevant_conditions.append({
                "category": "Initial Waiting Period",
                "status": "exempt",
                "severity": "low",
                "title": "Emergency / Accident Exception",
                "details": "Emergency hospitalization or accidental trauma is exempted from the initial 30-day waiting period.",
            })

    # -------------------------------------------------------------------------
    # 2. Specific Ailment Waiting Period (12 to 24 Months)
    # -------------------------------------------------------------------------
    detected_ailment = None
    sublimit_amount: float | None = None
    for pattern, name in SPECIFIC_AILMENT_PATTERNS.items():
        if _match_treatment_keyword(pattern, treatment_raw):
            detected_ailment = (pattern, name)
            break

    if detected_ailment:
        pattern_key, ailment_name = detected_ailment
        ailment_clauses = _find_matching_clauses(f"{ailment_name} waiting period 24 months 36 months", policy, top_k=3)
        for cl in ailment_clauses:
            cl["topic"] = f"Specific Clause: {ailment_name}"
            supporting_clauses.append(cl)

        # Check if policy facts establish a specific waiting period for this ailment or category
        standard_wp_months = 24
        specific_wp_facts = [
            f for f in facts
            if f.category == FactCategory.WAITING_PERIOD
            and (
                pattern_key in f.proposition.lower()
                or "specific" in f.proposition.lower()
                or "specified" in f.proposition.lower()
            )
            and f.validation_status != FactValidationStatus.REJECTED
        ]
        if specific_wp_facts and isinstance(specific_wp_facts[0].structured_value, DurationValue):
            dv = specific_wp_facts[0].structured_value
            standard_wp_months = (
                dv.amount * 12
                if dv.unit == DurationUnit.YEARS
                else (max(1, dv.amount // 30) if dv.unit == DurationUnit.DAYS else dv.amount)
            )
        elif "bariatric" in pattern_key:
            standard_wp_months = 36
        elif "maternity" in pattern_key or "delivery" in pattern_key:
            standard_wp_months = 24

        # Check for procedure-specific monetary sublimits (e.g. Cataract cap, Maternity limit)
        sublimit_facts = [
            f for f in facts
            if f.category == FactCategory.LIMIT_OR_SUBLIMIT
            and (
                pattern_key in f.proposition.lower()
                or any(pattern_key in (ref.exact_text or "").lower() for ref in f.evidence_references)
            )
            and f.validation_status != FactValidationStatus.REJECTED
        ]
        sublimit_amount: float | None = None
        if sublimit_facts:
            has_specific_sublimit = True
            slf = sublimit_facts[0]
            if slf.structured_value and hasattr(slf.structured_value, "amount"):
                sublimit_amount = float(slf.structured_value.amount)
            elif slf.structured_value and hasattr(slf.structured_value, "maximum_amount"):
                sublimit_amount = float(slf.structured_value.maximum_amount)
            limit_str = f"₹{sublimit_amount:,.0f}" if sublimit_amount else "specified sub-limit"
            relevant_conditions.append({
                "category": "Procedure Sub-Limit",
                "status": "sublimit_applied",
                "severity": "medium",
                "title": f"Specific Sub-Limit Applicable: {ailment_name} ({limit_str})",
                "details": (
                    f"Treatment for '{ailment_name}' is subject to a policy sub-limit of {limit_str}. "
                    "Any charges exceeding this threshold will be deducted as non-admissible out-of-pocket costs."
                ),
            })
            if slf.evidence_references:
                supporting_clauses.append({
                    "chunk_id": f"SUBLIMIT-{pattern_key.upper()}",
                    "page_number": slf.evidence_references[0].page_number,
                    "quote": slf.evidence_references[0].exact_text,
                    "topic": f"Sub-Limit Provision: {ailment_name}",
                })

        if elapsed_months < standard_wp_months:
            has_active_waiting_period = True
            relevant_conditions.append({
                "category": "Specific Ailment Waiting Period",
                "status": "active_risk",
                "severity": "high",
                "title": f"Specific Waiting Period Applicable ({ailment_name})",
                "details": (
                    f"Treatment involves '{ailment_name}', which is subject to a "
                    f"{standard_wp_months}-month waiting period under policy terms. Your current elapsed duration is {elapsed_months} month(s). "
                    "Hospitalization before this period may result in claim rejection unless continuity credit applies."
                ),
            })
            questions_to_ask.append(
                f"Is the specific waiting period for '{ailment_name}' satisfied under my policy schedule, or do I have waiting-period waiver endorsement?"
            )
        else:
            relevant_conditions.append({
                "category": "Specific Ailment Waiting Period",
                "status": "satisfied",
                "severity": "low",
                "title": f"Specific Waiting Period Satisfied ({ailment_name})",
                "details": f"Elapsed duration ({elapsed_months} months) meets or exceeds the {standard_wp_months}-month waiting period for {ailment_name}.",
            })

    # -------------------------------------------------------------------------
    # 3. Pre-Existing Condition (PED) Waiting Period
    # -------------------------------------------------------------------------
    ped_facts = [
        f for f in facts
        if f.category == FactCategory.WAITING_PERIOD
        and ("pre-existing" in f.proposition.lower() or "ped" in f.proposition.lower())
    ]
    ped_months = 36  # Default fallback
    ped_fact_quote = None
    ped_fact_page = 1
    if ped_facts:
        first_ped = ped_facts[0]
        if isinstance(first_ped.structured_value, DurationValue):
            amt = first_ped.structured_value.amount
            unit = first_ped.structured_value.unit
            if unit == DurationUnit.YEARS:
                ped_months = amt * 12
            else:
                ped_months = amt
        if first_ped.evidence_references:
            ped_fact_quote = first_ped.evidence_references[0].exact_text
            ped_fact_page = first_ped.evidence_references[0].page_number

    if req.is_pre_existing:
        if elapsed_months < ped_months:
            has_active_waiting_period = True
            relevant_conditions.append({
                "category": "Pre-Existing Disease (PED)",
                "status": "active_risk",
                "severity": "high",
                "title": f"Pre-Existing Disease Waiting Period Active ({ped_months} Months)",
                "details": (
                    f"This condition is marked as pre-existing. The policy establishes a {ped_months}-month "
                    f"waiting period for pre-existing ailments. With {elapsed_months} months of continuous coverage, "
                    f"expenses related to this condition are excluded until month {ped_months}."
                ),
            })
            questions_to_ask.append(
                f"Is my pre-existing condition covered under a PED buyback rider or waiting-period reduction endorsement?"
            )
        else:
            relevant_conditions.append({
                "category": "Pre-Existing Disease (PED)",
                "status": "satisfied",
                "severity": "low",
                "title": "Pre-Existing Condition Waiting Period Satisfied",
                "details": f"Your continuous coverage of {elapsed_months} months satisfies the {ped_months}-month PED waiting period.",
            })

        if ped_fact_quote:
            supporting_clauses.append({
                "chunk_id": "PED-FACT",
                "page_number": ped_fact_page,
                "quote": ped_fact_quote,
                "topic": "Pre-Existing Disease Waiting Period Clause",
            })

    # -------------------------------------------------------------------------
    # 4. Room Rent Limits & Proportionate Deductions
    # -------------------------------------------------------------------------
    room_facts = [
        f for f in facts
        if f.category == FactCategory.LIMIT_OR_SUBLIMIT
        or "room rent" in f.proposition.lower()
    ]
    room_clauses = _find_matching_clauses("Room Rent Single Private A/C room proportionate deduction", policy, top_k=2)
    for rc in room_clauses:
        rc["topic"] = "Room Rent Eligibility & Category Limit"
        supporting_clauses.append(rc)

    room_cat = (req.room_category or "single_private").lower()
    if room_cat in ["deluxe_suite", "suite"]:
        has_room_rent_risk = True
        relevant_conditions.append({
            "category": "Room Category & Proportionate Deduction",
            "status": "warning",
            "severity": "medium",
            "title": "High Room Category: Proportionate Deduction Risk",
            "details": (
                "You selected Deluxe / Suite room category. Most Indian health policies restrict room rent to "
                "Single Private Room (or 1% of Sum Insured). Choosing an upgraded room category triggers "
                "proportionate deductions across associated doctor fees, nursing, and surgery costs."
            ),
        })
        questions_to_ask.append(
            "What is the maximum room category eligible for 100% cashless reimbursement without proportionate deductions?"
        )
    elif room_cat == "icu":
        relevant_conditions.append({
            "category": "Room Category",
            "status": "info",
            "severity": "low",
            "title": "ICU Admission Covered",
            "details": "Intensive Care Unit (ICU) charges are covered without sublimits in comprehensive plans, subject to medical necessity.",
        })
    else:
        relevant_conditions.append({
            "category": "Room Category",
            "status": "compliant",
            "severity": "low",
            "title": "Eligible Room Category",
            "details": f"Selected room category ({room_cat.replace('_', ' ').title()}) aligns with standard single private or twin sharing entitlement.",
        })

    # -------------------------------------------------------------------------
    # 5. Co-Payment Evaluation (Entry Age or Zonal)
    # -------------------------------------------------------------------------
    copay_facts = [
        f for f in facts
        if f.category == FactCategory.DEDUCTIBLE_OR_COPAY
        or "co-payment" in f.proposition.lower()
        or "copay" in f.proposition.lower()
    ]
    copay_percentage = 0.0
    if copay_facts:
        copay_pct = 10.0
        threshold_age = 61
        for f in copay_facts:
            if isinstance(f.structured_value, PercentageValue):
                copay_pct = float(f.structured_value.percentage)
            combined_text = f"{f.proposition} {' '.join(f.conditions)}"
            m_thresh = re.search(
                r"(?:aged|age\s+at\s+entry|entry\s+age|age|insured\s+persons?)\s*(?:is|of|exceeding|above|>=)?\s*(\d{2})\s*(?:years|yrs|\+)?",
                combined_text,
                re.IGNORECASE,
            )
            if m_thresh:
                try:
                    threshold_age = int(m_thresh.group(1))
                except ValueError:
                    threshold_age = 61

        copay_clauses = _find_matching_clauses(f"co-payment age {threshold_age} {copay_pct:g}% each and every claim", policy, top_k=2)

        if req.member_age is not None and req.member_age >= threshold_age:
            has_copayment = True
            copay_percentage = copay_pct
            relevant_conditions.append({
                "category": "Age-Based Co-Payment",
                "status": "active_deduction",
                "severity": "medium",
                "title": f"{copay_pct:g}% Co-Payment Required for Age {threshold_age}+",
                "details": (
                    f"Member entry age is {req.member_age}. Policy terms mandate a {copay_pct:g}% co-payment on each and "
                    f"every admissible claim amount for insured persons aged {threshold_age} years or above at entry."
                ),
            })
            questions_to_ask.append(
                f"Will the {copay_pct:g}% co-payment be deducted from my cashless pre-authorization or settled at final discharge?"
            )
            for cl in copay_clauses:
                cl["topic"] = "Co-Payment Clause"
                supporting_clauses.append(cl)
        elif req.member_age is not None:
            relevant_conditions.append({
                "category": "Age-Based Co-Payment",
                "status": "exempt",
                "severity": "low",
                "title": f"Co-Payment Not Applicable (Age {req.member_age} < {threshold_age})",
                "details": f"Member entry age ({req.member_age}) is below the mandatory co-payment entry threshold of {threshold_age} years.",
            })
        else:
            missing_info.append(f"Member entry age was not specified. Age >= {threshold_age} attracts a {copay_pct:g}% co-payment under this policy.")
    else:
        relevant_conditions.append({
            "category": "Co-Payment",
            "status": "exempt",
            "severity": "low",
            "title": "No Mandatory Co-Payment Found in Policy Terms",
            "details": f"No mandatory entry-age or general co-payment provision was identified in {policy.filename}. Admissible hospital expenses are 100% covered subject to sum insured.",
        })

    # -------------------------------------------------------------------------
    # 6. Cashless Network vs Reimbursement Admission
    # -------------------------------------------------------------------------
    hosp_type = (req.hospital_type or "network_cashless").lower()
    if hosp_type == "network_cashless":
        checklist_items.append(
            RehearsalChecklistItem(
                id="chk_preauth_48h",
                title="Submit TPA Pre-Authorization Form (48-72h Prior)",
                description="For planned hospitalization, submit the pre-authorization request form filled by the treating doctor at the hospital TPA desk.",
                category="pre_admission",
                is_mandatory=True,
                suggested_action="Visit the hospital TPA / Insurance desk with your e-Card and doctor's prescription 48 hours before admission.",
            )
        )
        checklist_items.append(
            RehearsalChecklistItem(
                id="chk_tpa_card_kyc",
                title="Carry Physical ID, Policy e-Card & KYC",
                description="Government photo ID (Aadhaar / PAN) and Health Card for the patient and primary insured are mandatory for TPA desk check-in.",
                category="documentation",
                is_mandatory=True,
                suggested_action="Keep digital copies and 2 photocopies of Aadhaar Card and Policy Schedule ready.",
            )
        )
    else:
        checklist_items.append(
            RehearsalChecklistItem(
                id="chk_intimate_insurer",
                title="Intimate Insurer within 24 Hours of Admission",
                description="Non-network admissions require claim intimation to the insurer customer care or portal within 24 hours of hospital entry.",
                category="tpa_coordination",
                is_mandatory=True,
                suggested_action="Call the 24/7 toll-free helpline on your policy document and note the claim intimation reference number.",
            )
        )
        checklist_items.append(
            RehearsalChecklistItem(
                id="chk_collect_originals",
                title="Collect Original Discharge Summary & Itemized Bills",
                description="Reimbursement claims require original signed discharge summary, indoor case papers, pharmacy tax invoices, and payment receipts.",
                category="documentation",
                is_mandatory=True,
                suggested_action="Request the hospital billing department for original stamped bills and implant barcodes if surgery was performed.",
            )
        )

    checklist_items.append(
        RehearsalChecklistItem(
            id="chk_room_rent_verification",
            title="Confirm Room Category with Hospital Billing Desk",
            description="Verify with the hospital admission desk that your allotted room strictly matches your policy entitlement to prevent proportionate deductions.",
            category="financial",
            is_mandatory=True,
            suggested_action="Request a written confirmation of room tariff and check that no luxury surcharges are added.",
        )
    )

    checklist_items.append(
        RehearsalChecklistItem(
            id="chk_non_medical_expenses",
            title="Account for Non-Medical Consumables",
            description="Expenses on PPE kits, gloves, hygiene packs, and registration fees are non-medical exclusions under IRDAI guidelines (typically ₹3,000–₹8,000).",
            category="financial",
            is_mandatory=False,
            suggested_action="Confirm if you have a consumables rider (e.g. Star Wellness / Shield) or set aside a small cash contingency.",
        )
    )

    # -------------------------------------------------------------------------
    # 7. Financial Breakdown Calculation
    # -------------------------------------------------------------------------
    fin_breakdown = None
    if req.estimated_expense and req.estimated_expense > 0:
        bill = float(req.estimated_expense)
        notes: list[str] = []
        copay_amount = 0.0
        room_deduction = 0.0
        sublimit_deduction = 0.0

        if sublimit_amount and bill > sublimit_amount:
            sublimit_deduction = round(bill - sublimit_amount, 2)
            notes.append(f"Capped at procedure sub-limit of ₹{sublimit_amount:,.0f} (₹{sublimit_deduction:,.0f} excess out-of-pocket).")

        if has_room_rent_risk:
            # Proportionate deduction estimate ~12% on associated charges
            room_deduction = round(bill * 0.12, 2)
            notes.append(f"Estimated 12% proportionate deduction penalty for selecting Deluxe Suite room category (₹{room_deduction:,.0f}).")

        # Typical non-medical consumable allowance ~4%
        consumables_estimate = round(bill * 0.04, 2)
        notes.append(f"Estimated non-medical consumables (gloves, sanitizer, admin fees) not payable by insurer (~₹{consumables_estimate:,.0f}).")

        # Admissible amount before co-payment under IRDAI standard guidelines:
        # Co-payment applies strictly to the admissible portion after non-payable deductions
        admissible_base = max(0.0, bill - sublimit_deduction - room_deduction)
        if copay_percentage > 0:
            copay_amount = round(admissible_base * (copay_percentage / 100.0), 2)
            if sublimit_deduction > 0 or room_deduction > 0:
                notes.append(f"{copay_percentage:g}% Co-payment applied for member entry age {req.member_age} on admissible sum of ₹{admissible_base:,.0f} (₹{copay_amount:,.0f}).")
            else:
                notes.append(f"{copay_percentage:g}% Co-payment applied for member entry age {req.member_age} (₹{copay_amount:,.0f}).")

        out_of_pocket = min(bill, round(copay_amount + room_deduction + sublimit_deduction + consumables_estimate, 2))
        insurer_coverage = max(0.0, round(bill - out_of_pocket, 2))

        fin_breakdown = FinancialBreakdown(
            estimated_bill=bill,
            deductible_or_copay_amount=copay_amount,
            copayment_percentage=copay_percentage if copay_percentage > 0 else None,
            room_rent_deduction_amount=room_deduction if room_deduction > 0 else None,
            estimated_out_of_pocket=out_of_pocket,
            estimated_insurer_coverage=insurer_coverage,
            calculation_notes=notes,
        )

    # -------------------------------------------------------------------------
    # 8. Readiness Status & Executive Synthesis
    # -------------------------------------------------------------------------
    if has_exclusion:
        readiness_status = "important_checks_required"
        headline = "Critical Policy Exclusion Risk Identified for Proposed Treatment"
        executive_summary = (
            f"The proposed treatment '{treatment_raw}' matches standard policy exclusions "
            f"under {policy.filename}. Confirm with your treating physician whether an exempt clinical condition "
            "(such as reconstructive surgery following accidental trauma) applies before submitting a claim."
        )
    elif has_active_waiting_period or has_room_rent_risk:
        readiness_status = "important_checks_required"
        headline = "Critical Policy Checks Required Prior to Hospitalization"
        executive_summary = (
            f"Claim rehearsal identified active waiting periods or financial deduction risks for '{treatment_raw}'. "
            "Specifically, review policy waiting periods and verify that your selected room category will not trigger "
            "proportionate deductions before hospital admission."
        )
    elif len(treatment_raw) < 4 or treatment_raw == "hospitalization":
        readiness_status = "insufficient_information"
        headline = "Specific Treatment Diagnosis Needed for Accurate Rehearsal"
        executive_summary = (
            "A general hospitalization inquiry cannot resolve procedure-specific sublimits or waiting periods. "
            "Please specify the clinical diagnosis or surgical procedure (e.g., Cataract, Knee Replacement, Day Care)."
        )
        missing_info.append("Precise clinical diagnosis or medical procedure name")
    else:
        readiness_status = "ready_to_verify"
        headline = "Claim Parameters Satisfied — Proceed with TPA Pre-Authorization"
        executive_summary = (
            f"No active waiting period or major policy exclusion was detected for '{treatment_raw}' "
            f"under {policy.filename}. Follow the pre-admission checklist to submit cashless pre-authorization."
        )

    if not questions_to_ask:
        questions_to_ask.append("What is the pre-authorization approval turnaround time for cashless admission?")
        questions_to_ask.append("Are all prescribed surgical consumables and implants covered under the base sum insured?")

    # Deduplicate supporting clauses by chunk_id
    deduped_clauses: list[dict[str, Any]] = []
    seen_chunks: set[str] = set()
    for c in supporting_clauses:
        cid = c.get("chunk_id", "")
        if cid and cid in seen_chunks:
            continue
        seen_chunks.add(cid)
        deduped_clauses.append(c)

    return ClaimRehearsalResponse(
        rehearsal_id=f"rehearsal_{uuid.uuid4().hex[:12]}",
        policy_id=policy.fingerprint,
        policy_name=policy.filename,
        readiness_status=readiness_status,
        headline=headline,
        executive_summary=executive_summary,
        relevant_conditions=relevant_conditions,
        financial_breakdown=fin_breakdown,
        supporting_clauses=deduped_clauses,
        missing_information=missing_info,
        unresolved_assumptions=unresolved_assumptions,
        questions_to_ask_tpa=questions_to_ask,
        checklist=checklist_items,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
