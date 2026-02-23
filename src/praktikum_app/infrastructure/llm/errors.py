"""Exceptions for LLM infrastructure components."""

from __future__ import annotations

from praktikum_app.application.llm import (
    LLMRequestRejectedError,
    LLMResponseSchemaError,
    LLMTemporaryError,
    MissingApiKeyLLMError,
)


class LLMInfrastructureError(RuntimeError):
    """Base error for LLM infrastructure failures."""


class LLMConfigurationError(LLMInfrastructureError):
    """Raised when router/provider configuration is invalid."""


class MissingApiKeyError(MissingApiKeyLLMError, LLMInfrastructureError):
    """Raised when required provider key is missing in key store."""


class LLMExecutionError(LLMTemporaryError, LLMInfrastructureError):
    """User-safe wrapper for temporary provider execution failures."""


class ProviderResponseError(LLMInfrastructureError):
    """Raised when provider response shape cannot be parsed safely."""


class ProviderRequestError(LLMRequestRejectedError, LLMInfrastructureError):
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


class LLMResponseValidationError(LLMResponseSchemaError, LLMInfrastructureError):
    """Raised when provider output fails strict schema validation."""

    def __init__(
        self,
        message: str,
        *,
        repair_prompt: str,
        llm_call_id: str,
        invalid_output: str,
        validation_errors: str,
    ) -> None:
        super().__init__(
            message,
            llm_call_id=llm_call_id,
            repair_prompt=repair_prompt,
            invalid_output=invalid_output,
            validation_errors=validation_errors,
        )
