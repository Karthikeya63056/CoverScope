"""Safe basic validation and opening of user-provided PDF bytes."""
from dataclasses import dataclass
from pathlib import Path
import pymupdf


class PDFValidationError(ValueError):
    """Raised when the uploaded file is not a usable PDF."""


@dataclass
class OpenedPDF:
    document: pymupdf.Document
    filename: str
    size_bytes: int


def open_pdf_bytes(data: bytes, filename: str = "uploaded.pdf") -> OpenedPDF:
    if not data:
        raise PDFValidationError("The uploaded file is empty.")
    if not filename.lower().endswith(".pdf"):
        raise PDFValidationError("Please upload a PDF file.")
    if not data.startswith(b"%PDF-"):
        raise PDFValidationError(
            "The file does not appear to be a valid PDF. Please choose a PDF document."
        )
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise PDFValidationError(
            "The PDF could not be opened. It may be damaged or password-protected."
        ) from exc

    if document.is_encrypted:
        document.close()
        raise PDFValidationError(
            "Password-protected PDFs are not supported in this version."
        )
    if document.page_count == 0:
        document.close()
        raise PDFValidationError("The PDF contains no pages.")

    return OpenedPDF(document=document, filename=Path(filename).name, size_bytes=len(data))
