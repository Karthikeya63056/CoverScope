from backend.document_processing.chunker import chunk_pages
from backend.document_processing.text_extractor import ExtractedPage


def page(number: int, text: str) -> ExtractedPage:
    return ExtractedPage(number, text, len(text), 1, 0)


def test_chunk_ids_encode_page_and_chunk():
    chunks = chunk_pages(
        [page(12, "abcdefghij klmnopqrst uvwxyz")],
        chunk_chars=12,
    )
    assert chunks[0].chunk_id == "P12-C1"
    assert all(chunk.page_number == 12 for chunk in chunks)
    assert [chunk.chunk_id for chunk in chunks] == [
        f"P12-C{i}" for i in range(1, len(chunks) + 1)
    ]


def test_no_overlap_or_character_loss_except_boundary_whitespace():
    original = "alpha beta gamma delta epsilon zeta"
    chunks = chunk_pages([page(2, original)], chunk_chars=12)
    joined = " ".join(chunk.text for chunk in chunks)
    assert joined == original


def test_empty_page_creates_no_chunks():
    assert chunk_pages([page(1, "   ")]) == []


def test_orphan_trailing_fragment_is_merged_on_same_page():
    # If text has 1,830 chars with chunk_chars=1800, trailing 30 chars must merge into P1-C1 rather than creating P1-C2
    base_text = "word " * 358  # ~1790 chars
    tail_text = "This benefit is subject to 1 day Deductible."  # ~44 chars
    full_text = base_text + tail_text
    chunks = chunk_pages([page(1, full_text)], chunk_chars=1800)
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "P1-C1"
    assert "This benefit is subject to 1 day Deductible." in chunks[0].text


def test_page_boundaries_are_strictly_isolated():
    # Multiple pages must never merge across page boundaries
    p1 = page(1, "Page one text content here.")
    p2 = page(2, "Page two text content here.")
    chunks = chunk_pages([p1, p2], chunk_chars=1800)
    assert len(chunks) == 2
    assert chunks[0].chunk_id == "P1-C1"
    assert chunks[0].page_number == 1
    assert "Page one" in chunks[0].text and "Page two" not in chunks[0].text
    assert chunks[1].chunk_id == "P2-C1"
    assert chunks[1].page_number == 2
    assert "Page two" in chunks[1].text and "Page one" not in chunks[1].text

