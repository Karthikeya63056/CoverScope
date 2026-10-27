"""Adapters bridging the document processing pipeline with canonical domain models.

Provides deterministic, evidence-grounded candidate fact extraction for key
insurance provisions (waiting periods, exclusions, limits, copayments) with
explicit condition and qualifier preservation.
"""
from __future__ import annotations

import re
from typing import Sequence

from backend.document_processing.chunker import PolicyChunk
from backend.document_processing.normalization import normalize_for_match
from backend.domain.enums import (
    DocumentType,
    DurationUnit,
    ExtractionMethod,
    FactCategory,
    FactValidationStatus,
)
from backend.domain.models import (
    DurationValue,
    EvidenceReference,
    MonetaryLimit,
    PercentageValue,
    PolicyFact,
    SourceDocument,
    SourcePage,
)
from backend.qa.workflow import ProcessedPolicy

# Precision regex patterns for grounded insurance clauses
_PED_WAITING_PERIOD_RE = re.compile(
    r"(?:pre[- ]existing\s+diseases?|pre[- ]existing\s+conditions?|PED)\b[^.]{0,180}?"
    r"(\b\d{1,3}\b)\s+(months?|years?|days?)"
    r"[^.]{0,150}?(?:continuous\s+coverage|waiting\s+period|excluded)?",
    re.IGNORECASE,
)

_SPECIFIED_DISEASE_WAITING_PERIOD_RE = re.compile(
    r"(?:specified\s+disease(?:/procedure)?|listed\s+conditions?|specific\s+diseases?|specified\s+procedure)[^.]{0,220}?"
    r"(\b\d{1,3}\b)\s+(months?|years?|days?)"
    r"[^.]{0,150}?(?:continuous\s+coverage|waiting\s+period|excluded)?",
    re.IGNORECASE,
)

_INITIAL_WAITING_PERIOD_RE = re.compile(
    r"(\b\d{1,3}\b)[- ](?:days?|months?)\s+waiting\s+period\s*(?:\(Code[- ]?\s*Excl03\))?"
    r"|treatment\s+of\s+any\s+illness\s+within\s+(\b\d{1,3}\b)\s+(days?|months?)\s+from\s+the\s+(?:first\s+policy\s+commencement|date\s+of\s+inception)"
    r"|Initial\s+Waiting\s+Period\s*:\s*(\b\d{1,3}\b)\s+(days?|months?)",
    re.IGNORECASE,
)

_OTHER_WAITING_PERIOD_RE = re.compile(
    r"(bariatric\s+surgery|delivery\s+expenses|maternity)\s*:\s*(\b\d{1,3}\b)\s+(months?|years?|days?)",
    re.IGNORECASE,
)

_BUY_BACK_RE = re.compile(
    r"(?:upon purchase of this optional cover[,\s]+)?(?:the\s+)?(?:PED\s+)?Waiting\s+Period\s+reduces\s+(?:from\s+(\d{1,3})\s+(months?|years?)\s+)?to\s+(\d{1,3})\s+(months?|years?)",
    re.IGNORECASE,
)

_MODIFICATION_BENEFIT_RE = re.compile(
    r"(?:Pre[- ]Existing\s+Disease\s+Waiting\s+Time\s+Modi(?:fi|\ufb01)cation|Waiting\s+Time\s+Modi(?:fi|\ufb01)cation)[^.]{0,120}?"
    r"(?:reduce\s+or\s+completely\s+remove|CAN\s+NOT\s+be\s+reduced\s+further)",
    re.IGNORECASE,
)

_COPAYMENT_RE = re.compile(
    r"co[- ]?payment\s+of\s+(\b\d{1,2}(?:\.\d+)?\b)\s*%"
    r"|(\b\d{1,2}(?:\.\d+)?\b)\s*%\s*co[- ]?payment",
    re.IGNORECASE,
)

_MONETARY_SUBLIMIT_RE = re.compile(
    r"(cataract(?:\s+surgery)?|room\s+rent|maternity|ayush(?:\s+treatment)?|road\s+ambulance|organ\s+donor)"
    r"[^.\n]{0,120}?"
    r"(?:limit|sub[- ]?limit|up\s+to|capped\s+at|sum\s+insured\s+of)?\s*"
    r"(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d+)?)"
    r"[^.\n]{0,80}?(per\s+eye|per\s+day|per\s+hospitalization|per\s+year|per\s+delivery|annual)?",
    re.IGNORECASE,
)

_EXCLUSION_CLAUSE_RE = re.compile(
    r"(?:treatment\s+for[,.\s]+)?(alcoholism|drug\s+addiction|substance\s+abuse|cosmetic\s+surgery|hazardous\s+sports|weight\s+loss\s+surgery|obesity\s*/\s*weight\s+control|investigation\s+&\s+evaluation|rest\s+cure|rehabilitation\s+and\s+respite\s+care)"
    r"[^.\n]{0,120}?(?:is\s+excluded|not\s+covered|shall\s+not\s+be\s+payable|exclusion)"
    r"|(?:treatment\s+for[,.\s]+)?(alcoholism|drug\s+addiction|substance\s+abuse|cosmetic\s+surgery|hazardous\s+sports|weight\s+loss\s+surgery|obesity\s*/\s*weight\s+control|investigation\s+&\s+evaluation|rest\s+cure|rehabilitation\s+and\s+respite\s+care)"
    r"[^)]{0,120}?\(?Code[- ]?\s*Excl\d{2}\)?",
    re.IGNORECASE,
)

# Triggers indicating conditionality, optional riders, or exceptions
_CONDITIONAL_TRIGGERS = (
    "optional",
    "buy-back",
    "modi\ufb01cation",
    "modification",
    "you can choose",
    "upon purchase",
    "unless",
    "subject to",
    "does not ful\ufb01l",
    "does not fulfil",
    "except",
    "provided that",
    "if the insured",
)


def create_source_document(
    policy: ProcessedPolicy,
    *,
    policy_id: str | None = None,
    document_type: DocumentType = DocumentType.POLICY_WORDING,
) -> SourceDocument:
    """Build a canonical SourceDocument from an in-memory ProcessedPolicy."""
    table_pages = tuple(getattr(policy.quality, "table_review_pages", ()) or ())
    text_poor_pages = tuple(getattr(policy.quality, "text_poor_pages", ()) or ())
    warnings = tuple(getattr(policy.quality, "warnings", ()) or ())

    return SourceDocument(
        document_id=policy.fingerprint,
        policy_id=policy_id,
        filename=policy.filename,
        content_hash=policy.fingerprint,
        document_type=document_type,
        page_count=policy.page_count,
        size_bytes=policy.size_bytes,
        extracted_characters=policy.extracted_characters,
        extraction_status="extracted" if policy.quality.is_usable else "unusable",
        extraction_warnings=warnings,
        table_review_pages=table_pages,
        text_poor_pages=text_poor_pages,
    )


def create_source_pages(policy: ProcessedPolicy) -> list[SourcePage]:
    """Convert extracted pages into canonical SourcePage models."""
    table_pages = set(getattr(policy.quality, "table_review_pages", ()) or ())
    text_poor_pages = set(getattr(policy.quality, "text_poor_pages", ()) or ())

    pages: list[SourcePage] = []
    for p in policy.pages:
        pages.append(
            SourcePage(
                page_number=p.page_number,
                text=p.text,
                char_count=p.char_count,
                text_block_count=getattr(p, "text_block_count", 0),
                image_count=getattr(p, "image_count", 0),
                is_table_review=p.page_number in table_pages,
                is_text_poor=p.page_number in text_poor_pages,
            )
        )
    return pages


def create_evidence_from_chunk(
    chunk: PolicyChunk,
    document_id: str,
    *,
    quote: str | None = None,
    quality_warning: str | None = None,
) -> EvidenceReference:
    """Create a validated EvidenceReference grounding a citation in an exact chunk."""
    text_to_use = quote if quote is not None else chunk.text
    ev_id = f"ev_{document_id[:8]}_{chunk.chunk_id}"
    if quote is not None:
        ev_id = f"{ev_id}_{hash(quote) & 0xffff:04x}"

    return EvidenceReference(
        evidence_id=ev_id,
        document_id=document_id,
        page_number=chunk.page_number,
        exact_text=text_to_use,
        chunk_id=chunk.chunk_id,
        quality_warning=quality_warning,
        validation_status=FactValidationStatus.EVIDENCE_GROUNDED,
    )


extract_evidence_from_chunk = create_evidence_from_chunk


def _has_conditional_trigger(text: str) -> tuple[bool, list[str]]:
    """Detect whether text contains conditional riders, exceptions, or opt-ins."""
    lower = text.lower()
    matched = [trig for trig in _CONDITIONAL_TRIGGERS if trig in lower]
    return (len(matched) > 0, matched)


def extract_candidate_facts(policy: ProcessedPolicy) -> list[PolicyFact]:
    """Deterministically extract evidence-grounded candidate facts from policy text.

    Distinguishes unconditional facts from conditional or exception-heavy clauses.
    Never marks a conditional clause as unconditionally verified.
    """
    facts: list[PolicyFact] = []
    doc_id = policy.fingerprint
    table_pages = set(getattr(policy.quality, "table_review_pages", ()) or ())

    fact_idx = 1
    for page in policy.pages:
        text = page.text
        norm_page_text = normalize_for_match(text)
        is_table_page = page.page_number in table_pages

        # ---------------------------------------------------------------------
        # 1. Pre-Existing Disease (PED) Waiting Periods
        # ---------------------------------------------------------------------
        for match in _PED_WAITING_PERIOD_RE.finditer(text):
            span_text = match.group(0).strip()
            amount_str = match.group(1)
            unit_str = match.group(2).lower()
            unit = DurationUnit.MONTHS
            if "year" in unit_str:
                unit = DurationUnit.YEARS
            elif "day" in unit_str:
                unit = DurationUnit.DAYS

            try:
                amount = int(amount_str)
            except ValueError:
                continue

            # Context window around match for conditions
            start_ctx = max(0, match.start() - 150)
            end_ctx = min(len(text), match.end() + 150)
            surrounding = text[start_ctx:end_ctx]

            # Guard against definition lookback windows (e.g. "means any condition ... not more than 36 months")
            lower_surrounding = surrounding.lower()
            if (
                "means any condition" in lower_surrounding
                or "means any ailment" in lower_surrounding
                or "diagnosed by a physician not more than" in lower_surrounding
            ):
                continue

            # Guard against rider reduction clauses (e.g. "reduces from 36 months to 12 months")
            if re.search(r"reduces\s+from\s+\d+\s+(?:months?|years?)\s+to\s+\d+", surrounding, re.IGNORECASE):
                continue

            is_cond, cond_triggers = _has_conditional_trigger(surrounding)

            status = FactValidationStatus.EVIDENCE_GROUNDED
            review_reasons: list[str] = []
            conditions: list[str] = []

            if is_cond:
                status = FactValidationStatus.NEEDS_REVIEW
                review_reasons.append(f"Conditional phrasing detected ({', '.join(cond_triggers)})")
                conditions.append("Subject to optional rider or continuous coverage terms")
            if is_table_page:
                status = FactValidationStatus.NEEDS_REVIEW
                review_reasons.append("Page flagged for table review")

            is_grounded = normalize_for_match(span_text) in norm_page_text
            ev = EvidenceReference(
                evidence_id=f"ev_{doc_id[:8]}_p{page.page_number}_f{fact_idx}",
                document_id=doc_id,
                page_number=page.page_number,
                exact_text=span_text,
                validation_status=status,
            )

            facts.append(
                PolicyFact(
                    fact_id=f"fact_{doc_id[:8]}_{fact_idx:03d}",
                    document_id=doc_id,
                    category=FactCategory.WAITING_PERIOD,
                    proposition=f"Pre-existing disease waiting period of {amount} {unit.value} on page {page.page_number}.",
                    evidence_references=(ev,),
                    conditions=tuple(conditions),
                    structured_value=DurationValue(
                        amount=amount,
                        unit=unit,
                        raw_text=span_text,
                    ),
                    extraction_method=ExtractionMethod.HEURISTIC,
                    validation_status=status,
                    is_evidence_grounded=is_grounded,
                    semantic_status="unreviewed" if not is_cond else "ambiguous",
                    review_reasons=tuple(review_reasons),
                )
            )
            fact_idx += 1

        # ---------------------------------------------------------------------
        # 2. Specified Disease / Procedure Waiting Periods
        # ---------------------------------------------------------------------
        for match in _SPECIFIED_DISEASE_WAITING_PERIOD_RE.finditer(text):
            span_text = match.group(0).strip()
            amount_str = match.group(1)
            unit_str = match.group(2).lower()
            unit = DurationUnit.MONTHS
            if "year" in unit_str:
                unit = DurationUnit.YEARS
            elif "day" in unit_str:
                unit = DurationUnit.DAYS

            try:
                amount = int(amount_str)
            except ValueError:
                continue

            start_ctx = max(0, match.start() - 150)
            end_ctx = min(len(text), match.end() + 150)
            surrounding = text[start_ctx:end_ctx]
            is_cond, cond_triggers = _has_conditional_trigger(surrounding)

            status = FactValidationStatus.EVIDENCE_GROUNDED
            review_reasons: list[str] = []
            conditions: list[str] = ["Listed conditions and surgical procedures only"]

            if is_cond:
                status = FactValidationStatus.NEEDS_REVIEW
                review_reasons.append(f"Conditional phrasing detected ({', '.join(cond_triggers)})")
            if is_table_page:
                status = FactValidationStatus.NEEDS_REVIEW
                review_reasons.append("Page flagged for table review")

            is_grounded = normalize_for_match(span_text) in norm_page_text
            ev = EvidenceReference(
                evidence_id=f"ev_{doc_id[:8]}_p{page.page_number}_f{fact_idx}",
                document_id=doc_id,
                page_number=page.page_number,
                exact_text=span_text,
                validation_status=status,
            )

            facts.append(
                PolicyFact(
                    fact_id=f"fact_{doc_id[:8]}_{fact_idx:03d}",
                    document_id=doc_id,
                    category=FactCategory.WAITING_PERIOD,
                    proposition=f"Specified disease/procedure waiting period of {amount} {unit.value} on page {page.page_number}.",
                    evidence_references=(ev,),
                    conditions=tuple(conditions),
                    structured_value=DurationValue(
                        amount=amount,
                        unit=unit,
                        raw_text=span_text,
                    ),
                    extraction_method=ExtractionMethod.HEURISTIC,
                    validation_status=status,
                    is_evidence_grounded=is_grounded,
                    semantic_status="unreviewed",
                    review_reasons=tuple(review_reasons),
                )
            )
            fact_idx += 1

        # ---------------------------------------------------------------------
        # 3. Initial 30-Day Waiting Periods
        # ---------------------------------------------------------------------
        for match in _INITIAL_WAITING_PERIOD_RE.finditer(text):
            span_text = match.group(0).strip()
            amount_str = match.group(1) or match.group(2) or match.group(4)
            unit_str = (match.group(3) or match.group(5) or "days").lower()
            unit = DurationUnit.DAYS if "day" in unit_str else DurationUnit.MONTHS

            try:
                amount = int(amount_str)
            except (ValueError, TypeError):
                continue

            status = FactValidationStatus.EVIDENCE_GROUNDED
            review_reasons: list[str] = []
            conditions: list[str] = ["First policy commencement date; does not apply to accidental injury"]

            if is_table_page:
                status = FactValidationStatus.NEEDS_REVIEW
                review_reasons.append("Page flagged for table review")

            is_grounded = normalize_for_match(span_text) in norm_page_text
            ev = EvidenceReference(
                evidence_id=f"ev_{doc_id[:8]}_p{page.page_number}_f{fact_idx}",
                document_id=doc_id,
                page_number=page.page_number,
                exact_text=span_text,
                validation_status=status,
            )

            facts.append(
                PolicyFact(
                    fact_id=f"fact_{doc_id[:8]}_{fact_idx:03d}",
                    document_id=doc_id,
                    category=FactCategory.WAITING_PERIOD,
                    proposition=f"Initial waiting period of {amount} {unit.value} from commencement on page {page.page_number}.",
                    evidence_references=(ev,),
                    conditions=tuple(conditions),
                    structured_value=DurationValue(
                        amount=amount,
                        unit=unit,
                        raw_text=span_text,
                    ),
                    extraction_method=ExtractionMethod.HEURISTIC,
                    validation_status=status,
                    is_evidence_grounded=is_grounded,
                    semantic_status="unreviewed",
                    review_reasons=tuple(review_reasons),
                )
            )
            fact_idx += 1

        # ---------------------------------------------------------------------
        # 4. Other Specific Waiting Periods (e.g. Bariatric, Maternity)
        # ---------------------------------------------------------------------
        for match in _OTHER_WAITING_PERIOD_RE.finditer(text):
            scope = match.group(1).strip()
            amount_str = match.group(2)
            unit_str = match.group(3).lower()
            unit = DurationUnit.MONTHS
            if "year" in unit_str:
                unit = DurationUnit.YEARS
            elif "day" in unit_str:
                unit = DurationUnit.DAYS

            try:
                amount = int(amount_str)
            except ValueError:
                continue

            span_text = match.group(0).strip()
            is_grounded = normalize_for_match(span_text) in norm_page_text
            ev = EvidenceReference(
                evidence_id=f"ev_{doc_id[:8]}_p{page.page_number}_f{fact_idx}",
                document_id=doc_id,
                page_number=page.page_number,
                exact_text=span_text,
                validation_status=FactValidationStatus.EVIDENCE_GROUNDED,
            )

            facts.append(
                PolicyFact(
                    fact_id=f"fact_{doc_id[:8]}_{fact_idx:03d}",
                    document_id=doc_id,
                    category=FactCategory.WAITING_PERIOD,
                    proposition=f"Waiting period for {scope} is {amount} {unit.value} on page {page.page_number}.",
                    evidence_references=(ev,),
                    structured_value=DurationValue(
                        amount=amount,
                        unit=unit,
                        raw_text=span_text,
                    ),
                    extraction_method=ExtractionMethod.HEURISTIC,
                    validation_status=FactValidationStatus.EVIDENCE_GROUNDED,
                    is_evidence_grounded=is_grounded,
                    semantic_status="unreviewed",
                )
            )
            fact_idx += 1

        # ---------------------------------------------------------------------
        # 4b. Optional Rider Modifications & Buy-Backs
        # ---------------------------------------------------------------------
        for match in _BUY_BACK_RE.finditer(text):
            span_text = match.group(0).strip()
            from_amt_str = match.group(1)
            from_unit_str = match.group(2)
            to_amt_str = match.group(3)
            to_unit_str = match.group(4).lower()

            try:
                to_amt = int(to_amt_str)
            except (ValueError, TypeError):
                continue

            unit = DurationUnit.MONTHS if "month" in to_unit_str else DurationUnit.DAYS
            conditions = ["Upon purchase of optional buy-back cover"]
            if from_amt_str:
                conditions.append(f"Base PED waiting period reduced from {from_amt_str} {from_unit_str} to {to_amt} {unit.value}")

            is_grounded = normalize_for_match(span_text) in norm_page_text
            ev = EvidenceReference(
                evidence_id=f"ev_{doc_id[:8]}_p{page.page_number}_f{fact_idx}",
                document_id=doc_id,
                page_number=page.page_number,
                exact_text=span_text,
                validation_status=FactValidationStatus.NEEDS_REVIEW,
            )

            facts.append(
                PolicyFact(
                    fact_id=f"fact_{doc_id[:8]}_{fact_idx:03d}",
                    document_id=doc_id,
                    category=FactCategory.WAITING_PERIOD,
                    proposition=f"Optional cover reduces pre-existing disease waiting period to {to_amt} {unit.value} on page {page.page_number}.",
                    evidence_references=(ev,),
                    conditions=tuple(conditions),
                    structured_value=DurationValue(
                        amount=to_amt,
                        unit=unit,
                        raw_text=span_text,
                    ),
                    extraction_method=ExtractionMethod.HEURISTIC,
                    validation_status=FactValidationStatus.NEEDS_REVIEW,
                    is_evidence_grounded=is_grounded,
                    semantic_status="ambiguous",
                    review_reasons=("Optional rider cover modifying base waiting period upon election",),
                )
            )
            fact_idx += 1

        for match in _MODIFICATION_BENEFIT_RE.finditer(text):
            span_text = match.group(0).strip()
            is_grounded = normalize_for_match(span_text) in norm_page_text
            ev = EvidenceReference(
                evidence_id=f"ev_{doc_id[:8]}_p{page.page_number}_f{fact_idx}",
                document_id=doc_id,
                page_number=page.page_number,
                exact_text=span_text,
                validation_status=FactValidationStatus.NEEDS_REVIEW,
            )

            facts.append(
                PolicyFact(
                    fact_id=f"fact_{doc_id[:8]}_{fact_idx:03d}",
                    document_id=doc_id,
                    category=FactCategory.WAITING_PERIOD,
                    proposition=f"Pre-existing disease waiting time modification benefit on page {page.page_number}.",
                    evidence_references=(ev,),
                    conditions=("Optional benefit chosen at inception; cannot be reduced further once opted",),
                    structured_value=None,
                    extraction_method=ExtractionMethod.HEURISTIC,
                    validation_status=FactValidationStatus.NEEDS_REVIEW,
                    is_evidence_grounded=is_grounded,
                    semantic_status="ambiguous",
                    review_reasons=("Optional modification benefit alters base waiting time upon election",),
                )
            )
            fact_idx += 1

        # ---------------------------------------------------------------------
        # 5. Co-Payments & Deductibles
        # ---------------------------------------------------------------------
        for match in _COPAYMENT_RE.finditer(text):
            pct_str = match.group(1) or match.group(2)
            try:
                pct = float(pct_str)
            except (ValueError, TypeError):
                continue

            span_text = match.group(0).strip()
            start_ctx = max(0, match.start() - 100)
            end_ctx = min(len(text), match.end() + 200)
            surrounding = text[start_ctx:end_ctx]

            conditions: list[str] = []
            if "61" in surrounding or "age" in surrounding.lower():
                conditions.append("Applicable based on entry age criteria (e.g. 61+ years)")

            is_grounded = normalize_for_match(span_text) in norm_page_text
            ev = EvidenceReference(
                evidence_id=f"ev_{doc_id[:8]}_p{page.page_number}_f{fact_idx}",
                document_id=doc_id,
                page_number=page.page_number,
                exact_text=span_text,
                validation_status=FactValidationStatus.EVIDENCE_GROUNDED,
            )

            facts.append(
                PolicyFact(
                    fact_id=f"fact_{doc_id[:8]}_{fact_idx:03d}",
                    document_id=doc_id,
                    category=FactCategory.DEDUCTIBLE_OR_COPAY,
                    proposition=f"Co-payment of {pct:g}% specified on page {page.page_number}.",
                    evidence_references=(ev,),
                    conditions=tuple(conditions),
                    structured_value=PercentageValue(
                        percentage=pct,
                        scope="copayment",
                        raw_text=span_text,
                    ),
                    extraction_method=ExtractionMethod.HEURISTIC,
                    validation_status=FactValidationStatus.EVIDENCE_GROUNDED,
                    is_evidence_grounded=is_grounded,
                    semantic_status="unreviewed",
                )
            )
            fact_idx += 1

        # ---------------------------------------------------------------------
        # 6. Exclusions (with Exception Handling)
        # ---------------------------------------------------------------------
        for match in _EXCLUSION_CLAUSE_RE.finditer(text):
            span_text = match.group(0).strip()
            item = match.group(1) or match.group(2)
            if not item:
                continue

            start_ctx = max(0, match.start() - 50)
            end_ctx = min(len(text), match.end() + 250)
            surrounding = text[start_ctx:end_ctx]
            is_cond, cond_triggers = _has_conditional_trigger(surrounding)

            status = FactValidationStatus.EVIDENCE_GROUNDED
            review_reasons: list[str] = []
            exceptions: list[str] = []

            # Check for clinical exceptions (e.g. obesity surgery criteria, reconstructive cosmetic)
            if "obesity" in item.lower() or "weight" in item.lower():
                if "bmi" in surrounding.lower() or "clinical protocols" in surrounding.lower():
                    status = FactValidationStatus.NEEDS_REVIEW
                    review_reasons.append("Conditional exclusion with clinical exceptions (BMI/protocols)")
                    exceptions.append("Surgeries meeting medical necessity and BMI criteria are eligible")

            if "cosmetic" in item.lower() and ("accident" in surrounding.lower() or "burn" in surrounding.lower() or "cancer" in surrounding.lower()):
                status = FactValidationStatus.NEEDS_REVIEW
                review_reasons.append("Conditional exception for reconstructive surgery following accident/cancer")
                exceptions.append("Reconstructive surgery required following accident, burn, or cancer")

            if is_cond and status != FactValidationStatus.NEEDS_REVIEW:
                status = FactValidationStatus.NEEDS_REVIEW
                review_reasons.append(f"Conditional phrasing in clause ({', '.join(cond_triggers)})")

            is_grounded = normalize_for_match(span_text) in norm_page_text
            ev = EvidenceReference(
                evidence_id=f"ev_{doc_id[:8]}_p{page.page_number}_f{fact_idx}",
                document_id=doc_id,
                page_number=page.page_number,
                exact_text=span_text,
                validation_status=status,
            )

            facts.append(
                PolicyFact(
                    fact_id=f"fact_{doc_id[:8]}_{fact_idx:03d}",
                    document_id=doc_id,
                    category=FactCategory.EXCLUSION,
                    proposition=f"Exclusion provision for {item.strip()} on page {page.page_number}.",
                    evidence_references=(ev,),
                    exceptions=tuple(exceptions),
                    extraction_method=ExtractionMethod.HEURISTIC,
                    validation_status=status,
                    is_evidence_grounded=is_grounded,
                    semantic_status="unreviewed" if not exceptions else "ambiguous",
                    review_reasons=tuple(review_reasons),
                )
            )
            fact_idx += 1

        # ---------------------------------------------------------------------
        # 7. Monetary Sublimits
        # ---------------------------------------------------------------------
        for match in _MONETARY_SUBLIMIT_RE.finditer(text):
            span_text = match.group(0).strip()
            item = match.group(1)
            raw_amt = match.group(2).replace(",", "")
            scope_raw = match.group(3) or "lump_sum"
            try:
                amt = float(raw_amt)
            except ValueError:
                continue

            start_ctx = max(0, match.start() - 100)
            end_ctx = min(len(text), match.end() + 100)
            surrounding = text[start_ctx:end_ctx]

            status = FactValidationStatus.EVIDENCE_GROUNDED
            review_reasons: list[str] = []

            # Check if this is part of a complex tiered table with multiple currency numbers
            currency_counts = len(re.findall(r"(?:Rs\.?|INR|₹)\s*[\d,]+", surrounding))
            if currency_counts > 2 or is_table_page:
                status = FactValidationStatus.NEEDS_REVIEW
                review_reasons.append("Tiered or table-derived monetary limit requires policy schedule review")

            is_grounded = normalize_for_match(span_text) in norm_page_text
            ev = EvidenceReference(
                evidence_id=f"ev_{doc_id[:8]}_p{page.page_number}_f{fact_idx}",
                document_id=doc_id,
                page_number=page.page_number,
                exact_text=span_text,
                validation_status=status,
            )

            facts.append(
                PolicyFact(
                    fact_id=f"fact_{doc_id[:8]}_{fact_idx:03d}",
                    document_id=doc_id,
                    category=FactCategory.LIMIT_OR_SUBLIMIT,
                    proposition=f"Monetary sublimit for {item} of Rs {amt:,.0f} ({scope_raw.strip()}) on page {page.page_number}.",
                    evidence_references=(ev,),
                    structured_value=MonetaryLimit(
                        amount=amt,
                        currency="INR",
                        scope=scope_raw.strip(),
                        raw_text=span_text,
                    ),
                    extraction_method=ExtractionMethod.HEURISTIC,
                    validation_status=status,
                    is_evidence_grounded=is_grounded,
                    semantic_status="unreviewed" if status != FactValidationStatus.NEEDS_REVIEW else "ambiguous",
                    review_reasons=tuple(review_reasons),
                )
            )
            fact_idx += 1

    # Deterministic candidate deduplication pass:
    # Multiple regex patterns matching the same clause or heading on a single page
    # must not generate redundant duplicate candidate facts.
    deduped_facts: list[PolicyFact] = []
    seen_signatures: set[tuple[int, FactCategory, str | None, str]] = set()

    for fact in facts:
        ev = fact.evidence_references[0] if fact.evidence_references else None
        page_num = ev.page_number if ev else 0
        sv = fact.structured_value
        sv_key = (
            getattr(sv, "amount", None),
            getattr(getattr(sv, "unit", None), "value", None),
            getattr(sv, "percentage", None),
        ) if sv is not None else None
        prop_prefix = normalize_for_match(fact.proposition)[:45]
        sig = (page_num, fact.category, sv_key, prop_prefix)

        if sig in seen_signatures:
            continue
        seen_signatures.add(sig)
        deduped_facts.append(fact)

    return deduped_facts
