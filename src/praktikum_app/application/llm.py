"""Application-level contracts for LLM providers and routing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel


class LLMTaskType(StrEnum):
    """Supported internal task types for model routing policy."""

    COURSE_PARSE = "course_parse"
    PRACTICE_GEN = "practice_gen"
    PRACTICE_GRADE = "practice_grade"
    CURATOR_MSG = "curator_msg"


class LLMServiceProvider(StrEnum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"


TModel = TypeVar("TModel", bound=BaseModel)


@dataclass(frozen=True)
class LLMRequest(Generic[TModel]):
    """Application-level request contract for routed LLM invocation."""

    task_type: LLMTaskType
    system_prompt: str
    user_prompt: str
    response_schema: type[TModel]
    correlation_id: str
    course_id: str | None = None
    module_id: str | None = None
    max_output_tokens: int = 2048
    temperature: float = 0.2


@dataclass(frozen=True)
class ProviderCallRequest:
    """Provider-agnostic DTO for concrete provider clients."""

    model: str
    api_key: str
    system_prompt: str
    user_prompt: str
    max_output_tokens: int
    temperature: float
    timeout_seconds: float


@dataclass(frozen=True)
class ProviderCallResponse:
    """Provider-agnostic DTO for normalized provider responses."""

    output_text: str
    input_tokens: int | None
    output_tokens: int | None


@dataclass(frozen=True)
class LLMResponse(Generic[TModel]):
    """Application-level response contract for routed LLM invocation."""

    llm_call_id: str
    provider: LLMServiceProvider
    model: str
    prompt_hash: str
    latency_ms: int
    parsed: TModel
    output_text: str
    input_tokens: int | None
    output_tokens: int | None


class LLMProvider(Protocol):
    """Provider protocol implemented by infrastructure HTTP clients."""

    @property
    def provider(self) -> LLMServiceProvider:
        """Return provider identity."""
        ...

    def generate(self, request: ProviderCallRequest) -> ProviderCallResponse:
        """Call provider and return provider-agnostic response DTO."""
        ...


class LLMKeyStore(Protocol):
    """Storage port for provider API keys."""

    def set_key(self, provider: LLMServiceProvider, api_key: str) -> None:
        """Persist API key for provider."""
        ...

    def get_key(self, provider: LLMServiceProvider) -> str | None:
        """Load API key for provider if present."""
        ...

    def delete_key(self, provider: LLMServiceProvider) -> None:
        """Delete provider key from storage."""
        ...
