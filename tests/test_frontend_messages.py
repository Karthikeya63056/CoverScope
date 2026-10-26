import pytest

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
from frontend.messages import (
    CONFIDENCE_LABELS,
    MANUAL_REVIEW_MESSAGE,
    MAX_QUESTION_CHARS,
    NOT_STATED_MESSAGE,
    SUGGESTED_QUESTIONS,
    VERDICT_LABELS,
    VERDICT_SUMMARIES,
    describe_llm_error,
)


def test_suggested_questions_cover_the_required_topics():
    joined = " ".join(SUGGESTED_QUESTIONS).lower()
    assert len(SUGGESTED_QUESTIONS) >= 4
    assert "pre-existing" in joined
    assert "specified disease" in joined
    assert "exclusion" in joined
    assert "room-rent" in joined


def test_verdict_and_confidence_labels_cover_backend_values():
    assert set(VERDICT_LABELS) == {"covered", "excluded", "depends", "not_stated"}
    assert set(VERDICT_SUMMARIES) == set(VERDICT_LABELS)
    assert set(CONFIDENCE_LABELS) == {"high", "medium", "low"}
    assert 0 < MAX_QUESTION_CHARS <= 2_000
    assert "does not mean" in NOT_STATED_MESSAGE.lower()
    assert "manual review" in MANUAL_REVIEW_MESSAGE.lower()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (LLMConfigError("missing"), "GROQ_API_KEY"),
        (LLMAuthError("bad"), "credentials"),
        (LLMRateLimitError("slow"), "rate limit"),
        (LLMTimeoutError("slow"), "too long"),
        (LLMConnectionError("offline"), "could not reach"),
        (LLMServiceError("down"), "temporarily unavailable"),
        (LLMResponseError("bad json"), "could not use"),
        (LLMError("generic"), "request failed"),
        (RuntimeError("unexpected"), "Something went wrong"),
    ],
)
def test_llm_errors_become_friendly_messages(error, expected):
    friendly = describe_llm_error(error)
    assert expected.lower() in friendly.message.lower()


def test_rate_limit_includes_a_retry_delay():
    friendly = describe_llm_error(LLMRateLimitError("slow"))
    assert friendly.retry_after_seconds == 60


def test_error_copy_never_echoes_exception_text_or_secrets():
    secret = "fake-credential-value-that-must-not-appear"
    errors = [
        LLMAuthError(secret),
        LLMRateLimitError(secret),
        LLMTimeoutError(secret),
        LLMResponseError(secret),
        RuntimeError(secret),
    ]
    for error in errors:
        message = describe_llm_error(error).message
        assert secret not in message
