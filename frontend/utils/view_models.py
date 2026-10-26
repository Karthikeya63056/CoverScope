"""Presentation-only view models for CoverScope UI components."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from backend.qa.answer import AnswerResult, VerifiedCitation
from frontend.messages import VERDICT_LABELS, VERDICT_SUMMARIES
from frontend.utils.formatters import confidence_label, verdict_label


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
