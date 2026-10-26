import pytest

from backend.config import DEFAULT_MAX_EXTRACTED_CHARS
from backend.document_processing.quality_checks import assess_quality
from backend.document_processing.text_extractor import ExtractedPage
from backend.qa.reliability import is_explicitly_unreliable, parse_page_selection


def page(number: int, text: str) -> ExtractedPage:
    return ExtractedPage(number, text, len(text), 1, 0)


def test_default_document_limit_is_250000():
    assert DEFAULT_MAX_EXTRACTED_CHARS == 250_000


def test_oversized_document_is_rejected_not_truncated():
    report = assess_quality(
        [page(1, "x" * (DEFAULT_MAX_EXTRACTED_CHARS + 1))],
        max_extracted_chars=DEFAULT_MAX_EXTRACTED_CHARS,
    )
    assert not report.is_usable
    assert any("exceeding" in error for error in report.errors)
    assert any("250,000" in error for error in report.errors)


def test_parse_page_selection_accepts_numbers_and_ranges():
    assert parse_page_selection("50, 51-52") == (50, 51, 52)
    assert parse_page_selection(" 8 ") == (8,)
    assert parse_page_selection("") == ()
    assert parse_page_selection(None) == ()


@pytest.mark.parametrize("value", ["abc", "5-3", "0", "-2", "1,,x"])
def test_parse_page_selection_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        parse_page_selection(value)


def test_explicit_unreliable_page_lookup():
    assert is_explicitly_unreliable(51, (50, 51, 52))
    assert not is_explicitly_unreliable(49, (50, 51, 52))
