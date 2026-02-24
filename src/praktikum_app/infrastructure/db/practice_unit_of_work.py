"""SQLAlchemy unit-of-work implementation for practice generation flows."""

from __future__ import annotations

from datetime import datetime
from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from praktikum_app.application.practice_generation import (
    PracticeModuleContext,
    PracticeModuleSummary,
    PracticeRepository,
    PracticeTaskDraft,
    PracticeUnitOfWork,
)
from praktikum_app.domain.practice import PracticeDifficulty, PracticeTask
from praktikum_app.infrastructure.db.practice_repository import SqlAlchemyPracticeRepository


class _UninitializedPracticeRepository(PracticeRepository):
    """Placeholder repository before entering active transaction."""

    def get_module_context(self, module_id: str) -> PracticeModuleContext | None:
        raise RuntimeError("Unit of work is not active.")

    def list_modules_for_course(self, course_id: str) -> list[PracticeModuleSummary]:
        raise RuntimeError("Unit of work is not active.")

    def save_generated_batch(
        self,
        *,
        module_context: PracticeModuleContext,
        difficulty: PracticeDifficulty,
        llm_call_id: str,
        generation_id: str,
        created_at: datetime,
        candidates: list[PracticeTaskDraft],
    ) -> list[PracticeTask]:
        raise RuntimeError("Unit of work is not active.")

    def get_current_task(self, module_id: str) -> PracticeTask | None:
        raise RuntimeError("Unit of work is not active.")

    def list_task_history(self, module_id: str) -> list[PracticeTask]:
        raise RuntimeError("Unit of work is not active.")


class SqlAlchemyPracticeUnitOfWork(PracticeUnitOfWork):
    """Manage transactional scope for practice generation and history."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self.practice: PracticeRepository = _UninitializedPracticeRepository()

    def __enter__(self) -> SqlAlchemyPracticeUnitOfWork:
        self._session = self._session_factory()
        self.practice = SqlAlchemyPracticeRepository(self._session)
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
        self.practice = _UninitializedPracticeRepository()
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
