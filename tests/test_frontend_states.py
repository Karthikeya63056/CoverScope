"""Focused tests for Stage G Empty States, Error Handling, and Privacy UI."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from frontend.components.empty_state import (
    render_empty_answer_state,
    render_empty_evidence_state,
    render_empty_policy_guidance,
)
from frontend.components.error_state import (
    render_answer_error,
    render_cooldown_warning,
    render_document_error,
    render_empty_question_warning,
)
from frontend.components.privacy_notice import (
    render_compact_privacy_callout,
    render_privacy_notice,
)


def test_empty_state_explains_next_action_without_duplicating_hero():
    with patch("streamlit.markdown") as mock_markdown:
        render_empty_policy_guidance()
        rendered = " ".join(call.args[0] for call in mock_markdown.call_args_list if call.args)

        assert "Select or drag a text-based health insurance policy PDF" in rendered
        assert "waiting periods" in rendered


def test_sanitized_errors_render_without_leaking_secrets_or_traces():
    secret_key = "gsk_secret_api_key_12345_should_not_leak"
    trace = "Traceback (most recent call last):\n  File 'internal.py', line 42"

    with patch("streamlit.error") as mock_error, patch("streamlit.markdown") as mock_markdown:
        render_document_error({
            "message": "The PDF could not be processed. It may be damaged or unsupported.",
            "errors": ("Could not read cross-reference table.",),
        })

        error_calls = [call.args[0] for call in mock_error.call_args_list if call.args]
        joined = " ".join(error_calls)

        assert secret_key not in joined
        assert trace not in joined
        assert "could not be processed" in joined


def test_rate_limit_messaging_preserves_cooldown_countdown():
    with patch("streamlit.error") as mock_error, patch("streamlit.info") as mock_info:
        render_answer_error(
            "The AI provider's rate limit was reached. Wait about a minute, then ask again.",
            cooldown_seconds=45,
        )

        mock_error.assert_called_once()
        info_calls = [call.args[0] for call in mock_info.call_args_list if call.args]
        assert any("45 seconds" in text for text in info_calls)
        assert any("will not retry automatically" in text for text in info_calls)


def test_privacy_notice_describes_actual_data_flow_without_unsupported_guarantees():
    with patch("streamlit.markdown") as mock_markdown, patch("streamlit.expander"):
        render_privacy_notice()

        rendered = " ".join(call.args[0] for call in mock_markdown.call_args_list if call.args)

        # Accurately documents that excerpts are sent to Groq
        assert "Groq" in rendered
        assert "In-memory processing" in rendered
        # Does not make false claims like "never leaves your device"
        assert "never leaves your device" not in rendered.lower()
        assert "100% confidential guarantee" not in rendered.lower()


def test_compact_privacy_callout_mentions_in_memory_and_groq():
    with patch("streamlit.info") as mock_info:
        render_compact_privacy_callout()

        info_calls = [call.args[0] for call in mock_info.call_args_list if call.args]
        assert any("in memory" in text.lower() for text in info_calls)
        assert any("Groq" in text for text in info_calls)


def test_empty_evidence_and_missing_answer_remain_understandable():
    with patch("streamlit.caption") as mock_caption:
        render_empty_answer_state()
        render_empty_evidence_state()

        caption_calls = [call.args[0] for call in mock_caption.call_args_list if call.args]
        assert any("Ask a question to see a verdict" in text for text in caption_calls)
        assert any("No verified quotations were returned" in text for text in caption_calls)


def test_validation_warnings_provide_clear_actionable_direction():
    with patch("streamlit.warning") as mock_warning:
        render_empty_question_warning()
        render_cooldown_warning()

        warning_calls = [call.args[0] for call in mock_warning.call_args_list if call.args]
        assert "Enter a question first." in warning_calls
        assert any("rate-limit cooldown" in text for text in warning_calls)
