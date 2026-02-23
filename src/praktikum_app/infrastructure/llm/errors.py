"""Exceptions for LLM infrastructure components."""

from __future__ import annotations


class LLMInfrastructureError(RuntimeError):
    """Base error for LLM infrastructure failures."""


class LLMConfigurationError(LLMInfrastructureError):
    """Raised when router/provider configuration is invalid."""


class MissingApiKeyError(LLMInfrastructureError):
    """Raised when required provider key is missing in key store."""


class LLMExecutionError(LLMInfrastructureError):
    """User-safe wrapper for temporary provider execution failures."""


class ProviderResponseError(LLMInfrastructureError):
    """Raised when provider response shape cannot be parsed safely."""


class ProviderRequestError(LLMInfrastructureError):
    """Raised when provider rejects request as non-retryable client error."""


class ProviderRateLimitError(LLMInfrastructureError):
    """Raised on HTTP 429 from provider."""


class ProviderServerError(LLMInfrastructureError):
    """Raised on retryable provider server-side errors (HTTP 5xx)."""


class LLMRetryExhaustedError(LLMInfrastructureError):
    """Raised when retry budget is exhausted for retryable errors."""

    def __init__(self, message: str, attempts: int) -> None:
        super().__init__(message)
        self.attempts = attempts


class LLMResponseValidationError(LLMInfrastructureError):
    """Raised when provider output fails strict schema validation."""

    def __init__(
        self,
        message: str,
        *,
        repair_prompt: str,
        llm_call_id: str,
    ) -> None:
        super().__init__(message)
        self.repair_prompt = repair_prompt
        self.llm_call_id = llm_call_id
