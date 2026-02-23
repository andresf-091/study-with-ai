"""Configuration and policy checks for LLM routing."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from praktikum_app.application.llm import LLMServiceProvider, LLMTaskType
from praktikum_app.infrastructure.llm.errors import LLMConfigurationError
from praktikum_app.infrastructure.llm.retry import RetryPolicy


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
    return {
        LLMTaskType.COURSE_PARSE: TaskRoute(
            provider=LLMServiceProvider.ANTHROPIC,
            model="claude-3-5-sonnet-latest",
        ),
        LLMTaskType.PRACTICE_GRADE: TaskRoute(
            provider=LLMServiceProvider.ANTHROPIC,
            model="claude-3-5-sonnet-latest",
        ),
        LLMTaskType.PRACTICE_GEN: TaskRoute(
            provider=LLMServiceProvider.OPENROUTER,
            model="openai/gpt-4o-mini",
        ),
        LLMTaskType.CURATOR_MSG: TaskRoute(
            provider=LLMServiceProvider.OPENROUTER,
            model="openai/gpt-4o-mini",
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
            raise LLMConfigurationError(f"Missing route for task type: {task_type.value}")
        if route.provider is not expected_provider:
            raise LLMConfigurationError(
                
                    f"Policy violation for task {task_type.value}: "
                    f"expected {expected_provider.value}, got {route.provider.value}."
                
            )
