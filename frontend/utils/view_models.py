"""Presentation-only view models for CoverScope UI components."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from backend.qa.answer import AnswerResult, VerifiedCitation
from frontend.messages import VERDICT_LABELS, VERDICT_SUMMARIES
from frontend.utils.formatters import confidence_label, escape_md, format_bytes, verdict_label


@dataclass(frozen=True)
class DocumentViewModel:
    """Presentation model wrapping a ProcessedPolicy for structured display."""

    filename: str
    escaped_filename: str
    page_count: int
    page_count_display: str
    size_bytes: int
    file_size_display: str
    extracted_characters: int
    extracted_characters_display: str
    chunk_count: int
    chunk_count_display: str
    status_label: str
    text_poor_pages: tuple[int, ...]
    table_review_pages: tuple[int, ...]
    quality_warnings: tuple[str, ...]
    has_warnings: bool

    @classmethod
    def from_policy(cls, policy: Any) -> DocumentViewModel:
        raw_filename = getattr(policy, "filename", "Unnamed Policy.pdf") or "Unnamed Policy.pdf"
        pages = int(getattr(policy, "page_count", 0) or 0)
        size = int(getattr(policy, "size_bytes", 0) or 0)
        chars = int(getattr(policy, "extracted_characters", 0) or 0)
        chunks = getattr(policy, "chunks", ()) or ()
        chunk_count = len(chunks)

        quality = getattr(policy, "quality", None)
        text_poor = tuple(getattr(quality, "text_poor_pages", ()) or ())
        table_review = tuple(getattr(quality, "table_review_pages", ()) or ())
        warnings = tuple(getattr(quality, "warnings", ()) or ())

        has_warnings = bool(text_poor or table_review or warnings)

        return cls(
            filename=raw_filename,
            escaped_filename=escape_md(raw_filename),
            page_count=pages,
            page_count_display=f"{pages:,}",
            size_bytes=size,
            file_size_display=format_bytes(size),
            extracted_characters=chars,
            extracted_characters_display=f"{chars:,}",
            chunk_count=chunk_count,
            chunk_count_display=f"{chunk_count:,}",
            status_label="Extracted · Ready for Q&A",
            text_poor_pages=text_poor,
            table_review_pages=table_review,
            quality_warnings=warnings,
            has_warnings=has_warnings,
        )


@dataclass(frozen=True)
class VerdictViewModel:
    """Presentation data for a verdict outcome."""

    verdict_key: str
    display_label: str
    summary_text: str
    badge_class: str
    is_covered: bool
    is_excluded: bool
    is_depends: bool
    is_not_stated: bool

    @classmethod
    def from_verdict(cls, verdict: str) -> VerdictViewModel:
        clean = verdict.lower().strip()
        return cls(
            verdict_key=clean,
            display_label=verdict_label(clean),
            summary_text=VERDICT_SUMMARIES.get(clean, ""),
            badge_class=f"cs-badge-{clean.replace('_', '-')}",
            is_covered=clean == "covered",
            is_excluded=clean == "excluded",
            is_depends=clean == "depends",
            is_not_stated=clean == "not_stated",
        )


@dataclass(frozen=True)
class AnswerViewModel:
    """Presentation model wrapping an AnswerResult for structured rendering."""

    verdict: VerdictViewModel
    answer_text: str
    manual_review_required: bool
    citations_valid: bool
    confidence_display: str
    cited_pages_display: str
    citations: Sequence[VerifiedCitation]
    caveats: Sequence[str]
    warnings: Sequence[str]
    unverified_answer: str | None

    @classmethod
    def from_result(cls, result: AnswerResult) -> AnswerViewModel:
        manual_review = result.manual_review_required or not result.citations_valid
        pages_str = ", ".join(map(str, result.cited_pages)) if result.cited_pages else "None"
        distinct_caveats = [item for item in result.caveats if item not in result.warnings]

        return cls(
            verdict=VerdictViewModel.from_verdict(result.verdict),
            answer_text=result.answer,
            manual_review_required=manual_review,
            citations_valid=result.citations_valid,
            confidence_display=confidence_label(result.confidence),
            cited_pages_display=pages_str,
            citations=result.citations,
            caveats=distinct_caveats,
            warnings=result.warnings,
            unverified_answer=result.unverified_answer,
        )
