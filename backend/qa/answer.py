"""Evidence-grounded answer pipeline with Python-side citation validation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from pydantic import ValidationError

from backend.document_processing.chunker import PolicyChunk
from backend.document_processing.normalization import normalize_for_match
from backend.document_processing.quality_checks import QualityReport
from backend.llm.errors import LLMResponseError
from backend.qa.retrieval import RetrievedChunk, retrieve_chunks
from backend.qa.schemas import (
    ANSWER_JSON_SCHEMA,
    Confidence,
    ModelAnswer,
    Verdict,
)

# A short quote is easier to verify and less likely to match by accident.
MIN_QUOTE_MATCH_CHARS = 12

_STOPWORDS = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "isn't", "it", "its",
    "itself", "let's", "me", "more", "most", "mustn't", "my", "myself", "no",
    "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our",
    "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", "should",
    "shouldn't", "so", "some", "such", "than", "that", "the", "their", "theirs",
    "them", "themselves", "then", "there", "these", "they", "this", "those",
    "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we",
    "were", "weren't", "what", "when", "where", "which", "while", "who", "whom",
    "why", "with", "won't", "would", "wouldn't", "you", "your", "yours", "yourself",
    "yourselves",
})

_DOMAIN_KEYWORDS: dict[str, set[str]] = {
    "maternity_newborn": {"maternity", "delivery", "new born", "newborn", "infant", "obstetric"},
    "bariatric": {"bariatric", "weight loss", "obesity", "metabolic"},
    "dental": {"dental", "denture", "teeth", "tooth", "oral"},
    "ophthalmic": {"cataract", "ophthalmic", "eye", "lens"},
    "ayush": {"ayush", "ayurveda", "homeopathy", "unani", "siddha", "yoga", "naturopathy"},
    "motor": {"vehicle", "car", "motor", "repair", "traffic"},
    "organ_donor": {"organ donor", "donor"},
}


def _check_citation_relevance(
    quote: str,
    question: str | None,
    answer: str | None,
) -> str | None:
    """Validate semantic and topic alignment between cited quote and claim."""
    if not question and not answer:
        return None
    import re

    context_text = f"{question or ''} {answer or ''}".lower()
    quote_lower = quote.lower()

    # 1. Specialized Domain Mismatch
    for domain, terms in _DOMAIN_KEYWORDS.items():
        quote_has_domain = any(t in quote_lower for t in terms)
        if quote_has_domain:
            context_has_domain = any(t in context_text for t in terms)
            if not context_has_domain:
                return (
                    f"pertains to {domain} which is not relevant to the question "
                    "or answer claim"
                )

    # 2. Token Overlap Check
    q_tokens = {
        w
        for w in re.findall(r"\w+", quote_lower)
        if w not in _STOPWORDS and (len(w) >= 3 or w.isdigit())
    }
    ctx_tokens = {
        w
        for w in re.findall(r"\w+", context_text)
        if w not in _STOPWORDS and (len(w) >= 3 or w.isdigit())
    }
    if len(q_tokens) >= 2 and len(q_tokens & ctx_tokens) == 0:
        return "does not share topical relevance with the claim or question"

    # 3. Numeric Duration Contradiction Check
    if answer:
        answer_lower = answer.lower()
        quote_durations = re.findall(
            r"(\b\d+\b)\s*(month|months|day|days|year|years)", quote_lower
        )
        answer_durations = re.findall(
            r"(\b\d+\b)\s*(month|months|day|days|year|years)", answer_lower
        )
        if quote_durations and answer_durations:
            def _norm_unit(u: str) -> str:
                return "month" if "month" in u else ("day" if "day" in u else "year")

            q_dur_by_unit: dict[str, set[int]] = {}
            for num, u in quote_durations:
                q_dur_by_unit.setdefault(_norm_unit(u), set()).add(int(num))

            a_dur_by_unit: dict[str, set[int]] = {}
            for num, u in answer_durations:
                a_dur_by_unit.setdefault(_norm_unit(u), set()).add(int(num))

            for unit, q_nums in q_dur_by_unit.items():
                if unit in a_dur_by_unit:
                    a_nums = a_dur_by_unit[unit]
                    if not (q_nums & a_nums):
                        return (
                            f"duration ({', '.join(map(str, sorted(q_nums)))} {unit}s) "
                            f"contradicts duration in answer ({', '.join(map(str, sorted(a_nums)))} {unit}s)"
                        )

        # 4. Percentage Contradiction Check
        q_pcts = set(re.findall(r"(\b\d+\b)\s*%", quote_lower))
        a_pcts = set(re.findall(r"(\b\d+\b)\s*%", answer_lower))
        if q_pcts and a_pcts and not (q_pcts & a_pcts):
            return (
                f"percentage ({', '.join(sorted(q_pcts))}%) "
                f"contradicts percentage in answer ({', '.join(sorted(a_pcts))}%)"
            )

    return None


SYSTEM_PROMPT = """You are CoverScope, an insurance-policy evidence assistant.

Your only source of truth is the EVIDENCE supplied in the user message. Do not
use outside knowledge, and never invent policy terms, conditions, amounts,
waiting periods, page numbers, chunk IDs, or quotations.

EVIDENCE SYNTHESIS FRAMEWORK:
When analyzing a coverage question, synthesize the evidence systematically across
four distinct policy dimensions:
1. Benefit Category: Does the policy affirmatively cover this category of treatment
   (e.g., In-patient Treatment, Day Care Treatment, AYUSH Treatment, Bariatric Surgery)?
2. Waiting Periods: What waiting periods apply (e.g., Initial 30 days, Specified
   Disease/Procedure 24 months, Pre-Existing Disease 36 months, Bariatric 36 months)?
3. Cost Sharing & Limits: Are there sub-limits, co-payments (e.g., 10% co-payment
   for entry age 61+), or room rent category restrictions?
4. Exclusions: Does an explicit exclusion apply (e.g., cosmetic surgery, intentional
   self-injury, non-medical expenses)?

VERDICT DEFINITIONS & RULES:
- covered:
  Use "covered" when the evidence affirmatively establishes that the requested benefit
  or treatment category is included under policy coverages (e.g., "Is bariatric surgery
  covered under this policy?", "What room category is permitted?").
  Standard waiting periods and sub-limits do NOT turn an affirmatively covered benefit
  into "depends"; state the applicable waiting periods and sub-limits in your answer
  and caveats while keeping the verdict "covered".

- excluded:
  Use "excluded" when:
  a) The expense or treatment falls under an explicit policy exclusion (e.g., cosmetic
     surgery for aesthetic weight loss, car accident repairs).
  b) OR the specific claim timing stated by the user falls inside an active waiting
     period (e.g., food poisoning in the first 2 weeks when initial waiting period
     is 30 days; surgery in month 20 when waiting period is 36 months).

- depends:
  Use "depends" when coverage or the applicable terms are conditional:
  a) Procedure Classification / Clinical Context: When a procedure (such as keyhole
     surgery, arthroscopy, or joint surgery) is payable under Day Care or In-patient
     treatment up to Sum Insured, BUT is subject to a 24-month waiting period for
     specified disease/procedures or 36-month PED waiting period depending on medical
     history and continuous coverage. Do NOT use "not_stated" if general day care or
     inpatient surgical cover exists; explain the coverage and waiting periods, and
     use "depends".
  b) Waiting Period Queries with Optional Riders / Buy-Backs: When asked about a waiting
     period, reduction, or policy term that varies based on optional riders (e.g., "What
     is the waiting period for pre-existing diseases and can it be reduced?"), the
     verdict is NEVER "covered"—it MUST be "depends" because the applicable waiting period
     (36 months standard vs 12 months with optional Buy Back) depends on whether the optional
     cover was purchased.
  c) Dual-Nature Procedures: When a procedure is covered for medical necessity but
     excluded for aesthetic reasons (e.g., bariatric surgery for morbid obesity vs
     cosmetic weight reduction).
  d) Conditional Parameters: When coverage depends on unresolved variables such as
     entry age (co-payment applicability) or sum insured plan limits.

- not_stated:
  Use "not_stated" ONLY when the supplied evidence contains NO relevant information
  or is completely out-of-scope (e.g., motor vehicle repairs or pet insurance in a
  health policy). Do NOT use "not_stated" when the policy contains relevant day care,
  surgical, or waiting period provisions that govern the scenario.

ADDITIONAL RULES:
1. Distinguish an exclusion from a waiting period. A waiting period excludes a claim
   only during that period.
2. If a question contains an ambiguous reference (e.g. "What is the waiting period
   for that?") without naming the condition: state that the condition is not specified,
   summarize the policy's standard waiting periods by category, and do NOT cite
   unrelated specific clauses (such as newborn or delivery expenses).
3. Every citation quote must be a short, contiguous, verbatim substring of the SAME
   evidence block identified by its chunk_id. Do NOT fabricate citations or cite
   unrelated clauses.
4. Return JSON only, matching the required schema exactly. Put relevant conditions,
   missing information, or manual-verification warnings in caveats. Use an empty
   caveats array when none apply.
"""


class StructuredClient(Protocol):
    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict | None = None,
    ) -> dict: ...


@dataclass(frozen=True)
class VerifiedCitation:
    chunk_id: str
    page_number: int
    quote: str
    verified: bool
    warning: str | None = None


@dataclass(frozen=True)
class AnswerResult:
    verdict: Verdict
    answer: str
    citations: tuple[VerifiedCitation, ...]
    confidence: Confidence
    caveats: tuple[str, ...]
    citations_valid: bool
    manual_review_required: bool
    warnings: tuple[str, ...]
    unverified_answer: str | None = None

    @property
    def cited_pages(self) -> tuple[int, ...]:
        return tuple(dict.fromkeys(c.page_number for c in self.citations))


def _no_evidence_result() -> AnswerResult:
    return AnswerResult(
        verdict="not_stated",
        answer=(
            "The available policy text does not contain information relevant "
            "to this question."
        ),
        citations=(),
        confidence="low",
        caveats=(
            "This does not establish that the benefit is excluded.",
            "Try rephrasing the question or review the policy manually.",
        ),
        citations_valid=True,
        manual_review_required=False,
        warnings=(),
    )


def build_user_prompt(question: str, evidence: Sequence[RetrievedChunk]) -> str:
    blocks = []
    for chunk in evidence:
        blocks.append(f"[{chunk.chunk_id} | page {chunk.page_number}]\n{chunk.text}")
    return (
        "EVIDENCE:\n\n"
        + "\n\n".join(blocks)
        + "\n\nQUESTION:\n"
        + question.strip()
        + "\n\nAnswer using only the evidence above."
    )


def verify_citations(
    citations: Sequence,
    evidence: Sequence[RetrievedChunk],
    *,
    question: str | None = None,
    answer: str | None = None,
) -> tuple[tuple[VerifiedCitation, ...], tuple[str, ...]]:
    """Verify chunk IDs, quotation substrings, and claim relevance against retrieved evidence.

    Page numbers always come from the trusted chunk metadata, never from the
    model. Quotations are compared after NFKC/case/whitespace normalization.
    """
    evidence_by_id = {chunk.chunk_id: chunk for chunk in evidence}
    verified: list[VerifiedCitation] = []
    problems: list[str] = []

    for citation in citations:
        source = evidence_by_id.get(citation.chunk_id)
        if source is None:
            # Check normalized chunk ID in case the model copied bracket/page headers (e.g. "P10-C2 | page 10")
            clean_id = citation.chunk_id.split("|")[0].strip().strip("[]").strip("'\"")
            source = evidence_by_id.get(clean_id)

        if source is None:
            problems.append(
                f"Unknown chunk ID {citation.chunk_id!r} was cited."
            )
            continue

        s_norm = normalize_for_match(source.text)
        quote_norm = normalize_for_match(citation.quote)

        # Enforce substantive quote length to reject punctuation, single letters, or degenerate quotes
        if len(quote_norm) < MIN_QUOTE_MATCH_CHARS:
            problems.append(
                f"Quotation for {citation.chunk_id} is too short or lacks substantive text (minimum {MIN_QUOTE_MATCH_CHARS} characters required)."
            )
            continue

        matched = quote_norm in s_norm
        if not matched and ("..." in citation.quote or "\u2026" in citation.quote):
            import re
            parts = re.split(r"\s*(?:\.{3,}|\u2026)\s*", citation.quote)
            clean_parts = [p.strip() for p in parts if len(normalize_for_match(p)) >= 6]
            if clean_parts and sum(len(normalize_for_match(cp)) for cp in clean_parts) >= MIN_QUOTE_MATCH_CHARS:
                matched = all(
                    normalize_for_match(cp) in s_norm
                    for cp in clean_parts
                )
            else:
                matched = False

        if not matched:
            # Tolerant match for multi-column table extraction interleaving in PDFs
            import re
            q_tokens = [w for w in re.findall(r"\w+", citation.quote.lower()) if len(w) > 1]
            t_tokens = [w for w in re.findall(r"\w+", source.text.lower()) if len(w) > 1]
            if len(q_tokens) >= 4 and len(quote_norm) >= MIN_QUOTE_MATCH_CHARS:
                for i, tw in enumerate(t_tokens):
                    if tw == q_tokens[0]:
                        qi = 0
                        ti = i
                        curr_gap = 0
                        total_gap = 0
                        while qi < len(q_tokens) and ti < len(t_tokens):
                            if q_tokens[qi] == t_tokens[ti]:
                                qi += 1
                                ti += 1
                                curr_gap = 0
                            else:
                                curr_gap += 1
                                total_gap += 1
                                if curr_gap > 10 or total_gap > 15:
                                    break
                                ti += 1
                        if qi == len(q_tokens):
                            matched = True
                            break

        if not matched:
            problems.append(
                f"Quotation for {citation.chunk_id} does not match the source text."
            )
            continue

        # Check claim-to-citation topic and semantic relevance
        relevance_err = _check_citation_relevance(
            citation.quote, question, answer
        )
        if relevance_err:
            problems.append(
                f"Quotation for {citation.chunk_id} ({citation.quote[:40]}...) "
                f"does not substantiate the claim: {relevance_err}."
            )
            continue

        verified.append(
            VerifiedCitation(
                chunk_id=source.chunk_id,
                page_number=source.page_number,
                quote=citation.quote,
                verified=True,
            )
        )

    return tuple(verified), tuple(problems)


def _dedupe(items: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item for item in items if item))


def answer_question(
    question: str,
    chunks: Sequence[PolicyChunk],
    client: StructuredClient,
    *,
    top_k: int = 5,
    unreliable_pages: Sequence[int] = (),
    quality_report: QualityReport | None = None,
) -> AnswerResult:
    """Retrieve evidence, ask the model, and validate every citation.

    An empty question raises ``ValueError``. Empty evidence returns a safe
    ``not_stated`` result without contacting the provider. Provider failures
    propagate as ``LLMError`` subclasses for the CLI to report.
    """
    if not question or not question.strip():
        raise ValueError("Question must not be empty.")

    evidence = retrieve_chunks(question, chunks, top_k=top_k)
    if not evidence:
        return _no_evidence_result()

    payload = client.complete_json(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(question, evidence),
        schema=ANSWER_JSON_SCHEMA,
    )
    try:
        model = ModelAnswer.model_validate(payload)
    except ValidationError as exc:
        raise LLMResponseError(
            "Groq returned JSON that did not match the required answer schema."
        ) from exc

    verified, problems = verify_citations(
        model.citations,
        evidence,
        question=question,
        answer=model.answer,
    )
    warnings = list(problems)
    caveats = list(model.caveats)

    requires_citation = model.verdict in {"covered", "excluded", "depends"}
    if requires_citation and not verified:
        warnings.append(
            "A coverage verdict requires at least one verified policy quotation."
        )

    citations_valid = not warnings
    manual_review_required = False
    verdict: Verdict = model.verdict
    confidence: Confidence = model.confidence
    answer = model.answer
    unverified_answer: str | None = None

    if not citations_valid:
        manual_review_required = True
        confidence = "low"
        if not verified:
            if verdict != "not_stated":
                verdict = "depends"
            answer = (
                "CoverScope could not verify the model's citations against the "
                "policy text. Please review the cited pages manually."
            )
            unverified_answer = model.answer
            caveats.append(
                "The model's answer is unverified and must not be treated as a "
                "coverage decision."
            )
        else:
            caveats.append(
                "Some citations could not be verified automatically against the "
                "extracted text. Please review the flagged citations manually."
            )
    else:
        flagged_pages = sorted(
            {
                citation.page_number
                for citation in verified
                if citation.page_number in unreliable_pages
            }
        )
        if flagged_pages:
            manual_review_required = True
            confidence = "low"
            if verdict in {"covered", "excluded"}:
                verdict = "depends"
            answer = (
                "The answer depends on a page explicitly flagged as unreliable "
                "for extraction. Verify the policy wording manually."
            )
            unverified_answer = model.answer
            warnings.append(
                "Explicitly flagged unreliable page(s): "
                + ", ".join(map(str, flagged_pages))
                + "."
            )

        if quality_report is not None:
            heuristic_pages = sorted(
                {
                    citation.page_number
                    for citation in verified
                    if citation.page_number in quality_report.table_review_pages
                }
            )
            if heuristic_pages:
                caveats.append(
                    "The table-review heuristic also flagged page(s) "
                    + ", ".join(map(str, heuristic_pages))
                    + ". This is not proof of a problem; verify any "
                    "table-derived amounts manually."
                )

    return AnswerResult(
        verdict=verdict,
        answer=answer,
        citations=verified,
        confidence=confidence,
        caveats=_dedupe(caveats + warnings),
        citations_valid=citations_valid,
        manual_review_required=manual_review_required,
        warnings=_dedupe(warnings),
        unverified_answer=unverified_answer,
    )
