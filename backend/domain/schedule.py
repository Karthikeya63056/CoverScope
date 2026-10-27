"""Domain models, extraction pipeline, and association logic for Policy Schedules.

Extracts customer-specific policy certificates, links fields to verbatim evidence,
safely associates schedules with base policy wordings, and detects conflicts.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Sequence
from pydantic import BaseModel, ConfigDict, Field

from backend.domain.enums import DocumentAssociationStatus, ScheduleFieldStatus
from backend.qa.workflow import ProcessedPolicy


class InsuredMember(BaseModel):
    """Insured individual named in the policy schedule."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    member_id: str
    name: str
    age: int | None = Field(default=None, ge=0, le=120)
    relation: str | None = None
    is_primary: bool = False


class ExtractedScheduleField(BaseModel):
    """Single evidence-grounded field extracted from a policy schedule."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    field_key: str
    label: str
    value: Any
    normalized_display: str
    source_page: int
    exact_quote: str
    status: ScheduleFieldStatus = ScheduleFieldStatus.EVIDENCE_GROUNDED
    review_reasons: tuple[str, ...] = ()


class PolicySchedule(BaseModel):
    """Structured representation of an issued Policy Schedule or Certificate of Insurance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schedule_id: str
    filename: str
    document_fingerprint: str
    associated_policy_fingerprint: str | None = None
    association_status: DocumentAssociationStatus = DocumentAssociationStatus.UNASSOCIATED

    insurer_name: str | None = None
    product_name: str | None = None
    product_variant: str | None = None
    policy_version_or_uin: str | None = None
    policy_number_masked: str | None = None
    inception_date: str | None = None
    expiry_date: str | None = None
    sum_insured: float | None = None
    voluntary_deductible: float | None = None

    members: tuple[InsuredMember, ...] = ()
    optional_riders: tuple[str, ...] = ()
    fields: tuple[ExtractedScheduleField, ...] = ()
    conflicts: tuple[str, ...] = ()
    unresolved_conditions: tuple[str, ...] = ()
    endorsement_policy_refs: tuple[str, ...] = ()
    raw_text_summary: str = ""


# -----------------------------------------------------------------------------
# Pattern matching regexes for Indian Policy Schedules
# -----------------------------------------------------------------------------
_INSURER_PATTERNS = [
    (re.compile(r"HDFC\s+ERGO\s+General\s+Insurance", re.IGNORECASE), "HDFC ERGO General Insurance"),
    (re.compile(r"Star\s+Health\s+and\s+Allied\s+Insurance", re.IGNORECASE), "Star Health & Allied Insurance"),
    (re.compile(r"Care\s+Health\s+Insurance", re.IGNORECASE), "Care Health Insurance"),
    (re.compile(r"Niva\s+Bupa\s+Health\s+Insurance", re.IGNORECASE), "Niva Bupa Health Insurance"),
    (re.compile(r"ICICI\s+Lombard\s+General\s+Insurance", re.IGNORECASE), "ICICI Lombard General Insurance"),
]

_PRODUCT_PATTERNS = [
    (re.compile(r"Optima\s+Secure", re.IGNORECASE), "Optima Secure"),
    (re.compile(r"Star\s+Comprehensive\s+Insurance\s+Policy", re.IGNORECASE), "Star Comprehensive Insurance Policy"),
    (re.compile(r"Comprehensive\s+Insurance\s+Policy", re.IGNORECASE), "Star Comprehensive Insurance Policy"),
    (re.compile(r"ReAssure\s*(?:2\.0)?", re.IGNORECASE), "ReAssure 2.0"),
    (re.compile(r"Care\s+Advantage", re.IGNORECASE), "Care Advantage"),
    (re.compile(r"Care\s+Classic", re.IGNORECASE), "Care Classic"),
]

_POLICY_NUM_RE = re.compile(r"(?:Policy\s*(?:No|Number|Certificate\s*No)[\s.:]+)([A-Z0-9\/\-_]{6,30})", re.IGNORECASE)
_DATE_RANGE_RE = re.compile(
    r"(?:Period\s+of\s+Insurance|Policy\s+Period|Duration)[\s.:]+(?:From[\s.:]+)?(\d{1,2}[-\/\.][A-Za-z0-9]+[-\/\.]\d{2,4})\s+(?:To|until|till)[\s.:]+(\d{1,2}[-\/\.][A-Za-z0-9]+[-\/\.]\d{2,4})",
    re.IGNORECASE,
)
_SUM_INSURED_RE = re.compile(
    r"(?:Sum\s+Insured|Coverage\s+Amount)(?:\s*\([A-Za-z]+\))?[\s.:]+(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{2})?)",
    re.IGNORECASE,
)
_DEDUCTIBLE_RE = re.compile(
    r"(?:Voluntary\s+Deductible|Deductible)(?:\s*\([A-Za-z]+\))?[\s.:]+(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{2})?)",
    re.IGNORECASE,
)

_RIDER_PATTERNS = [
    (re.compile(r"(?:Reduction\s+in\s+PED\s+Waiting\s+Period|PED\s+Buy-?Back|Modification\s+of\s+PED\s+Waiting\s+Period|Pre-Existing\s+Disease\s+Waiting\s+Period\s+Modification)", re.IGNORECASE), "Pre-Existing Disease (PED) Waiting Period Modification Rider"),
    (re.compile(r"(?:Hospital\s+(?:Daily\s+)?Cash|Daily\s+Hospital\s+Allowance)", re.IGNORECASE), "Hospital Daily Cash Rider"),
    (re.compile(r"(?:Critical\s+Illness\s+(?:Cover|Rider)|Major\s+Illness\s+Benefit)", re.IGNORECASE), "Critical Illness Optional Cover"),
    (re.compile(r"(?:Co-?Payment\s+Waiver|Waiver\s+of\s+Co-?Payment)", re.IGNORECASE), "Co-Payment Waiver Endorsement"),
]

_VARIANT_RE = re.compile(
    r"(?:Plan|Variant|Tier|Option)[\s.:]+(Silver|Gold|Platinum|Titanium|Diamond|Bronze|Basic|Plus|Pro|Smart|Elite|Executive|Premier|Base)",
    re.IGNORECASE,
)
_UIN_RE = re.compile(
    r"(?:UIN|Unique\s+Identification\s+No|IRDAI\s+UIN)[\s.:]+([A-Z0-9\/\-]{8,30})",
    re.IGNORECASE,
)
_ENDORSEMENT_POLICY_REF_RE = re.compile(
    r"Endorsement[\s\w]*?(?:Policy\s*(?:No|Number)|applicable\s+to\s+Policy)[\s.:]+([A-Z0-9\/\-_]{6,30})",
    re.IGNORECASE,
)


def _normalize_date_str(raw: str) -> str | None:
    """Safely parse various date formats into ISO YYYY-MM-DD."""
    raw = raw.strip()
    # Try ISO
    try:
        return date.fromisoformat(raw).isoformat()
    except Exception:
        pass

    # Split on -, /, .
    parts = re.split(r"[-/\.]", raw)
    if len(parts) == 3:
        d_str, m_str, y_str = parts[0], parts[1], parts[2]
        if len(y_str) == 2:
            y_str = "20" + y_str
        # Check month name
        month_names = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        try:
            m_val = month_names.get(m_str.lower()[:3]) or int(m_str)
            d_val = int(d_str)
            y_val = int(y_str)
            return date(y_val, m_val, d_val).isoformat()
        except Exception:
            pass
    return None


def mask_policy_number(raw_num: str) -> str:
    """Mask sensitive policy number preserving only initial prefix and trailing 4 chars."""
    clean = re.sub(r"\s+", "", raw_num)
    if len(clean) <= 6:
        return "****"
    prefix = clean[:2]
    suffix = clean[-4:]
    masked_mid = "*" * min(6, len(clean) - 6)
    return f"{prefix}-{masked_mid}-{suffix}"


class PolicyScheduleExtractor:
    """Deterministic, evidence-grounded parser for Policy Schedules and Certificates."""

    def extract(self, schedule_policy: ProcessedPolicy) -> PolicySchedule:
        """Extract structured schedule fields from processed schedule document."""
        fields: list[ExtractedScheduleField] = []
        conflicts: list[str] = []

        insurer_name: str | None = None
        product_name: str | None = None
        product_variant: str | None = None
        policy_version_or_uin: str | None = None
        policy_number_masked: str | None = None
        inception_date: str | None = None
        expiry_date: str | None = None
        sum_insured: float | None = None
        voluntary_deductible: float | None = None
        riders: list[str] = []
        members: list[InsuredMember] = []
        endorsement_refs: list[str] = []

        all_text = ""
        for page_idx, chunk in enumerate(schedule_policy.chunks):
            p_num = chunk.page_number
            text = chunk.text
            all_text += text + "\n"

            # 1. Insurer
            if not insurer_name:
                for pat, name in _INSURER_PATTERNS:
                    m = pat.search(text)
                    if m:
                        insurer_name = name
                        fields.append(
                            ExtractedScheduleField(
                                field_key="insurer_name",
                                label="Issuing Insurer",
                                value=name,
                                normalized_display=name,
                                source_page=p_num,
                                exact_quote=m.group(0),
                                status=ScheduleFieldStatus.EVIDENCE_GROUNDED,
                            )
                        )
                        break

            # 2. Product Name & Variant
            if not product_name:
                for pat, name in _PRODUCT_PATTERNS:
                    m = pat.search(text)
                    if m:
                        product_name = name
                        fields.append(
                            ExtractedScheduleField(
                                field_key="product_name",
                                label="Insurance Plan / Product",
                                value=name,
                                normalized_display=name,
                                source_page=p_num,
                                exact_quote=m.group(0),
                                status=ScheduleFieldStatus.EVIDENCE_GROUNDED,
                            )
                        )
                        break

            if not product_variant:
                vm = _VARIANT_RE.search(text)
                if vm:
                    product_variant = vm.group(1).capitalize()
                    fields.append(
                        ExtractedScheduleField(
                            field_key="product_variant",
                            label="Product Variant / Tier",
                            value=product_variant,
                            normalized_display=product_variant,
                            source_page=p_num,
                            exact_quote=vm.group(0),
                            status=ScheduleFieldStatus.EVIDENCE_GROUNDED,
                        )
                    )

            if not policy_version_or_uin:
                uin_m = _UIN_RE.search(text)
                if uin_m:
                    policy_version_or_uin = uin_m.group(1).upper()
                    fields.append(
                        ExtractedScheduleField(
                            field_key="policy_uin",
                            label="Policy UIN / Identifier",
                            value=policy_version_or_uin,
                            normalized_display=policy_version_or_uin,
                            source_page=p_num,
                            exact_quote=uin_m.group(0),
                            status=ScheduleFieldStatus.EVIDENCE_GROUNDED,
                        )
                    )

            # Check for endorsement policy references
            for em in _ENDORSEMENT_POLICY_REF_RE.finditer(text):
                eref = em.group(1).strip()
                if eref not in endorsement_refs:
                    endorsement_refs.append(eref)

            # 3. Policy Number (Masked)
            if not policy_number_masked:
                m = _POLICY_NUM_RE.search(text)
                if m:
                    raw_num = m.group(1).strip()
                    policy_number_masked = mask_policy_number(raw_num)
                    safe_quote = m.group(0).replace(raw_num, policy_number_masked)
                    fields.append(
                        ExtractedScheduleField(
                            field_key="policy_number",
                            label="Policy / Certificate Number",
                            value=policy_number_masked,
                            normalized_display=policy_number_masked,
                            source_page=p_num,
                            exact_quote=safe_quote,
                            status=ScheduleFieldStatus.EVIDENCE_GROUNDED,
                        )
                    )

            # 4. Period of Insurance
            if not inception_date or not expiry_date:
                m = _DATE_RANGE_RE.search(text)
                if m:
                    raw_from = m.group(1).strip()
                    raw_to = m.group(2).strip()
                    d_from = _normalize_date_str(raw_from)
                    d_to = _normalize_date_str(raw_to)
                    if d_from and d_to:
                        inception_date = d_from
                        expiry_date = d_to
                        fields.append(
                            ExtractedScheduleField(
                                field_key="policy_period",
                                label="Policy Period (Inception to Expiry)",
                                value={"from": d_from, "to": d_to},
                                normalized_display=f"{d_from} to {d_to}",
                                source_page=p_num,
                                exact_quote=m.group(0),
                                status=ScheduleFieldStatus.EVIDENCE_GROUNDED,
                            )
                        )

            # 5. Sum Insured
            if sum_insured is None:
                m = _SUM_INSURED_RE.search(text)
                if m:
                    raw_val = m.group(1).replace(",", "").strip()
                    try:
                        val = float(raw_val)
                        sum_insured = val
                        fields.append(
                            ExtractedScheduleField(
                                field_key="sum_insured",
                                label="Sum Insured",
                                value=val,
                                normalized_display=f"₹{val:,.0f}",
                                source_page=p_num,
                                exact_quote=m.group(0),
                                status=ScheduleFieldStatus.EVIDENCE_GROUNDED,
                            )
                        )
                    except ValueError:
                        pass

            # 6. Voluntary Deductible
            if voluntary_deductible is None:
                m = _DEDUCTIBLE_RE.search(text)
                if m:
                    raw_val = m.group(1).replace(",", "").strip()
                    try:
                        val = float(raw_val)
                        voluntary_deductible = val
                        fields.append(
                            ExtractedScheduleField(
                                field_key="voluntary_deductible",
                                label="Voluntary Deductible",
                                value=val,
                                normalized_display=f"₹{val:,.0f}",
                                source_page=p_num,
                                exact_quote=m.group(0),
                                status=ScheduleFieldStatus.EVIDENCE_GROUNDED,
                            )
                        )
                    except ValueError:
                        pass

            # 7. Optional Riders & Endorsements
            for pat, rider_name in _RIDER_PATTERNS:
                m = pat.search(text)
                if m and rider_name not in riders:
                    riders.append(rider_name)
                    fields.append(
                        ExtractedScheduleField(
                            field_key=f"rider_{len(riders)}",
                            label="Elected Optional Rider",
                            value=rider_name,
                            normalized_display=rider_name,
                            source_page=p_num,
                            exact_quote=m.group(0),
                            status=ScheduleFieldStatus.EVIDENCE_GROUNDED,
                        )
                    )

            # 8. Insured Members
            member_lines = self._extract_member_lines(text)
            for m_name, m_age, m_rel in member_lines:
                if not any(mem.name == m_name for mem in members):
                    m_id = f"mem_{len(members) + 1}"
                    is_prim = len(members) == 0 or (m_rel and "self" in m_rel.lower())
                    member_obj = InsuredMember(
                        member_id=m_id,
                        name=m_name,
                        age=m_age,
                        relation=m_rel,
                        is_primary=is_prim,
                    )
                    members.append(member_obj)
                    fields.append(
                        ExtractedScheduleField(
                            field_key=f"member_{m_id}",
                            label=f"Insured Member: {m_name}",
                            value={"name": m_name, "age": m_age, "relation": m_rel},
                            normalized_display=f"{m_name} (Age: {m_age if m_age is not None else '?'}, Relation: {m_rel or 'Self'})",
                            source_page=p_num,
                            exact_quote=f"{m_name} | Age: {m_age}",
                            status=ScheduleFieldStatus.EVIDENCE_GROUNDED,
                        )
                    )

        # Build raw text summary
        summary = f"Schedule document: {schedule_policy.filename} ({schedule_policy.page_count} pages). "
        if insurer_name:
            summary += f"Insurer: {insurer_name}. "
        if product_name:
            summary += f"Product: {product_name}. "
        if policy_number_masked:
            summary += f"Policy: {policy_number_masked}. "
        if members:
            summary += f"Members: {len(members)} named. "
        if riders:
            summary += f"Riders: {len(riders)} active."

        return PolicySchedule(
            schedule_id=f"sch_{schedule_policy.fingerprint[:8]}",
            filename=schedule_policy.filename,
            document_fingerprint=schedule_policy.fingerprint,
            insurer_name=insurer_name,
            product_name=product_name,
            product_variant=product_variant,
            policy_version_or_uin=policy_version_or_uin,
            policy_number_masked=policy_number_masked,
            inception_date=inception_date,
            expiry_date=expiry_date,
            sum_insured=sum_insured,
            voluntary_deductible=voluntary_deductible,
            members=tuple(members),
            optional_riders=tuple(riders),
            fields=tuple(fields),
            conflicts=tuple(conflicts),
            endorsement_policy_refs=tuple(endorsement_refs),
            raw_text_summary=summary,
        )

    def _extract_member_lines(self, text: str) -> list[tuple[str, int | None, str | None]]:
        """Parse structured tabular lines for insured member entries."""
        results: list[tuple[str, int | None, str | None]] = []

        # Common format: "Insured Name: John Doe | Age: 45 | Relation: Self"
        # Or table row: "1. John Doe | Male | 45 Years | Self"
        # Or: "Mr/Mrs/Ms/Dr Name ... Age: XX"
        lines = text.splitlines()
        member_pattern = re.compile(
            r"(?:(?:\d+[\.\)]|\*|-)?\s*)?(?:(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?)\s+([A-Za-z\s]{3,30})|Name[\s.:]+([A-Za-z\s]{3,30})|([A-Za-z\s]{3,30}))\s*(?:[\|,;]|\s+)\s*(?:Age|DOB)[\s.:]+(\d{1,2})(?:[^\n\r]*?Relation(?:ship)?[\s.:]+([A-Za-z]+))?",
            re.IGNORECASE,
        )

        for line in lines:
            m = member_pattern.search(line)
            if m:
                name = (m.group(1) or m.group(2) or m.group(3) or "").strip()
                age_str = m.group(4)
                rel_str = (m.group(5) or "Self").strip()
                try:
                    age = int(age_str)
                except (ValueError, TypeError):
                    age = None
                if name and len(name) > 2:
                    results.append((name, age, rel_str))

        # Secondary fallback: "Member: [Name], Age: [Age]"
        if not results:
            fallback_pattern = re.compile(r"Member[\s.:]+([A-Za-z\s]{3,25})[,\s]+Age[\s.:]+(\d{1,2})", re.IGNORECASE)
            for line in lines:
                m = fallback_pattern.search(line)
                if m:
                    name = m.group(1).strip()
                    try:
                        age = int(m.group(2))
                    except ValueError:
                        age = None
                    results.append((name, age, "Self"))

        return results


class PolicyScheduleAssociator:
    """Evaluates compatibility between a Policy Schedule and a Policy Wording."""

    def evaluate_association(
        self,
        schedule: PolicySchedule,
        policy: ProcessedPolicy,
    ) -> tuple[DocumentAssociationStatus, list[str]]:
        """Determine whether schedule can safely associate with the given policy wording.

        Returns (status, reasons/conflicts).
        """
        conflicts: list[str] = []
        unresolved: list[str] = []
        policy_text_lower = " ".join(c.text.lower() for c in policy.chunks[:15])

        # 1. Insurer compatibility
        generic_insurer_tokens = {"general", "insurance", "company", "limited", "ltd", "health", "allied", "life", "corp", "co", "india"}
        if schedule.insurer_name:
            sch_ins = schedule.insurer_name.lower()
            key_tokens = [t for t in sch_ins.split() if len(t) > 2 and t not in generic_insurer_tokens]
            if key_tokens and not any(t in policy_text_lower for t in key_tokens):
                conflicts.append(
                    f"Insurer mismatch: Schedule specifies '{schedule.insurer_name}', "
                    f"which was not found in wording document '{policy.filename}'."
                )
        else:
            unresolved.append("Issuing insurer not identified on schedule document.")

        # 2. Product name & same-insurer different product compatibility
        generic_product_tokens = {"insurance", "policy", "plan", "product", "cover"}
        if schedule.product_name:
            sch_prod = schedule.product_name.lower()
            prod_tokens = [t for t in sch_prod.split() if len(t) > 3 and t not in generic_product_tokens]
            if prod_tokens and not any(t in policy_text_lower for t in prod_tokens):
                conflicts.append(
                    f"Product mismatch: Schedule specifies plan '{schedule.product_name}', "
                    f"which does not match wording document '{policy.filename}'."
                )

            # Check for known different products under the same insurer
            for pat, known_prod in _PRODUCT_PATTERNS:
                if pat.search(policy_text_lower) and known_prod.lower() != sch_prod and not any(t in sch_prod for t in known_prod.lower().split() if len(t) > 3 and t not in generic_product_tokens):
                    if not any(t in policy_text_lower for t in prod_tokens):
                        conflicts.append(
                            f"Product conflict: Schedule specifies '{schedule.product_name}' but policy wording is for '{known_prod}'."
                        )
                        break
        else:
            unresolved.append("Schedule product name not identified; cannot verify policy plan match.")

        # 3. Product variant / tier compatibility
        if schedule.product_variant:
            sch_var = schedule.product_variant.lower()
            if "only " in policy_text_lower and sch_var not in policy_text_lower:
                conflicts.append(
                    f"Product variant mismatch: Schedule specifies variant '{schedule.product_variant}', "
                    f"which contradicts the plan variants established in '{policy.filename}'."
                )
            elif sch_var not in policy_text_lower:
                unresolved.append(
                    f"Product variant '{schedule.product_variant}' identified on schedule could not be confirmed in base policy wording."
                )

        # 4. Endorsement policy reference consistency
        if schedule.endorsement_policy_refs:
            for ref in schedule.endorsement_policy_refs:
                masked_ref = mask_policy_number(ref)
                if schedule.policy_number_masked and masked_ref != schedule.policy_number_masked:
                    conflicts.append(
                        f"Endorsement conflict: Rider endorsement explicitly references policy number '{masked_ref}', "
                        f"which contradicts the schedule policy number '{schedule.policy_number_masked}'."
                    )

        # 5. UIN / Policy version consistency
        if schedule.policy_version_or_uin:
            uin_m = _UIN_RE.search(policy_text_lower)
            if uin_m:
                wording_uin = uin_m.group(1).upper()
                if schedule.policy_version_or_uin.upper() != wording_uin:
                    conflicts.append(
                        f"UIN mismatch: Schedule specifies UIN '{schedule.policy_version_or_uin}', "
                        f"which does not match wording UIN '{wording_uin}'."
                    )

        if conflicts:
            return (DocumentAssociationStatus.CONFLICT_DETECTED, conflicts)
        if unresolved:
            return (DocumentAssociationStatus.NEEDS_REVIEW, unresolved)

        # If variant and version are confirmed in text
        if (
            schedule.product_variant
            and schedule.product_variant.lower() in policy_text_lower
            and schedule.policy_version_or_uin
        ):
            return (
                DocumentAssociationStatus.VERIFIED_COMPATIBILITY,
                ["Insurer, product, variant, and policy version mutually verified with base wording."],
            )

        reasons = ["Document metadata and product identifiers are mutually consistent."]
        return (DocumentAssociationStatus.SUGGESTED_MATCH, reasons)

    def confirm_association(
        self,
        schedule: PolicySchedule,
    ) -> PolicySchedule:
        """Explicitly confirm association, strictly rejecting override if an actual conflict exists."""
        if schedule.association_status == DocumentAssociationStatus.CONFLICT_DETECTED:
            rejection_note = "User confirmation rejected: Document conflict cannot be overridden while contractual contradictions persist."
            updated_conflicts = tuple(dict.fromkeys(list(schedule.conflicts) + [rejection_note]))
            return schedule.model_copy(update={
                "conflicts": updated_conflicts,
            })

        return schedule.model_copy(update={
            "association_status": DocumentAssociationStatus.USER_CONFIRMED,
        })
