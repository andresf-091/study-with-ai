"""Unit tests for bounded retry/backoff behavior."""

from __future__ import annotations

import httpx
import pytest

from praktikum_app.infrastructure.llm.errors import LLMRetryExhaustedError, ProviderRateLimitError
from praktikum_app.infrastructure.llm.retry import RetryExecutor, RetryPolicy


def test_retry_executor_retries_timeout_then_succeeds() -> None:
    attempts = {"count": 0}
    sleep_calls: list[float] = []

    def operation() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise httpx.ReadTimeout("timed out")
        return "ok"

    executor = RetryExecutor(
        RetryPolicy(
            max_attempts=4,
            base_delay_seconds=0.1,
            max_delay_seconds=1.0,
            backoff_multiplier=2.0,
        ),
        sleep=sleep_calls.append,
    )

    result = executor.run(operation)

    assert result == "ok"
    assert attempts["count"] == 3
    assert sleep_calls == [0.1, 0.2]


def test_retry_executor_raises_when_retry_budget_exhausted() -> None:
    sleep_calls: list[float] = []
    executor = RetryExecutor(
        RetryPolicy(
            max_attempts=3,
            base_delay_seconds=0.0,
            max_delay_seconds=0.0,
            backoff_multiplier=2.0,
        ),
        sleep=sleep_calls.append,
    )

    with pytest.raises(LLMRetryExhaustedError) as exc_info:
        executor.run(lambda: (_ for _ in ()).throw(ProviderRateLimitError("429")))

    assert exc_info.value.attempts == 3
    assert sleep_calls == [0.0, 0.0]


def test_retry_executor_does_not_retry_non_retryable_error() -> None:
    sleep_calls: list[float] = []
    executor = RetryExecutor(RetryPolicy(max_attempts=3), sleep=sleep_calls.append)

    with pytest.raises(ValueError, match="bad input"):
        executor.run(lambda: (_ for _ in ()).throw(ValueError("bad input")))

    assert sleep_calls == []
