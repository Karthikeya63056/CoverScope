import pymupdf
import pytest
from backend.document_processing.pdf_loader import open_pdf_bytes, PDFValidationError
from backend.document_processing.text_extractor import extract_pages


def test_rejects_non_pdf_extension():
    with pytest.raises(PDFValidationError):
        open_pdf_bytes(b"%PDF-1.4", "policy.txt")


def test_rejects_non_pdf_bytes():
    with pytest.raises(PDFValidationError):
        open_pdf_bytes(b"not a pdf", "policy.pdf")


def test_accepts_valid_pdf_and_extracts_text():
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Policy text")
    data = document.tobytes()
    document.close()

    opened = open_pdf_bytes(data, "policy.pdf")
    try:
        assert opened.filename == "policy.pdf"
        assert opened.document.page_count == 1
        assert "Policy text" in extract_pages(opened.document)[0].text
    finally:
        opened.document.close()
