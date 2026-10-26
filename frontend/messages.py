"""Presentation copy and safe error translation for the Streamlit UI.

This module deliberately does not import Streamlit so it can be unit-tested
without a Streamlit runtime. It never includes exception text, document text,
or credentials in user-facing messages.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.llm.errors import (
    LLMAuthError,
    LLMConfigError,
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
    LLMResponseError,
    LLMServiceError,
    LLMTimeoutError,
)

SUGGESTED_QUESTIONS: tuple[str, ...] = (
    "Is a pre-existing disease covered in month 20?",
    "What waiting period applies to specified diseases?",
    "What exclusions apply to this policy?",
    "Are room-rent limits dependent on the selected plan?",
)

VERDICT_LABELS: dict[str, str] = {
    "covered": "Covered",
    "excluded": "Excluded",
    "depends": "Depends",
    "not_stated": "Not stated",
}

VERDICT_SUMMARIES: dict[str, str] = {
    "covered": (
        "The policy wording affirmatively covers the requested benefit, subject "
        "to the conditions stated in the evidence."
    ),
    "excluded": (
        "The policy wording affirmatively excludes the requested benefit or says "
        "it is not payable."
    ),
    "depends": (
        "Coverage depends on a condition that the available wording or the "
        "question does not resolve, such as a plan, endorsement, or policy start date."
    ),
    "not_stated": (
        "The relevant provision was not found in the retrieved evidence. This "
        "does not establish that the benefit is excluded."
    ),
}

CONFIDENCE_LABELS: dict[str, str] = {
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}

MAX_QUESTION_CHARS = 500

MANUAL_REVIEW_MESSAGE = (
    "CoverScope could not verify every quotation, or the answer relies on a page "
    "flagged as unreliable for extraction. Treat this as a prompt for manual "
    "review, not as a coverage decision."
)

NOT_STATED_MESSAGE = (
    "“Not stated” means the relevant provision was not found in the available "
    "policy evidence. It does not mean the benefit is excluded. Check the policy "
    "schedule or ask a more specific question."
)


@dataclass(frozen=True)
class FriendlyError:
    """A safe message plus optional retry guidance for the UI."""

    message: str
    retry_after_seconds: int | None = None


def describe_llm_error(exc: BaseException) -> FriendlyError:
    """Translate an application-level LLM failure into safe UI copy.

    The exception's own text is intentionally never shown: provider errors can
    contain request details, and this keeps keys and document content out of the
    interface. Unknown failures get a generic message.
    """
    if isinstance(exc, LLMConfigError):
        return FriendlyError(
            "The AI provider is not configured. Add GROQ_API_KEY to the "
            "environment or the deployment secrets, then restart the app."
        )
    if isinstance(exc, LLMAuthError):
        return FriendlyError(
            "The AI provider rejected the configured credentials. Check the API "
            "key and try again."
        )
    if isinstance(exc, LLMRateLimitError):
        return FriendlyError(
            "The AI provider's rate limit was reached. Wait about a minute, then "
            "ask again.",
            retry_after_seconds=60,
        )
    if isinstance(exc, LLMTimeoutError):
        return FriendlyError(
            "The AI provider took too long to respond. Wait a moment, then try again."
        )
    if isinstance(exc, LLMConnectionError):
        return FriendlyError(
            "CoverScope could not reach the AI provider. Check the network "
            "connection and try again."
        )
    if isinstance(exc, LLMServiceError):
        return FriendlyError(
            "The AI provider is temporarily unavailable. Try again shortly."
        )
    if isinstance(exc, LLMResponseError):
        return FriendlyError(
            "The AI provider returned a response CoverScope could not use. Try "
            "rephrasing the question."
        )
    if isinstance(exc, LLMError):
        return FriendlyError(
            "The AI provider request failed. Wait a moment, then try again."
        )
    return FriendlyError(
        "Something went wrong while answering. Please try again."
    )
