"""Regression and audit tests for Answer Quality, Evidence Integrity & Request-Intent Routing.

Verifies:
1. Intent classification distinguishes specific coverage, broad summary, exclusion summary,
   clause explanation, educational advice, and greetings.
2. Broad policy-summary queries produce multi-category evidence-grounded summaries with verdict="summary".
3. Educational advice is cleanly separated from policy-specific findings and contains no fake citations.
4. Irrelevant domain citations (motor/ayush on specific coverage queries) are rejected even with keyword overlap.
5. Mismatched or non-existent quotes fail validation and trigger manual review.
6. Missing categories in summaries are explicitly marked as not located rather than hallucinated.
7. Existing specific coverage questions preserve backward compatibility.
"""
from __future__ import annotations

import pytest

from backend.document_processing.chunker import PolicyChunk
from backend.qa.answer import (
    AnswerResult,
    _check_citation_relevance,
    answer_question,
    verify_citations,
)
from backend.qa.intent import (
    RequestIntent,
    classify_intent,
    handle_exclusion_summary,
    handle_general_education,
    handle_policy_summary,
)
from backend.qa.retrieval import RetrievedChunk
from backend.qa.schemas import Citation


class MockStructuredClient:
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or {
            "verdict": "covered",
            "answer": "This procedure is covered.",
            "citations": [],
            "confidence": "high",
            "caveats": [],
        }
        self.calls = 0

    def complete_json(self, *, system_prompt: str, user_prompt: str, schema: dict | None = None) -> dict:
        self.calls += 1
        return self.payload


def make_policy_chunks() -> list[PolicyChunk]:
    return [
        PolicyChunk(
            "P1-C1",
            1,
            "SECTION 1: IN-PATIENT HOSPITALIZATION BENEFITS\n"
            "Room rent, boarding and nursing expenses up to Single Private A/C Room.\n"
            "Intensive Care Unit (ICU) charges and surgeon fees are covered up to the Sum Insured.",
        ),
        PolicyChunk(
            "P2-C1",
            2,
            "SECTION 2: DAY CARE PROCEDURES\n"
            "Day Care procedures requiring less than 24 hours hospitalization are covered.\n"
            "Pre-hospitalization medical expenses for 60 days and post-hospitalization for 90 days are payable.",
        ),
        PolicyChunk(
            "P3-C1",
            3,
            "SECTION 3: WAITING PERIODS\n"
            "Initial waiting period of 30 days applies to all illnesses except accidental injuries.\n"
            "Pre-existing diseases (PED) are excluded until the expiry of 36 months of continuous coverage.\n"
            "Specific ailments like cataract and joint replacement have a waiting period of 24 months.",
        ),
        PolicyChunk(
            "P4-C1",
            4,
            "SECTION 4: EXCLUSIONS\n"
            "Treatment for substance abuse, alcoholism, and drug addiction is excluded.\n"
            "Cosmetic or plastic surgery is excluded unless required due to an accidental injury.\n"
            "Participating in motor racing and hazardous sports is not covered.",
        ),
        PolicyChunk(
            "P5-C1",
            5,
            "SECTION 5: SUBLIMITS & DEDUCTIBLES\n"
            "Cataract surgery is subject to a sublimit of Rs. 50,000 per eye.\n"
            "Hospital Cash Benefit is subject to a 1 day Deductible.",
        ),
    ]


def test_intent_classification_distinguishes_queries():
    assert classify_intent("Is my surgery covered?") == RequestIntent.SPECIFIC_COVERAGE
    assert classify_intent("If I am hospitalized for 1 day, will I get cash benefit?") == RequestIntent.SPECIFIC_COVERAGE
    assert classify_intent("What does my policy cover?") == RequestIntent.POLICY_SUMMARY
    assert classify_intent("What are the benefits in this policy?") == RequestIntent.POLICY_SUMMARY
    assert classify_intent("What does my policy exclude?") == RequestIntent.EXCLUSION_SUMMARY
    assert classify_intent("List all exclusions under this policy") == RequestIntent.EXCLUSION_SUMMARY
    assert classify_intent("Explain the waiting period for pre-existing diseases") == RequestIntent.CLAUSE_EXPLANATION
    assert classify_intent("How should I choose health insurance?") == RequestIntent.GENERAL_EDUCATION
    assert classify_intent("What to look for when buying health insurance?") == RequestIntent.GENERAL_EDUCATION
    assert classify_intent("hi") == RequestIntent.GREETING
    assert classify_intent("hello there") == RequestIntent.GREETING


def test_broad_policy_summary_returns_multicategory_summary():
    chunks = make_policy_chunks()
    client = MockStructuredClient()

    res = answer_question("What does my policy cover?", chunks, client)

    # Must produce summary verdict, not "not_stated" or "covered"
    assert res.verdict == "summary"
    assert res.citations_valid is True
    assert res.manual_review_required is False
    assert len(res.citations) >= 3

    # Must cover standard categories with document findings and page attribution
    assert "In-Patient Hospitalization" in res.answer
    assert "Day Care" in res.answer or "Outpatient" in res.answer
    assert "Waiting Periods" in res.answer
    assert "Exclusions" in res.answer
    assert "Page" in res.answer

    # Categories not in this short policy fixture must be explicitly marked as not located
    assert "Not explicitly located" in res.answer

    # Does not invoke the single-answer LLM unnecessarily
    assert client.calls == 0


def test_general_education_distinguished_from_policy_findings():
    chunks = make_policy_chunks()
    client = MockStructuredClient()

    res = answer_question("How should I choose health insurance?", chunks, client)

    assert res.verdict == "not_stated"
    assert res.citations == ()
    assert res.citations_valid is True
    assert res.manual_review_required is False
    assert "Sum Insured" in res.answer
    assert "Room Rent" in res.answer
    assert any("Educational Guidance" in c for c in res.caveats)
    assert any("not extracted from your uploaded policy document" in c for c in res.caveats)
    assert client.calls == 0


def test_irrelevant_domain_citation_rejected():
    # User asks about knee surgery, but citation is an irrelevant motor racing exclusion
    question = "Is knee surgery covered after month 25?"
    answer = "Yes, knee surgery is covered after 24 months."

    # Citation from unrelated motor domain
    motor_quote = "Participating in motor racing and hazardous sports is not covered."
    err = _check_citation_relevance(motor_quote, question, answer)
    assert err is not None
    assert "motor" in err


def test_mismatched_quotation_fails_verification():
    chunks = make_policy_chunks()
    retrieved = [RetrievedChunk(chunks[0].chunk_id, chunks[0].page_number, chunks[0].text, 1.0, ("room",))]

    # Citation quote that does not exist in the source chunk
    bad_citation = Citation(chunk_id="P1-C1", quote="This text is completely fabricated by the model.")
    verified, problems = verify_citations([bad_citation], retrieved, question="Is room rent covered?")

    assert len(verified) == 0
    assert len(problems) == 1
    assert "does not match the source text" in problems[0]


def test_failed_validation_enforces_review_and_lowers_confidence():
    chunks = make_policy_chunks()
    client = MockStructuredClient({
        "verdict": "covered",
        "answer": "Yes, laser eye treatment is covered unconditionally.",
        "citations": [{"chunk_id": "P1-C1", "quote": "Fabricated nonexistent quote for eye surgery."}],
        "confidence": "high",
        "caveats": [],
    })

    res = answer_question("Is laser eye treatment covered?", chunks, client)

    assert res.citations_valid is False
    assert res.manual_review_required is True
    assert res.confidence == "low"
    assert res.verdict == "depends"  # downgraded from covered due to unverified claims
    assert "could not verify the model's citations" in res.answer


def test_specific_coverage_preserves_contract_and_condition_reasoning():
    chunks = make_policy_chunks()
    chunk5 = chunks[4]  # Hospital Cash 1 day deductible
    client = MockStructuredClient({
        "verdict": "covered",
        "answer": "Hospital cash is payable for hospitalization.",
        "citations": [{"chunk_id": chunk5.chunk_id, "quote": "Hospital Cash Benefit is subject to a 1 day Deductible."}],
        "confidence": "high",
        "caveats": [],
    })

    res = answer_question("If I am hospitalized for 1 day, will I receive the hospital cash benefit?", chunks, client)

    # Condition-first deductible barrier check: 1-day stay yields 0 cash benefit -> excluded
    assert res.verdict == "excluded"
    assert res.citations_valid is True
    assert any("deductible" in c.lower() for c in res.caveats)


# -----------------------------------------------------------------------------
# Additional Focused Regression Tests for Final Freeze Acceptance
# -----------------------------------------------------------------------------
def test_unknown_chunk_id_fails_verification_and_downgrades():
    """Scenario C: Citations with nonexistent/fabricated chunk IDs must be rejected."""
    chunks = make_policy_chunks()
    client = MockStructuredClient({
        "verdict": "excluded",
        "answer": "Cosmetic surgery is excluded under P5-C2.",
        "citations": [{"chunk_id": "P5-C2", "quote": "Cosmetic surgery is excluded"}],
        "confidence": "high",
        "caveats": [],
    })

    res = answer_question("Is cosmetic surgery covered?", chunks, client)

    assert res.citations_valid is False
    assert res.manual_review_required is True
    assert res.confidence == "low"
    assert res.verdict == "depends"
    assert any("Unknown chunk ID 'P5-C2'" in w for w in res.warnings)


def test_material_duration_contradiction_downgrades_verdict():
    """Scenario D: Duration contradictions between answer and quote must not be ignored."""
    chunks = make_policy_chunks()
    chunk3 = chunks[2]  # Section 3: PED waiting period 36 months
    client = MockStructuredClient({
        "verdict": "covered",
        "answer": "Pre-existing diseases are covered after a waiting period of 48 months.",
        "citations": [{"chunk_id": chunk3.chunk_id, "quote": "Pre-existing diseases (PED) are excluded until the expiry of 36 months of continuous coverage."}],
        "confidence": "high",
        "caveats": [],
    })

    res = answer_question("What is the waiting period for pre-existing diseases?", chunks, client)

    # 48 months in answer contradicts 36 months in citation -> must fail validation
    assert res.citations_valid is False
    assert res.manual_review_required is True
    assert res.confidence == "low"
    assert res.verdict == "depends"
    assert any("contradicts" in w for w in res.warnings)


def test_percentage_contradiction_rejected():
    """Ensure percentage mismatch between citation and answer triggers verification failure."""
    question = "What is the co-payment percentage?"
    answer = "The co-payment is 20% on all claims."
    quote = "A co-payment of 10% applies to senior citizens."

    err = _check_citation_relevance(quote, question, answer)
    assert err is not None
    assert "percentage" in err
    assert "contradicts" in err


def test_generic_hospitalization_quote_cannot_substantiate_brain_surgery():
    """Scenario F: Generic room rent quote cannot substantiate specific brain surgery claim."""
    question = "Tell me whether it covers anything related to Brain Surgery and all."
    answer = "Brain surgery is covered up to Sum Insured."
    generic_room_quote = "Room rent, boarding and nursing expenses up to Single Private A/C Room."

    err = _check_citation_relevance(generic_room_quote, question, answer)
    assert err is not None
    assert "generic" in err or "topical" in err or "brain" in err


def test_specific_surgery_silent_in_policy_returns_qualified_depends():
    """Scenario F: Named procedure with only generic hospitalization in policy yields depends."""
    chunks = make_policy_chunks()  # contains hospitalization and room rent, but no brain surgery
    client = MockStructuredClient({
        "verdict": "covered",
        "answer": "Brain surgery is covered under In-Patient Hospitalization.",
        "citations": [{"chunk_id": "P1-C1", "quote": "Intensive Care Unit (ICU) charges and surgeon fees are covered up to the Sum Insured."}],
        "confidence": "high",
        "caveats": [],
    })

    res = answer_question("Tell me whether it covers anything related to Brain Surgery and all.", chunks, client)

    # Must NOT return unqualified 'covered' when specific procedure is absent from policy
    assert res.verdict == "depends"
    assert res.confidence == "low"
    assert res.manual_review_required is True
    assert any("brain surgery" in c.lower() for c in res.caveats)


def test_summary_category_rejects_unusable_fragments_and_headings():
    """Section 3: Summary categories must reject headers like 'g) Cumulative Bonus' or colons."""
    from backend.qa.intent import _is_unusable_fragment

    assert _is_unusable_fragment("Claims Procedure for Reimbursement:") is True
    assert _is_unusable_fragment("g) Cumulative Bonus") is True
    assert _is_unusable_fragment("SECTION IV: EXCLUSIONS") is True
    assert _is_unusable_fragment("expenses as charged by the Hospital/Nursing Home Excluding registration and") is True

    # Real substantive clause with verbs and operative rules must be accepted
    good_clause = "Intensive Care Unit (ICU) charges and surgeon fees are covered up to the Sum Insured."
    assert _is_unusable_fragment(good_clause) is False


def test_summary_with_only_headings_marks_partial_not_verified():
    """Section 3 & Scenario B: If a policy has only headings, summary is marked partial and not verified."""
    fragment_chunks = [
        PolicyChunk("P1-C1", 1, "Claims Procedure for Reimbursement:\ng) Cumulative Bonus\nSECTION IV: EXCLUSIONS"),
    ]
    summary_data = handle_policy_summary(fragment_chunks)

    assert summary_data["verdict"] == "summary"
    # No substantive clauses were found, so confidence is low and manual review is required
    assert summary_data["confidence"] == "low"
    assert summary_data["citations_valid"] is False
    assert summary_data["manual_review_required"] is True
    assert len(summary_data["citations"]) == 0


def test_hospital_cash_deductible_isolated_from_unrelated_queries():
    """Scenario E: 1-day deductible applies ONLY to Hospital Cash, NOT to room rent or cataract."""
    chunks = make_policy_chunks()
    client = MockStructuredClient({
        "verdict": "covered",
        "answer": "Room rent is payable for 1 day hospitalization.",
        "citations": [{"chunk_id": "P1-C1", "quote": "Room rent, boarding and nursing expenses up to Single Private A/C Room."}],
        "confidence": "high",
        "caveats": [],
    })

    res = answer_question("If I am hospitalized for 1 day, will my room rent be covered?", chunks, client)

    # Must NOT be marked excluded due to the Hospital Cash deductible!
    assert res.verdict == "covered"
    assert not any("mandatory 1-day deductible" in c for c in res.caveats)


def test_unsupported_question_returns_not_stated_without_hallucinations():
    """Scenario G: Questions completely unsupported by policy must return not_stated."""
    chunks = make_policy_chunks()
    client = MockStructuredClient({
        "verdict": "not_stated",
        "answer": "The provided policy text contains no information regarding veterinary pet care.",
        "citations": [],
        "confidence": "low",
        "caveats": ["Not mentioned in policy."],
    })

    res = answer_question("Is pet dog surgery covered under this health policy?", chunks, client)

    assert res.verdict == "not_stated"
    assert res.confidence == "low"
    assert len(res.citations) == 0

