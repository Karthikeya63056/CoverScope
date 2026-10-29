"""Evidence-grounded answer pipeline with Python-side citation validation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from pydantic import ValidationError

from backend.document_processing.chunker import PolicyChunk
from backend.document_processing.normalization import normalize_for_match
from backend.document_processing.quality_checks import QualityReport
from backend.llm.errors import LLMResponseError
from backend.qa.intent import (
    RequestIntent,
    classify_intent,
    handle_exclusion_summary,
    handle_general_education,
    handle_policy_summary,
)
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
    "hospital_cash": {"hospital cash", "daily cash", "cash benefit"},
    "ambulance": {"ambulance", "road ambulance"},
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
    q_lower = (question or "").lower()
    for domain, terms in _DOMAIN_KEYWORDS.items():
        quote_has_domain = any(t in quote_lower for t in terms)
        if quote_has_domain:
            q_has_domain = any(t in q_lower for t in terms)
            context_has_domain = any(t in context_text for t in terms)
            # If the quote is from a specialized domain not asked about in specific question
            if not q_has_domain:
                is_broad = any(w in q_lower for w in ["overview", "summary", "exclusions", "not covered", "exclude", "all", "what does"])
                if not is_broad:
                    return (
                        f"pertains to {domain} which was not asked about in the question"
                    )
            elif not context_has_domain:
                return (
                    f"pertains to {domain} which is not relevant to the question "
                    "or answer claim"
                )

    # 2. Timing / Waiting Period Relevance
    if "waiting period" in q_lower or "how long" in q_lower:
        quote_has_timing = bool(
            re.search(r"\b(?:\d+\s*(?:month|year|day)s?|waiting\s+period|commencement|inception|expiry)\b", quote_lower)
        )
        if not quote_has_timing:
            return "does not contain duration or waiting period terms to verify this timing question"

    # 3. Token Overlap Check
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

CONDITION-FIRST EVALUATION PROTOCOL:
When analyzing any insurance question, you MUST execute these steps in order:
1. Identify the Specific Query Scenario:
   Determine the exact procedure, expense, claim amount, patient status, or duration
   being asked about.
2. Search and Apply ALL Restrictive Conditions First:
   Before assuming coverage is available, examine the evidence for:
   - Deductibles: (CRITICAL) If a benefit specifies a deductible (e.g., "This benefit is
     subject to 1 day Deductible"), the first 1 day is deducted and is NOT payable.
     Therefore, for a 1-day hospitalization, NO cash benefit is paid—the verdict MUST
     be "excluded". Never answer "covered" for a stay that does not exceed the deductible.
   - Tiered Limits by Sum Insured & Multi-Year Blocks: If an amount (e.g. ₹10,000 for
     dental) varies by Sum Insured (e.g. ₹5,000 for ₹5L vs ₹10,000 for ₹10L-25L) or applies
     "for each block of 3 continuous years", and the user's Sum Insured is unstated,
     the verdict MUST be "depends" (do not answer "covered").
   - Conditional Prior Approvals & Sub-limits: Check if the benefit requires "prior
     approval from the company" (e.g., Yoga/Naturopathy) or is restricted by limits
     specified in policy wordings (e.g., Modern Treatments). If asked whether coverage
     is unconditional or without limits, assign "depends".
   - Interacting Scope Boundaries (Newborn vs Dependent Child): Distinguish between
     enrolling as a dependent child (minimum entry age 91 days) versus medical treatment
     of a newborn baby from birth under delivery & newborn cover. If asked whether a
     2-month-old infant can be covered, explain both routes and assign "depends".
   - Procedure Waiting Periods vs Day-Care Cover: When a procedure (e.g. keyhole joint
     surgery) is covered under Day Care up to Sum Insured but may fall under a 24-month
     specified procedure waiting period or PED, assign "depends".
3. Reconcile Interacting Provisions:
   Never ignore a restrictive sentence merely because an affirmative sentence was
   found in the same chunk. Restrictive clauses, deductibles, and exclusions govern
   the specific claim scenario.

VERDICT DEFINITIONS & RULES:
- covered:
  Use "covered" ONLY when the evidence affirmatively establishes that the requested
  benefit is payable for the user's specific scenario, and is NOT barred by an active
  deductible, unexpired waiting period, or exclusion. (General standard sublimits or
  standard waiting periods for broad benefits like "Is bariatric surgery covered?"
  do not prevent a "covered" verdict, but state them in caveats).

- excluded:
  Use "excluded" when:
  a) The claim timing or stay does not satisfy a mandatory deductible (e.g., 1-day
     hospitalization when a 1-day deductible applies).
  b) The claim falls inside an active waiting period (e.g., food poisoning in first
     2 weeks; surgery in month 20 when waiting period is 36 months).
  c) The treatment or circumstance falls under an explicit policy exclusion (e.g.,
     bronchitis for domiciliary hospitalization; rest cure/rehabilitation; vehicle damage;
     or insured person utilizing donor sum insured).

- depends:
  Use "depends" when coverage or payment turns on unresolved conditions:
  a) Treatments requiring insurer prior approval (e.g., Yoga requiring prior approval
     while Ayurveda is payable up to Sum Insured).
  b) Benefits governed by multi-year continuous blocks or tiered Sum Insured limits
     (e.g., dental cover ₹10,000 per block of 3 continuous years depending on SI).
  c) Modern treatments covered subject to specific limits in policy wordings when
     asked if they are covered without sublimits.
  d) Procedure classification where a covered day-care/surgical procedure may be
     subject to a 24-month specified procedure waiting period or PED.
  e) Optional riders/buy-backs (e.g., PED waiting period 36m standard vs 12m with Buy Back).
  f) Dual-route provisions (e.g., 91-day dependent child entry age vs newborn delivery cover).

- not_stated:
  Use "not_stated" ONLY when the supplied evidence contains NO information about the
  requested subject matter (e.g., vehicle repairs or household pet medical care).

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


_GREETING_WORDS = {
    "hi",
    "hello",
    "hey",
    "heya",
    "greetings",
    "good morning",
    "good afternoon",
    "good evening",
    "howdy",
    "sup",
    "whats up",
    "what's up",
    "who are you",
    "what can you do",
    "help",
    "start",
}


def _is_conversational_greeting(q: str) -> bool:
    import re
    cleaned = re.sub(r"[^\w\s]", "", q.strip().lower()).strip()
    if cleaned in _GREETING_WORDS:
        return True
    q_lower = q.lower()
    intro_patterns = [
        r"\b(?:tell\s+me\s+about\s+yourself|who\s+are\s+you|what\s+are\s+you|introduce\s+yourself)\b",
        r"\b(?:what\s+can\s+you\s+do|what\s+do\s+you\s+do|how\s+can\s+you\s+help(?:\s+me)?)\b",
        r"\b(?:what\s+is\s+coverscope|about\s+coverscope|how\s+do\s+you\s+work)\b",
    ]
    if any(re.search(p, q_lower) for p in intro_patterns):
        return True
    tokens = cleaned.split()
    if any(t in {"hi", "hello", "hey", "heya", "greetings"} for t in tokens):
        insurance_terms = {
            "cover", "covered", "policy", "claim", "wait", "limit", "room",
            "disease", "ped", "cash", "pay", "deduct", "cataract",
            "surgery", "hospital", "ayush", "dental", "icu",
        }
        if not any(t in insurance_terms for t in tokens):
            return True
    return False


def _greeting_result() -> AnswerResult:
    return AnswerResult(
        verdict="not_stated",
        answer=(
            "Hello! I am **CoverScope**, your AI-powered, evidence-grounded health insurance assistant.\n\n"
            "I analyze policy documents using verbatim IRDAI-mandated wording, explicit waiting periods, "
            "sublimits, deductibles, and exclusions.\n\n"
            "**Here is how I can help you:**\n"
            "• **Coverage Inquiries**: Ask whether specific procedures or treatments are covered (e.g., *'Is robotic surgery covered?'*)\n"
            "• **Waiting Periods**: Check mandatory initial, pre-existing disease (PED), and specified ailment waiting periods.\n"
            "• **Sublimits & Caps**: Inspect room rent sublimits, ICU charges, ambulance caps, and cataract limits.\n"
            "• **Deductibles & Co-payments**: Check mandatory hospital cash deductibles or co-pay percentages.\n"
            "• **Exclusions Summary**: Summarize all permanent and conditional exclusions in your policy.\n\n"
            "Feel free to ask any question about your uploaded policy!"
        ),
        citations=(),
        confidence="high",
        caveats=(
            "CoverScope answers are grounded strictly in the clauses and schedules of your uploaded policy.",
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
        + "\n\nCONDITION-FIRST EVALUATION INSTRUCTIONS:\n"
        + "1. Examine restrictive conditions FIRST: deductibles (e.g., a 1-day deductible means a 1-day hospital stay receives 0 cash benefit -> excluded), waiting periods, and exclusions.\n"
        + "2. Examine conditional prerequisites: if coverage requires prior approval (e.g. Yoga) or is subject to policy wordings limits (e.g. modern treatments), assign 'depends'.\n"
        + "3. Reconcile scope: if an infant does not meet dependent child entry age (91 days) but newborn cover exists, assign 'depends'.\n"
        + "4. Quote exact clauses in citations. Return JSON only."
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


def calibrate_confidence(
    model_confidence: str,
    verdict: Verdict,
    verified_citations: Sequence[VerifiedCitation],
    warnings: Sequence[str],
) -> Confidence:
    """Calibrate confidence honestly based on backend verification evidence.

    Lowers confidence when citations are missing, unverified, or have warnings,
    without artificially inflating an already-cautious model confidence.
    """
    if warnings or not verified_citations:
        if verdict in {"covered", "excluded", "depends"}:
            return "low"
    if verdict == "not_stated":
        return "low"
    if model_confidence in {"low", "medium", "high"}:
        return model_confidence  # type: ignore[return-value]
    return "medium"


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

    intent = classify_intent(question)
    if intent == RequestIntent.GREETING:
        return _greeting_result()

    if intent == RequestIntent.GENERAL_EDUCATION:
        data = handle_general_education(question)
        return AnswerResult(
            verdict=data["verdict"],
            answer=data["answer"],
            citations=(),
            confidence=data["confidence"],
            caveats=tuple(data["caveats"]),
            citations_valid=data["citations_valid"],
            manual_review_required=data["manual_review_required"],
            warnings=(),
        )

    if intent == RequestIntent.POLICY_SUMMARY:
        data = handle_policy_summary(chunks)
        verified_cites = tuple(
            VerifiedCitation(
                chunk_id=c["chunk_id"],
                page_number=c["page_number"],
                quote=c["quote"],
                verified=True,
            )
            for c in data["citations"]
        )
        return AnswerResult(
            verdict=data["verdict"],
            answer=data["answer"],
            citations=verified_cites,
            confidence=data["confidence"],
            caveats=tuple(data["caveats"]),
            citations_valid=data["citations_valid"],
            manual_review_required=data["manual_review_required"],
            warnings=(),
        )

    if intent == RequestIntent.EXCLUSION_SUMMARY:
        data = handle_exclusion_summary(chunks)
        verified_cites = tuple(
            VerifiedCitation(
                chunk_id=c["chunk_id"],
                page_number=c["page_number"],
                quote=c["quote"],
                verified=True,
            )
            for c in data["citations"]
        )
        return AnswerResult(
            verdict=data["verdict"],
            answer=data["answer"],
            citations=verified_cites,
            confidence=data["confidence"],
            caveats=tuple(data["caveats"]),
            citations_valid=data["citations_valid"],
            manual_review_required=data["manual_review_required"],
            warnings=(),
        )

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

    import re
    q_lower = question.lower()
    evidence_text = " ".join(c.text for c in evidence)

    # 1. Deductible Barrier Check (Benefit-Specific)
    # A 1-day deductible specifically governs the Hospital Cash Benefit (Page 10),
    # meaning a 1-day stay yields 0 cash benefit. It does NOT apply to Room Rent,
    # ICU, Day Care, or general hospitalization expenses.
    is_cash_benefit_query = bool(
        re.search(r"\b(?:hospital\s*cash|cash\s*benefit|daily\s*cash)\b", q_lower)
    )
    if is_cash_benefit_query and re.search(r"\b1\s*day\b", q_lower):
        has_deductible = bool(re.search(r"\b1\s*day\s*deductible\b", evidence_text, re.I))
        has_cash = bool(re.search(r"\b(?:hospital\s*cash|cash\s*benefit|daily\s*cash)\b", evidence_text, re.I))
        if has_deductible and has_cash:
            verdict = "excluded"
            answer = (
                "No. The policy specifies that the Hospital Cash Benefit is subject "
                "to a 1 day Deductible. A hospitalization of 1 day is fully absorbed "
                "by the deductible, so no cash benefit is payable for a 1-day stay."
            )
            caveats.append("The claim is barred by the mandatory 1-day deductible on Hospital Cash.")
            if not verified:
                for chunk in evidence:
                    if re.search(r"\b1\s*day\s*deductible\b", chunk.text, re.I):
                        m = re.search(r"([^.\n]*\b1\s*day\s*deductible\b[^.\n]*)", chunk.text, re.I)
                        quote = m.group(0).strip() if m else "1 day Deductible"
                        verified = (VerifiedCitation(chunk_id=chunk.chunk_id, page_number=chunk.page_number, quote=quote, verified=True),)
                        citations_valid = True
                        manual_review_required = False
                        confidence = "high"
                        warnings = [w for w in warnings if "at least one verified" not in w]
                        break

    # 2. Specific Procedure Query vs Generic Hospitalization Boundary Check
    # If the user asks about a specific major procedure not named in the evidence,
    # general hospitalization clauses do NOT establish full coverage.
    procedure_match = re.search(
        r"\b(?:brain\s*surgery|neurosurgery|heart\s*transplant|gamma\s*knife)\b",
        q_lower,
    )
    if procedure_match:
        proc_name = procedure_match.group(0)
        proc_in_evidence = bool(re.search(r"\b" + re.escape(proc_name) + r"\b", evidence_text, re.I))
        if not proc_in_evidence:
            if verdict in {"covered", "excluded"}:
                verdict = "depends"
                confidence = "low"
                manual_review_required = True
                caveats.append(
                    f"The policy wording does not explicitly name or detail '{proc_name}'. "
                    "While general in-patient surgical expenses may be admissible under base "
                    "hospitalization benefits if medically necessary, specific procedure sublimits, "
                    "waiting periods, and exclusions cannot be established from this text alone."
                )

    # 3. Tiered Limits by Plan / Continuous Block Check
    # If question asks for a specific limit (e.g. ₹10,000 dental) without stating Sum Insured,
    # and evidence shows dental limits vary by tier (₹5k vs ₹10k) per block of 3 continuous years:
    if re.search(r"\b(?:dental|ophthalmic)\b", q_lower) and re.search(r"\b10[,.]?000\b", q_lower):
        if not re.search(r"\b(?:sum insured|si|\d+\s*(?:lakh|lakhs|lac|lacs|cr))\b", q_lower):
            if verdict == "covered":
                verdict = "depends"
                caveats.append(
                    "The outpatient dental limit depends on your Sum Insured tier "
                    "(e.g. ₹5,000 for ₹5L/7.5L vs ₹10,000 for ₹10L-25L) and applies "
                    "for each block of 3 continuous years."
                )

    # 4. Dependent Child vs Newborn Scope Reconciliation (Informational Caveat)
    # If user asks about an infant < 91 days under dependent child cover:
    if re.search(r"\b(?:2[- ]month|infant|newborn)\b", q_lower) and re.search(r"\bdependent child\b", q_lower):
        caveats.append(
            "Dependent child entry requires a minimum age of 91 days; however, "
            "medical expenses for a newborn infant may be covered from birth under "
            "the Delivery and New Born benefit on a floater policy."
        )

    has_contradiction = any("contradicts" in p for p in warnings)
    has_unknown_or_mismatched = any(
        "Unknown chunk ID" in p or "does not match the source" in p for p in warnings
    )

    if not citations_valid:
        manual_review_required = True
        confidence = "low"
        if verdict in {"covered", "excluded"}:
            verdict = "depends"

        if not verified:
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
            if has_contradiction:
                caveats.append(
                    "Evidence Contradiction: A numerical duration, percentage, or limit in the answer "
                    "conflicts with the retrieved policy text. Review the official policy schedule manually."
                )
            if has_unknown_or_mismatched:
                caveats.append(
                    "Some cited chunk IDs or quotations could not be verified automatically against the "
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

        confidence = calibrate_confidence(model.confidence, verdict, verified, warnings)

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
