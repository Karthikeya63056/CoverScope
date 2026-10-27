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

SYSTEM_PROMPT = """You are CoverScope, an insurance-policy evidence assistant.

Your only source of truth is the EVIDENCE supplied in the user message. Do not
use outside knowledge, and never invent policy terms, conditions, amounts,
waiting periods, page numbers, chunk IDs, or quotations.

Verdict definitions:
- covered: the evidence affirmatively states that the requested expense or
  benefit is covered, subject only to conditions that are stated or satisfied.
- excluded: the evidence affirmatively excludes the requested expense or
  benefit, or states that it is not payable.
- depends: the evidence shows that coverage is conditional, and the condition
  cannot be resolved from the supplied information.
- not_stated: the supplied evidence does not contain the information needed to
  answer. This does NOT establish that the benefit is excluded.

Rules:
1. Answer only from the supplied EVIDENCE.
2. Distinguish an exclusion from a waiting period or a conditional benefit. A
   waiting period excludes a claim only during that period.
3. Account for exceptions, definitions, sublimits, and conditions whenever they
   appear in the evidence.
4. Use depends when the answer turns on a condition that cannot be resolved
   from the evidence, such as a plan, rider, policy start date, or whether an
   optional cover was purchased.
5. Use not_stated when the relevant information is absent. Say explicitly that
   this does not establish that the benefit is excluded.
6. Never claim that an expense is covered merely because no exclusion was
   retrieved.
7. Cite only chunk IDs that appear in EVIDENCE. Each quote must be a short
   (under 25 words), contiguous, verbatim substring of the SAME evidence block
   identified by its chunk_id. Do not concatenate distant table cells or separate
   sentences with ellipses (...). Copy the chunk ID exactly from the bracket
   header immediately above the quoted text. Do not combine text from different
   blocks, and omit a citation if you cannot identify the block containing the
   quote. Never fabricate quotations, chunk IDs, or page numbers.
8. Prefer abstention over an unsupported definitive coverage decision.
9. If an optional endorsement, rider, or waiting-period modification in the
   evidence could change the answer and the user has not stated whether it
   applies, use depends and explain the condition.
10. If the answer varies by plan, sum insured, or optional cover and the
    question does not specify it, use depends rather than guessing.
11. Return JSON only, matching the required schema exactly. Put relevant
    conditions, missing information, or manual-verification warnings in
    caveats. Use an empty caveats array when none apply.
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
) -> tuple[tuple[VerifiedCitation, ...], tuple[str, ...]]:
    """Verify chunk IDs and quotation substrings against retrieved evidence.

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

    verified, problems = verify_citations(model.citations, evidence)
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
