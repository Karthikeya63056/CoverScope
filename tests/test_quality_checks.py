from backend.document_processing.quality_checks import assess_quality
from backend.document_processing.text_extractor import ExtractedPage


def p(number, text, blocks=1, images=0):
    return ExtractedPage(number, text, len(text), blocks, images)


def test_rejects_all_text_poor_document():
    report = assess_quality([p(1, ""), p(2, "  ")], min_page_chars=40)
    assert not report.is_usable
    assert any("scanned" in error.lower() for error in report.errors)


def test_flags_possible_table_pages():
    report = assess_quality([p(1, "x" * 100, blocks=30)])
    assert 1 in report.table_review_pages
    assert any("table" in warning.lower() for warning in report.warnings)


def test_configured_character_limit_is_enforced():
    report = assess_quality([p(1, "x" * 101)], max_extracted_chars=100)
    assert not report.is_usable
    assert any("exceeding" in error for error in report.errors)
