"""Streamlit-agnostic workflow helpers for a single policy document.

The UI must not re-implement extraction, quality checks, retrieval, or citation
validation. These helpers wrap the existing backend pipeline so the CLI and the
Streamlit app share exactly the same behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Sequence

from backend.config import settings
from backend.document_processing.chunker import PolicyChunk, chunk_pages
from backend.document_processing.pdf_loader import PDFValidationError, open_pdf_bytes
from backend.document_processing.quality_checks import QualityReport, assess_quality
from backend.document_processing.text_extractor import ExtractedPage, extract_pages
from backend.qa.answer import AnswerResult, StructuredClient, answer_question


class PolicyProcessingError(ValueError):
    """A user-facing document problem with optional detail lines.

    ``message`` is safe to display. ``errors`` and ``warnings`` come from the
    existing quality report and never contain the document body or a secret.
    """

    def __init__(
        self,
        message: str,
        *,
        errors: Sequence[str] = (),
        warnings: Sequence[str] = (),
    ) -> None:
        super().__init__(message)
        self.errors = tuple(errors)
        self.warnings = tuple(warnings)


@dataclass(frozen=True)
class ProcessedPolicy:
    """Everything the UI needs to answer questions about one PDF."""

    fingerprint: str
    filename: str
    size_bytes: int
    page_count: int
    extracted_characters: int
    quality: QualityReport
    chunks: tuple[PolicyChunk, ...]
    pages: tuple[ExtractedPage, ...] = ()


def fingerprint(data: bytes, filename: str) -> str:
    """Stable identifier for a selected upload, without storing the document."""
    digest = hashlib.sha256()
    digest.update(filename.encode("utf-8", "replace"))
    digest.update(b"\0")
    digest.update(data)
    return digest.hexdigest()


def prepare_policy(
    data: bytes,
    filename: str,
    *,
    max_upload_bytes: int | None = None,
    max_extracted_chars: int | None = None,
    min_page_chars: int | None = None,
    chunk_chars: int | None = None,
) -> ProcessedPolicy:
    """Validate, extract, and chunk one PDF in memory.

    Oversized files and documents with too little extractable text are rejected
    with an actionable message. Text is never truncated.
    """
    upload_limit = (
        settings.max_upload_bytes if max_upload_bytes is None else max_upload_bytes
    )
    if len(data) > upload_limit:
        raise PolicyProcessingError(
            f"The PDF is {len(data) / 1_000_000:.1f} MB, above the "
            f"{upload_limit / 1_000_000:.1f} MB upload limit. Choose a smaller "
            "file; the document was not truncated."
        )

    try:
        opened = open_pdf_bytes(data, filename)
    except PDFValidationError as exc:
        raise PolicyProcessingError(str(exc)) from exc

    try:
        pages = extract_pages(opened.document)
    finally:
        opened.document.close()

    report = assess_quality(
        pages,
        min_page_chars=(
            settings.min_page_chars if min_page_chars is None else min_page_chars
        ),
        max_extracted_chars=(
            settings.max_extracted_chars
            if max_extracted_chars is None
            else max_extracted_chars
        ),
    )
    if not report.is_usable:
        raise PolicyProcessingError(
            "This PDF could not be used for evidence-grounded answers.",
            errors=report.errors,
            warnings=report.warnings,
        )

    chunks = chunk_pages(
        pages,
        chunk_chars=settings.chunk_chars if chunk_chars is None else chunk_chars,
    )
    if not chunks:
        raise PolicyProcessingError(
            "No usable text was found to search in this PDF.",
            warnings=report.warnings,
        )

    return ProcessedPolicy(
        fingerprint=fingerprint(data, filename),
        filename=filename,
        size_bytes=len(data),
        page_count=report.total_pages,
        extracted_characters=report.extracted_characters,
        quality=report,
        chunks=tuple(chunks),
        pages=tuple(pages),
    )


def ask_policy_question(
    question: str,
    policy: ProcessedPolicy,
    client: StructuredClient,
    *,
    top_k: int | None = None,
    unreliable_pages: Sequence[int] | None = None,
) -> AnswerResult:
    """Answer one question against an already-processed policy."""
    return answer_question(
        question,
        policy.chunks,
        client,
        top_k=settings.retrieval_top_k if top_k is None else top_k,
        unreliable_pages=(
            settings.unreliable_pages
            if unreliable_pages is None
            else tuple(unreliable_pages)
        ),
        quality_report=policy.quality,
    )
