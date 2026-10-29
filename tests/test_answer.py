import pytest

from backend.document_processing.chunker import PolicyChunk
from backend.document_processing.quality_checks import QualityReport
from backend.llm.errors import LLMAuthError, LLMResponseError
from backend.qa.answer import (
    MIN_QUOTE_MATCH_CHARS,
    answer_question,
    build_user_prompt,
    verify_citations,
)
from backend.qa.retrieval import RetrievedChunk
from backend.qa.schemas import Citation

EXCLUSION_TEXT = (
    "Expenses related to the treatment of a pre-existing disease are "
    "excluded until the expiry of 36 months of continuous coverage."
)
COVER_TEXT = (
    "Out-patient medical consultations are payable up to Rs. 300 per "
    "consultation."
)
EXCLUSION = PolicyChunk("P10-C1", 10, EXCLUSION_TEXT)
COVER = PolicyChunk("P9-C1", 9, COVER_TEXT)


class FakeClient:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.calls = 0
        self.last_kwargs = None

    def complete_json(self, *, system_prompt, user_prompt, schema=None):
        self.calls += 1
        self.last_kwargs = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "schema": schema,
        }
        if self.error is not None:
            raise self.error
        return self.payload


def model_payload(
    verdict: str,
    *,
    chunk_id: str = "P10-C1",
    quote: str = EXCLUSION_TEXT,
    confidence: str = "high",
    caveats=None,
    citations=None,
):
    if citations is None:
        citations = [{"chunk_id": chunk_id, "quote": quote}] if chunk_id else []
    return {
        "verdict": verdict,
        "answer": "Model explanation.",
        "citations": citations,
        "confidence": confidence,
        "caveats": caveats or [],
    }


def quality_report(table_review_pages=()):
    return QualityReport(
        total_pages=10,
        extracted_characters=1000,
        text_poor_pages=[],
        image_heavy_pages=[],
        table_review_pages=list(table_review_pages),
        warnings=[],
        errors=[],
    )


@pytest.mark.parametrize(
    "verdict",
    ["covered", "excluded", "depends", "not_stated"],
)
def test_all_four_verdicts_are_accepted(verdict):
    if verdict == "not_stated":
        payload = model_payload("not_stated", chunk_id=None)
    elif verdict == "covered":
        payload = model_payload("covered", chunk_id="P9-C1", quote=COVER_TEXT)
    else:
        payload = model_payload(verdict)
    client = FakeClient(payload)

    question = "Are outpatient consultations covered?" if verdict == "covered" else (
        "Is a pre-existing disease covered?"
    )
    chunks = [EXCLUSION, COVER]
    result = answer_question(question, chunks, client)

    assert result.verdict == verdict
    assert result.citations_valid
    assert not result.manual_review_required


def test_valid_citation_derives_page_from_trusted_metadata():
    client = FakeClient(model_payload("excluded"))
    result = answer_question("Is a pre-existing disease covered?", [EXCLUSION], client)

    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == "P10-C1"
    assert result.citations[0].page_number == 10
    assert result.cited_pages == (10,)


def test_unknown_chunk_id_triggers_safe_manual_review():
    client = FakeClient(model_payload("excluded", chunk_id="P99-C9"))
    result = answer_question("Is a pre-existing disease covered?", [EXCLUSION], client)

    assert result.verdict == "depends"
    assert not result.citations_valid
    assert result.manual_review_required
    assert result.confidence == "low"
    assert result.unverified_answer == "Model explanation."
    assert any("Unknown chunk ID" in warning for warning in result.warnings)


def test_fabricated_quotation_triggers_safe_manual_review():
    client = FakeClient(
        model_payload(
            "excluded",
            quote="This sentence does not appear anywhere in the policy.",
        )
    )
    result = answer_question("Is a pre-existing disease covered?", [EXCLUSION], client)

    assert result.verdict == "depends"
    assert not result.citations_valid
    assert result.manual_review_required
    assert any("does not match" in warning for warning in result.warnings)


def test_short_quotation_is_rejected():
    client = FakeClient(model_payload("excluded", quote="covered"))
    result = answer_question("Is a pre-existing disease covered?", [EXCLUSION], client)

    assert not result.citations_valid
    assert result.manual_review_required


@pytest.mark.parametrize("degenerate_quote", [".", "...", "a", ".,.", "short"])
def test_degenerate_punctuation_and_empty_quotes_are_rejected(degenerate_quote):
    client = FakeClient(model_payload("excluded", quote=degenerate_quote))
    result = answer_question("Is a pre-existing disease covered?", [EXCLUSION], client)

    assert not result.citations_valid
    assert result.manual_review_required
    assert any("too short or lacks substantive text" in w for w in result.warnings)


def test_definitive_verdict_without_citations_is_not_accepted():
    client = FakeClient(model_payload("covered", chunk_id=None))
    result = answer_question("Are outpatient consultations covered?", [COVER], client)

    assert result.verdict == "depends"
    assert not result.citations_valid
    assert result.manual_review_required


def test_not_stated_without_citations_is_a_valid_abstention():
    client = FakeClient(model_payload("not_stated", chunk_id=None))
    result = answer_question("Is a pre-existing disease covered?", [EXCLUSION], client)

    assert result.verdict == "not_stated"
    assert result.citations_valid
    assert not result.manual_review_required


def test_empty_evidence_does_not_call_the_model():
    client = FakeClient(model_payload("excluded"))
    result = answer_question("Is car theft covered?", [EXCLUSION], client)

    assert client.calls == 0
    assert result.verdict == "not_stated"
    assert result.citations_valid
    assert not result.manual_review_required
    assert any("does not establish" in caveat for caveat in result.caveats)


def test_empty_question_raises_value_error():
    with pytest.raises(ValueError):
        answer_question("   ", [EXCLUSION], FakeClient())


def test_api_failure_propagates():
    client = FakeClient(error=LLMAuthError("bad key"))
    with pytest.raises(LLMAuthError):
        answer_question("Is a pre-existing disease covered?", [EXCLUSION], client)


def test_malformed_model_output_is_rejected():
    client = FakeClient({"verdict": "excluded"})
    with pytest.raises(LLMResponseError):
        answer_question("Is a pre-existing disease covered?", [EXCLUSION], client)


def test_explicit_unreliable_page_forces_manual_review():
    client = FakeClient(model_payload("excluded"))
    result = answer_question(
        "Is a pre-existing disease covered?",
        [EXCLUSION],
        client,
        unreliable_pages=(10,),
    )

    assert result.verdict == "depends"
    assert result.citations_valid
    assert result.manual_review_required
    assert result.confidence == "low"
    assert result.unverified_answer == "Model explanation."
    assert any("explicitly flagged" in warning.lower() for warning in result.warnings)


def test_heuristic_table_flag_adds_caveat_but_not_manual_review():
    client = FakeClient(model_payload("excluded"))
    result = answer_question(
        "Is a pre-existing disease covered?",
        [EXCLUSION],
        client,
        quality_report=quality_report(table_review_pages=[10]),
    )

    assert result.verdict == "excluded"
    assert result.citations_valid
    assert not result.manual_review_required
    assert any("table-review heuristic" in caveat for caveat in result.caveats)


def test_confidence_is_independent_of_citation_validity():
    valid = answer_question(
        "Is a pre-existing disease covered?",
        [EXCLUSION],
        FakeClient(model_payload("excluded", confidence="medium")),
    )
    invalid = answer_question(
        "Is a pre-existing disease covered?",
        [EXCLUSION],
        FakeClient(model_payload("excluded", quote="fabricated text here")),
    )

    assert valid.confidence == "medium"
    assert valid.citations_valid
    assert invalid.confidence == "low"
    assert not invalid.citations_valid


def test_ligature_difference_does_not_invalidate_a_quote():
    source = "The de\ufb01nition of pre-existing disease is stated in this policy."
    chunk = PolicyChunk("P3-C1", 3, source)
    client = FakeClient(
        model_payload(
            "excluded",
            chunk_id="P3-C1",
            quote="The definition of pre-existing disease",
        )
    )
    result = answer_question("definition of pre-existing disease", [chunk], client)
    assert result.citations_valid
    assert result.citations[0].page_number == 3


def test_prompt_contains_chunk_ids_pages_and_question():
    evidence = [
        RetrievedChunk("P10-C1", 10, EXCLUSION_TEXT, 1.0, ("disease",)),
    ]
    prompt = build_user_prompt("Is it covered?", evidence)
    assert "[P10-C1 | page 10]" in prompt
    assert EXCLUSION_TEXT in prompt
    assert "Is it covered?" in prompt


def test_verify_citations_reports_each_bad_citation():
    evidence = [
        RetrievedChunk("P10-C1", 10, EXCLUSION_TEXT, 1.0, ("disease",)),
    ]
    verified, problems = verify_citations(
        [
            Citation(chunk_id="P10-C1", quote="not in the source at all"),
            Citation(chunk_id="P404", quote=EXCLUSION_TEXT),
            Citation(chunk_id="P10-C1", quote="x" * MIN_QUOTE_MATCH_CHARS),
        ],
        evidence,
    )
    assert verified == ()
    assert len(problems) == 3


def test_verify_citations_rejects_domain_mismatched_quote():
    source_text = (
        "Waiting Periods: Delivery Expenses and New Born: 24 months. "
        "Bariatric Surgery: 36 months."
    )
    evidence = [
        RetrievedChunk("P12-C1", 12, source_text, 1.0, ("bariatric",)),
    ]
    # Citation is literally in chunk, but is about maternity/newborn while query is about bariatric surgery
    verified, problems = verify_citations(
        [Citation(chunk_id="P12-C1", quote="Delivery Expenses and New Born: 24 months")],
        evidence,
        question="What is the waiting period for bariatric surgery?",
        answer="The waiting period for bariatric surgery is 36 months.",
    )
    assert len(verified) == 0
    assert len(problems) == 1
    assert "pertains to maternity_newborn" in problems[0]


def test_verify_citations_rejects_topically_unrelated_quote():
    source_text = (
        "Expenses related to the treatment of a pre-existing disease are "
        "excluded until the expiry of 36 months of continuous coverage."
    )
    evidence = [
        RetrievedChunk("P10-C1", 10, source_text, 1.0, ("room",)),
    ]
    # Quote is in source, but has zero content words in common with room rent inquiry
    verified, problems = verify_citations(
        [Citation(chunk_id="P10-C1", quote="pre-existing disease are excluded until")],
        evidence,
        question="What room rent category is permitted?",
        answer="Single Private A/C Room is permitted under this policy.",
    )
    assert len(verified) == 0
    assert len(problems) == 1
    assert "does not share topical relevance" in problems[0]


def test_verify_citations_accepts_topically_relevant_quote():
    source_text = (
        "Waiting Periods: Delivery Expenses and New Born: 24 months. "
        "Bariatric Surgery: 36 months."
    )
    evidence = [
        RetrievedChunk("P12-C1", 12, source_text, 1.0, ("bariatric",)),
    ]
    verified, problems = verify_citations(
        [Citation(chunk_id="P12-C1", quote="Bariatric Surgery: 36 months")],
        evidence,
        question="What is the waiting period for bariatric surgery?",
        answer="The waiting period for bariatric surgery is 36 months.",
    )
    assert len(verified) == 1
    assert len(problems) == 0
    assert verified[0].quote == "Bariatric Surgery: 36 months"


def test_verify_citations_rejects_duration_contradiction():
    source_text = "Bariatric Surgery: 36 months waiting period applies."
    evidence = [RetrievedChunk("P12-C1", 12, source_text, 1.0, ("bariatric",))]
    verified, problems = verify_citations(
        [Citation(chunk_id="P12-C1", quote="Bariatric Surgery: 36 months")],
        evidence,
        question="What is the waiting period for bariatric surgery?",
        answer="The waiting period for bariatric surgery is 24 months.",
    )
    assert len(verified) == 0
    assert len(problems) == 1
    assert "duration" in problems[0] and "contradicts" in problems[0]


def test_verify_citations_rejects_percentage_contradiction():
    source_text = "This policy is subject to Co-payment of 10% of each and every claim amount."
    evidence = [RetrievedChunk("P4-C1", 4, source_text, 1.0, ("copay",))]
    verified, problems = verify_citations(
        [Citation(chunk_id="P4-C1", quote="Co-payment of 10% of each and every claim")],
        evidence,
        question="What is the co-payment percentage for senior citizens?",
        answer="The mandatory co-payment for senior citizens entering above 61 is 20%.",
    )
    assert len(verified) == 0
    assert len(problems) == 1
    assert "percentage" in problems[0] and "contradicts" in problems[0]


