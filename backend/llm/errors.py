"""Provider-independent application-level LLM exceptions."""
from __future__ import annotations


class LLMError(Exception):
    """Base class for all LLM failures that the application can handle."""


class LLMConfigError(LLMError):
    """The provider is not configured (for example, a missing API key)."""


class LLMAuthError(LLMError):
    """Authentication or permission failed. Never retry this."""


class LLMRateLimitError(LLMError):
    """The provider rate limit was reached."""


class LLMTimeoutError(LLMError):
    """The provider request timed out."""


class LLMConnectionError(LLMError):
    """The provider could not be reached."""


class LLMServiceError(LLMError):
    """The provider returned a transient server-side failure."""


class LLMResponseError(LLMError):
    """The provider returned malformed or schema-incompatible output."""
