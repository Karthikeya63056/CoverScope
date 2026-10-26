"""Groq provider implementation.

Provider-specific code is isolated here. The answer pipeline depends only on a
small ``complete_json`` protocol, so a fake client (or another provider) can be
substituted without changing validation logic.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

try:  # Imported lazily enough that tests can inject a fake SDK client.
    import groq
except ImportError:  # pragma: no cover - requirements install the SDK
    groq = None

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
from backend.qa.schemas import ANSWER_JSON_SCHEMA

DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_TIMEOUT_SECONDS = 30.0

DEFAULT_MAX_COMPLETION_TOKENS = 1_200
DEFAULT_MAX_RETRIES = 2
DEFAULT_REASONING_EFFORT = "low"


class GroqClient:
    """Small synchronous client for strict structured answers."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
        sdk_client: Any | None = None,
        sleep: Any = time.sleep,
    ) -> None:
        if not model or not model.strip():
            raise LLMConfigError("Groq model must not be empty")
        if timeout <= 0:
            raise LLMConfigError("Groq timeout must be greater than zero")
        if max_completion_tokens <= 0:
            raise LLMConfigError(
                "Groq max_completion_tokens must be greater than zero"
            )
        if max_retries < 0:
            raise LLMConfigError("Groq max_retries must not be negative")
        if reasoning_effort not in {"low", "medium", "high"}:
            raise LLMConfigError(
                "Groq reasoning_effort must be low, medium, or high"
            )

        # Never store the key on the instance and never log it.
        if sdk_client is None:
            key = api_key or os.getenv("GROQ_API_KEY")
            if not key or not key.strip():
                raise LLMConfigError(
                    "GROQ_API_KEY is not set. Add it to .env or the environment."
                )
            if groq is None:  # pragma: no cover
                raise LLMConfigError(
                    "The groq package is not installed. Run pip install -r requirements.txt."
                )
            sdk_client = groq.Groq(
                api_key=key,
                timeout=timeout,
                max_retries=0,  # retries are handled below
            )

        self._client = sdk_client
        self.model = model.strip()
        self.timeout = timeout
        self.max_completion_tokens = max_completion_tokens
        self.max_retries = max_retries
        self.reasoning_effort = reasoning_effort
        self._sleep = sleep

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict | None = None,
    ) -> dict:
        """Call Groq and return a parsed JSON object.

        The schema defaults to the CoverScope answer schema. This method never
        logs prompts, responses, or the API key.
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "policy_answer",
                    "strict": True,
                    "schema": schema if schema is not None else ANSWER_JSON_SCHEMA,
                },
            },
            "max_completion_tokens": self.max_completion_tokens,
            "reasoning_effort": self.reasoning_effort,
            "timeout": self.timeout,
        }

        response = self._request_with_retries(payload)
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise LLMResponseError(
                "Groq returned an unexpected response shape."
            ) from exc

        if not content or not content.strip():
            raise LLMResponseError("Groq returned an empty response.")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMResponseError(
                "Groq returned a response that was not valid JSON."
            ) from exc
        if not isinstance(parsed, dict):
            raise LLMResponseError("Groq returned JSON that is not an object.")
        return parsed

    def _request_with_retries(self, payload: dict) -> Any:
        last_error: LLMError | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return self._client.chat.completions.create(**payload)
            except Exception as exc:  # SDK-specific exceptions are mapped below
                mapped = self._map_exception(exc)
                last_error = mapped
                retryable = isinstance(
                    mapped,
                    (
                        LLMRateLimitError,
                        LLMTimeoutError,
                        LLMConnectionError,
                        LLMServiceError,
                    ),
                )
                if not retryable or attempt >= self.max_retries:
                    raise mapped from exc
                self._sleep(self._retry_delay(exc, attempt))
        raise last_error or LLMError("Groq request failed")

    @staticmethod
    def _retry_delay(exc: Exception, attempt: int) -> float:
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None) or {}
        retry_after = headers.get("retry-after") or headers.get("Retry-After")
        if retry_after is not None:
            try:
                return min(max(float(retry_after), 0.0), 10.0)
            except (TypeError, ValueError):
                pass
        return min(2.0**attempt, 8.0)

    @staticmethod
    def _map_exception(exc: Exception) -> LLMError:
        """Map SDK exceptions by name so injected fakes are testable.

        Groq's SDK exception names are stable and public. Name matching also
        avoids importing every SDK exception class solely for isinstance checks.
        """
        name = type(exc).__name__
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)

        if name in {"AuthenticationError", "PermissionDeniedError"}:
            return LLMAuthError(
                "Groq authentication failed. Check GROQ_API_KEY in .env or the environment."
            )
        if name == "RateLimitError":
            return LLMRateLimitError(
                "Groq rate limit reached. Wait before retrying or reduce retrieved context."
            )
        if name in {"APITimeoutError", "TimeoutError", "ReadTimeout", "ConnectTimeout"}:
            return LLMTimeoutError("Groq request timed out.")
        if name in {"APIConnectionError", "ConnectError", "ConnectionError"}:
            return LLMConnectionError("Could not connect to Groq.")
        if name in {"BadRequestError", "UnprocessableEntityError", "NotFoundError"}:
            return LLMResponseError(
                "Groq rejected the request or the requested model is unavailable."
            )
        if name in {"APIStatusError", "InternalServerError"}:
            if status_code is None or status_code >= 500:
                return LLMServiceError(
                    "Groq returned a temporary server error. Try again shortly."
                )
            return LLMResponseError(
                f"Groq rejected the request (HTTP {status_code})."
            )
        return LLMError(f"Groq request failed ({name}).")
