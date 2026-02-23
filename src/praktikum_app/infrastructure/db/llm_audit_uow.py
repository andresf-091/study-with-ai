"""SQLAlchemy unit-of-work implementation for llm_calls audit table."""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from praktikum_app.application.llm_audit import (
    LLMCallAuditRecord,
    LLMCallAuditRepository,
    LLMCallAuditUnitOfWork,
)
from praktikum_app.infrastructure.db.llm_audit_repository import SqlAlchemyLlmCallAuditRepository


class _UninitializedAuditRepository(LLMCallAuditRepository):
    """Placeholder repository used before unit-of-work context is active."""

    def save_call(self, record: LLMCallAuditRecord) -> None:
        raise RuntimeError("Unit of work is not active.")


class SqlAlchemyLlmCallAuditUnitOfWork(LLMCallAuditUnitOfWork):
    """Manage transactional scope for llm_calls persistence."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self.llm_calls: LLMCallAuditRepository = _UninitializedAuditRepository()

    def __enter__(self) -> SqlAlchemyLlmCallAuditUnitOfWork:
        self._session = self._session_factory()
        self.llm_calls = SqlAlchemyLlmCallAuditRepository(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc is not None:
            self.rollback()

        session = self._session
        self._session = None
        self.llm_calls = _UninitializedAuditRepository()
        if session is not None:
            session.close()

    def commit(self) -> None:
        session = self._require_session()
        session.commit()

    def rollback(self) -> None:
        session = self._session
        if session is not None:
            session.rollback()

    def _require_session(self) -> Session:
        if self._session is None:
            raise RuntimeError("Unit of work is not active.")
        return self._session
