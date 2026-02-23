"""SQLAlchemy unit-of-work implementation for course plan operations."""

from __future__ import annotations

from datetime import datetime
from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from praktikum_app.application.course_decomposition import (
    CoursePlanRepository,
    CoursePlanUnitOfWork,
    CourseRawTextRecord,
    SaveCoursePlanStats,
)
from praktikum_app.domain.course_plan import CoursePlanV1
from praktikum_app.infrastructure.db.course_plan_repository import SqlAlchemyCoursePlanRepository


class _UninitializedCoursePlanRepository(CoursePlanRepository):
    """Placeholder repository before entering active transaction."""

    def get_raw_text(
        self,
        course_id: str,
        raw_text_id: str | None = None,
    ) -> CourseRawTextRecord | None:
        raise RuntimeError("Unit of work is not active.")

    def load_course_plan(self, course_id: str) -> CoursePlanV1 | None:
        raise RuntimeError("Unit of work is not active.")

    def replace_course_plan(
        self,
        course_id: str,
        plan: CoursePlanV1,
        saved_at: datetime,
    ) -> SaveCoursePlanStats:
        raise RuntimeError("Unit of work is not active.")


class SqlAlchemyCoursePlanUnitOfWork(CoursePlanUnitOfWork):
    """Manage transactional scope for course plan parsing/saving."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self.plans: CoursePlanRepository = _UninitializedCoursePlanRepository()

    def __enter__(self) -> SqlAlchemyCoursePlanUnitOfWork:
        self._session = self._session_factory()
        self.plans = SqlAlchemyCoursePlanRepository(self._session)
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
        self.plans = _UninitializedCoursePlanRepository()
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
