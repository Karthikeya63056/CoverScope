import json
from types import SimpleNamespace

import pytest

from backend.config import DEFAULT_GROQ_MAX_COMPLETION_TOKENS, DEFAULT_GROQ_MODEL
from backend.llm.errors import (
    LLMAuthError,
    LLMConfigError,
    LLMConnectionError,
    LLMRateLimitError,
    LLMResponseError,
    LLMServiceError,
    LLMTimeoutError,
)
from backend.llm.groq_client import GroqClient


class FakeCompletions:
    def __init__(self, effects):
        self.effects = list(effects)
        self.calls = 0
        self.payloads = []

    def create(self, **kwargs):
        self.payloads.append(kwargs)
        effect = self.effects[self.calls]
        self.calls += 1
        if isinstance(effect, BaseException):
            raise effect
        return effect


class FakeSDK:
    def __init__(self, effects):
        self.chat = SimpleNamespace(completions=FakeCompletions(effects))


def response(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


class AuthenticationError(Exception):
    pass


class RateLimitError(Exception):
    pass


class APITimeoutError(Exception):
    pass


class APIConnectionError(Exception):
    pass


class BadRequestError(Exception):
    pass


class APIStatusError(Exception):
    pass


def make_client(effects, **kwargs):
    sdk = FakeSDK(effects)
    client = GroqClient(sdk_client=sdk, **kwargs)
    return client, sdk


def test_complete_json_uses_strict_schema_and_returns_dict():
    payload = {"verdict": "excluded"}
    client, sdk = make_client([response(json.dumps(payload))])

    result = client.complete_json(system_prompt="system", user_prompt="user")

    assert result == payload
    request = sdk.chat.completions.payloads[0]
    assert request["model"] == DEFAULT_GROQ_MODEL
    assert request["response_format"]["type"] == "json_schema"
    assert request["response_format"]["json_schema"]["strict"] is True
    assert request["max_completion_tokens"] == DEFAULT_GROQ_MAX_COMPLETION_TOKENS
    assert request["reasoning_effort"] == "low"


def test_custom_schema_is_forwarded():
    client, sdk = make_client([response("{}")])
    schema = {"type": "object", "properties": {}}
    client.complete_json(system_prompt="s", user_prompt="u", schema=schema)
    assert sdk.chat.completions.payloads[0]["response_format"]["json_schema"]["schema"] == schema


def test_rate_limit_is_retried_after_server_guidance():
    error = RateLimitError("slow down")
    error.response = SimpleNamespace(headers={"retry-after": "0"})
    delays = []
    client, sdk = make_client(
        [error, response('{"ok": true}')], max_retries=2, sleep=delays.append
    )

    result = client.complete_json(system_prompt="s", user_prompt="u")

    assert result == {"ok": True}
    assert sdk.chat.completions.calls == 2
    assert delays == [0.0]


def test_authentication_failure_is_not_retried():
    delays = []
    client, sdk = make_client(
        [AuthenticationError("bad key"), response("{}")],
        max_retries=3,
        sleep=delays.append,
    )

    with pytest.raises(LLMAuthError):
        client.complete_json(system_prompt="s", user_prompt="u")

    assert sdk.chat.completions.calls == 1
    assert delays == []


def test_timeout_uses_bounded_backoff_then_fails():
    delays = []
    client, sdk = make_client(
        [APITimeoutError(), APITimeoutError(), APITimeoutError()],
        max_retries=2,
        sleep=delays.append,
    )

    with pytest.raises(LLMTimeoutError):
        client.complete_json(system_prompt="s", user_prompt="u")

    assert sdk.chat.completions.calls == 3
    assert delays == [1.0, 2.0]


def test_connection_failure_maps_to_application_error():
    client, _ = make_client([APIConnectionError()], max_retries=0)
    with pytest.raises(LLMConnectionError):
        client.complete_json(system_prompt="s", user_prompt="u")


def test_server_error_is_retryable():
    error = APIStatusError("unavailable")
    error.response = SimpleNamespace(status_code=503)
    client, sdk = make_client([error, response('{"ok": true}')], max_retries=1)
    assert client.complete_json(system_prompt="s", user_prompt="u") == {"ok": True}
    assert sdk.chat.completions.calls == 2


def test_bad_request_is_not_retried():
    client, sdk = make_client([BadRequestError("bad")], max_retries=3)
    with pytest.raises(LLMResponseError):
        client.complete_json(system_prompt="s", user_prompt="u")
    assert sdk.chat.completions.calls == 1


def test_malformed_json_is_reported():
    client, _ = make_client([response("not json")])
    with pytest.raises(LLMResponseError):
        client.complete_json(system_prompt="s", user_prompt="u")


def test_empty_response_is_reported():
    client, _ = make_client([response("")])
    with pytest.raises(LLMResponseError):
        client.complete_json(system_prompt="s", user_prompt="u")


def test_unexpected_response_shape_is_reported():
    client, _ = make_client([SimpleNamespace(choices=[])])
    with pytest.raises(LLMResponseError):
        client.complete_json(system_prompt="s", user_prompt="u")


def test_missing_key_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(LLMConfigError):
        GroqClient()


def test_rate_limit_without_retries_raises_rate_limit_error():
    client, _ = make_client([RateLimitError()], max_retries=0)
    with pytest.raises(LLMRateLimitError):
        client.complete_json(system_prompt="s", user_prompt="u")
