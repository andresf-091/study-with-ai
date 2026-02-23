"""Application ports for persisting LLM call audit records."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol

from praktikum_app.application.llm import LLMServiceProvider


@dataclass(frozen=True)
class LLMCallAuditRecord:
    """Audit record persisted for each LLM call attempt."""

    llm_call_id: str
    provider: LLMServiceProvider
    model: str
    prompt_hash: str
    status: str
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    course_id: str | None
    module_id: str | None
    created_at: datetime
    output_hash: str | None = None
    output_length: int | None = None
    output_text: str | None = None
    validation_errors: str | None = None


class LLMCallAuditRepository(Protocol):
    """Repository port for llm_calls persistence."""

    def save_call(self, record: LLMCallAuditRecord) -> None:
        """Persist a call audit record."""
        ...


class LLMCallAuditUnitOfWork(Protocol):
    """Unit-of-work port around llm_calls persistence."""

    llm_calls: LLMCallAuditRepository

    def __enter__(self) -> LLMCallAuditUnitOfWork:
        """Start transactional scope."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Finalize transactional scope."""
        ...

    def commit(self) -> None:
        """Commit transaction."""
        ...

    def rollback(self) -> None:
        """Rollback transaction."""
        ...


LLMCallAuditUnitOfWorkFactory = Callable[[], LLMCallAuditUnitOfWork]
