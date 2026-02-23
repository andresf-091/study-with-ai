"""Bounded retry/backoff utilities for LLM provider calls."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

import httpx

from praktikum_app.infrastructure.llm.errors import (
    LLMRetryExhaustedError,
    ProviderRateLimitError,
    ProviderServerError,
)

TResult = TypeVar("TResult")


@dataclass(frozen=True)
class RetryPolicy:
    """Retry limits and exponential backoff configuration."""

    max_attempts: int = 3
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 2.0
    backoff_multiplier: float = 2.0


def is_retryable_llm_error(error: Exception) -> bool:
    """Return whether exception should be retried."""
    return isinstance(
        error,
        (
            ProviderRateLimitError,
            ProviderServerError,
            httpx.TimeoutException,
            httpx.TransportError,
        ),
    )


class RetryExecutor:
    """Execute operation with bounded retry/backoff policy."""

    def __init__(
        self,
        policy: RetryPolicy,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if policy.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if policy.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds must be >= 0")
        if policy.max_delay_seconds < 0:
            raise ValueError("max_delay_seconds must be >= 0")
        if policy.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be >= 1")

        self._policy = policy
        self._sleep = sleep

    def run(
        self,
        operation: Callable[[], TResult],
        *,
        is_retryable: Callable[[Exception], bool] = is_retryable_llm_error,
    ) -> TResult:
        """Run operation with bounded retry/backoff strategy."""
        attempt = 1
        while True:
            try:
                return operation()
            except Exception as exc:
                if not is_retryable(exc):
                    raise

                if attempt >= self._policy.max_attempts:
                    raise LLMRetryExhaustedError(
                        f"Retry budget exhausted after {attempt} attempts.",
                        attempts=attempt,
                    ) from exc

                delay_seconds = min(
                    self._policy.max_delay_seconds,
                    self._policy.base_delay_seconds
                    * (self._policy.backoff_multiplier ** (attempt - 1)),
                )
                self._sleep(delay_seconds)
                attempt += 1
