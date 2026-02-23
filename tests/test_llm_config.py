"""Tests for router default model resolution from environment variables."""

from __future__ import annotations

import pytest

from praktikum_app.application.llm import LLMTaskType
from praktikum_app.infrastructure.llm.config import (
    ANTHROPIC_MODEL_ENV_VAR,
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_OPENROUTER_MODEL,
    OPENROUTER_MODEL_ENV_VAR,
    default_routes,
)


def test_default_routes_use_builtin_models_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ANTHROPIC_MODEL_ENV_VAR, raising=False)
    monkeypatch.delenv(OPENROUTER_MODEL_ENV_VAR, raising=False)

    routes = default_routes()

    assert routes[LLMTaskType.COURSE_PARSE].model == DEFAULT_ANTHROPIC_MODEL
    assert routes[LLMTaskType.PRACTICE_GRADE].model == DEFAULT_ANTHROPIC_MODEL
    assert routes[LLMTaskType.PRACTICE_GEN].model == DEFAULT_OPENROUTER_MODEL
    assert routes[LLMTaskType.CURATOR_MSG].model == DEFAULT_OPENROUTER_MODEL


def test_default_routes_use_env_model_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ANTHROPIC_MODEL_ENV_VAR, "claude-opus-4-6")
    monkeypatch.setenv(OPENROUTER_MODEL_ENV_VAR, "anthropic/claude-3.5-sonnet")

    routes = default_routes()

    assert routes[LLMTaskType.COURSE_PARSE].model == "claude-opus-4-6"
    assert routes[LLMTaskType.PRACTICE_GRADE].model == "claude-opus-4-6"
    assert routes[LLMTaskType.PRACTICE_GEN].model == "anthropic/claude-3.5-sonnet"
    assert routes[LLMTaskType.CURATOR_MSG].model == "anthropic/claude-3.5-sonnet"


def test_default_routes_ignore_blank_env_model_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ANTHROPIC_MODEL_ENV_VAR, "   ")
    monkeypatch.setenv(OPENROUTER_MODEL_ENV_VAR, "")

    routes = default_routes()

    assert routes[LLMTaskType.COURSE_PARSE].model == DEFAULT_ANTHROPIC_MODEL
    assert routes[LLMTaskType.PRACTICE_GEN].model == DEFAULT_OPENROUTER_MODEL
