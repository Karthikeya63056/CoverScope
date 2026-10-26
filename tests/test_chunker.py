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
