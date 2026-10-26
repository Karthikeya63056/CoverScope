from backend.document_processing.chunker import PolicyChunk
from backend.qa.retrieval import extract_query_terms, retrieve_chunks


def chunk(chunk_id: str, page: int, text: str) -> PolicyChunk:
    return PolicyChunk(chunk_id=chunk_id, page_number=page, text=text)


CHUNKS = [
    chunk(
        "P10-C1",
        10,
        "Expenses related to the treatment of a pre-existing disease are "
        "excluded until the expiry of 36 months of continuous coverage.",
    ),
    chunk(
        "P10-C2",
        10,
        "Expenses related to a specified disease or procedure are excluded "
        "until the expiry of 24 months of continuous coverage.",
    ),
    chunk(
        "P9-C1",
        9,
        "Out-patient medical consultations are payable up to Rs. 300 per "
        "consultation. This benefit is payable only on a cashless basis.",
    ),
    chunk(
        "P13-C1",
        13,
        "Treatment for alcoholism, drug or substance abuse, or any addictive "
        "condition and consequences thereof is excluded.",
    ),
]


def test_pre_existing_query_ranks_the_waiting_period_clause_first():
    results = retrieve_chunks(
        "Is a pre-existing disease covered in month 20?", CHUNKS
    )
    assert results
    assert results[0].chunk_id == "P10-C1"
    assert results[0].page_number == 10
    assert "pre-existing" in results[0].text
    assert "pre" in results[0].matched_terms
    assert "existing" in results[0].matched_terms


def test_exclusion_query_ranks_the_exclusion_clause():
    results = retrieve_chunks("Is alcoholism covered?", CHUNKS)
    assert results[0].chunk_id == "P13-C1"


def test_outpatient_synonym_and_plural_normalization_work():
    results = retrieve_chunks("Are outpatient consultations covered?", CHUNKS)
    assert results[0].chunk_id == "P9-C1"


def test_stop_words_alone_return_no_results():
    assert extract_query_terms("the of and is a") == []
    assert retrieve_chunks("the of and is a", CHUNKS) == []


def test_empty_question_and_empty_document_return_empty_lists():
    assert retrieve_chunks("", CHUNKS) == []
    assert retrieve_chunks("   ", CHUNKS) == []
    assert retrieve_chunks("pre-existing disease", []) == []


def test_irrelevant_question_returns_no_matches():
    assert retrieve_chunks("Is car theft covered?", CHUNKS) == []


def test_top_k_is_applied_and_ranking_is_deterministic():
    first = retrieve_chunks("disease excluded months", CHUNKS, top_k=2)
    second = retrieve_chunks("disease excluded months", CHUNKS, top_k=2)
    assert len(first) == 2
    assert [item.chunk_id for item in first] == [item.chunk_id for item in second]


def test_returned_text_is_the_original_source_text():
    results = retrieve_chunks("pre-existing disease", CHUNKS)
    source = {item.chunk_id: item.text for item in CHUNKS}
    for result in results:
        assert result.text == source[result.chunk_id]


def test_top_k_must_be_positive():
    import pytest

    with pytest.raises(ValueError):
        retrieve_chunks("disease", CHUNKS, top_k=0)
