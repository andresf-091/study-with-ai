"""SQLAlchemy unit-of-work implementation for import persistence."""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from praktikum_app.application.import_persistence import (
    ImportedCourseRepository,
    ImportUnitOfWork,
    PersistedImportRecord,
)
from praktikum_app.domain.import_text import RawCourseText
from praktikum_app.infrastructure.db.import_repository import SqlAlchemyImportedCourseRepository


class _UninitializedRepository(ImportedCourseRepository):
    """Placeholder repository before entering unit-of-work context."""

    def save_imported_text(self, imported_text: RawCourseText) -> PersistedImportRecord:
        raise RuntimeError("Unit of work is not active.")

    def get_latest_imported_text(self) -> PersistedImportRecord | None:
        raise RuntimeError("Unit of work is not active.")


class SqlAlchemyImportUnitOfWork(ImportUnitOfWork):
    """Manage transactional scope for import persistence."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self.imports: ImportedCourseRepository = _UninitializedRepository()

    def __enter__(self) -> SqlAlchemyImportUnitOfWork:
        self._session = self._session_factory()
        self.imports = SqlAlchemyImportedCourseRepository(self._session)
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
        self.imports = _UninitializedRepository()
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
