"""Configuration and policy checks for LLM routing."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from praktikum_app.application.llm import LLMServiceProvider, LLMTaskType
from praktikum_app.infrastructure.llm.errors import LLMConfigurationError
from praktikum_app.infrastructure.llm.retry import RetryPolicy

ANTHROPIC_MODEL_ENV_VAR = "PRAKTIKUM_ANTHROPIC_MODEL"
OPENROUTER_MODEL_ENV_VAR = "PRAKTIKUM_OPENROUTER_MODEL"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-6"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-4o-mini"


@dataclass(frozen=True)
class TaskRoute:
    """Provider/model target for one task type."""

    provider: LLMServiceProvider
    model: str


@dataclass(frozen=True)
class LLMRouterConfig:
    """Router configuration including route map and retry settings."""

    routes: Mapping[LLMTaskType, TaskRoute]
    timeout_seconds: float = 30.0
    retry_policy: RetryPolicy = RetryPolicy()


EXPECTED_PROVIDER_BY_TASK: dict[LLMTaskType, LLMServiceProvider] = {
    LLMTaskType.COURSE_PARSE: LLMServiceProvider.ANTHROPIC,
    LLMTaskType.PRACTICE_GRADE: LLMServiceProvider.ANTHROPIC,
    LLMTaskType.PRACTICE_GEN: LLMServiceProvider.OPENROUTER,
    LLMTaskType.CURATOR_MSG: LLMServiceProvider.OPENROUTER,
}


def default_routes() -> dict[LLMTaskType, TaskRoute]:
    """Return default task routing aligned with approved provider policy."""
    anthropic_model = _resolve_model(
        env_var=ANTHROPIC_MODEL_ENV_VAR,
        fallback=DEFAULT_ANTHROPIC_MODEL,
    )
    openrouter_model = _resolve_model(
        env_var=OPENROUTER_MODEL_ENV_VAR,
        fallback=DEFAULT_OPENROUTER_MODEL,
    )
    return {
        LLMTaskType.COURSE_PARSE: TaskRoute(
            provider=LLMServiceProvider.ANTHROPIC,
            model=anthropic_model,
        ),
        LLMTaskType.PRACTICE_GRADE: TaskRoute(
            provider=LLMServiceProvider.ANTHROPIC,
            model=anthropic_model,
        ),
        LLMTaskType.PRACTICE_GEN: TaskRoute(
            provider=LLMServiceProvider.OPENROUTER,
            model=openrouter_model,
        ),
        LLMTaskType.CURATOR_MSG: TaskRoute(
            provider=LLMServiceProvider.OPENROUTER,
            model=openrouter_model,
        ),
    }


def default_router_config() -> LLMRouterConfig:
    """Build default config with policy-compliant routes."""
    return LLMRouterConfig(routes=default_routes())


def validate_routing_policy(routes: Mapping[LLMTaskType, TaskRoute]) -> None:
    """Ensure task routes do not violate provider policy."""
    for task_type, expected_provider in EXPECTED_PROVIDER_BY_TASK.items():
        route = routes.get(task_type)
        if route is None:
            raise LLMConfigurationError(
                f"Missing route for task type: {task_type.value}"
            )
        if route.provider is not expected_provider:
            raise LLMConfigurationError(
                f"Policy violation for task {task_type.value}: "
                f"expected {expected_provider.value}, got {route.provider.value}."
            )


def _resolve_model(*, env_var: str, fallback: str) -> str:
    raw_value = os.environ.get(env_var, "")
    resolved = raw_value.strip()
    return resolved if resolved else fallback
