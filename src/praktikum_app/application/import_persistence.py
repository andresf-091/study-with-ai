"""Application ports and use-cases for import persistence."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import uuid4

from praktikum_app.domain.import_text import CourseSourceType, RawCourseText

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PersistedImportRecord:
    """Persisted import identifiers and materialized domain payload."""

    course_id: str
    source_id: str
    raw_text_id: str
    raw_text: RawCourseText


@dataclass(frozen=True)
class ImportedCourseSummary:
    """Compact persisted course info for course list UI."""

    course_id: str
    source_type: CourseSourceType
    filename: str | None
    imported_at: datetime
    length: int
    content_hash: str


class ImportedCourseRepository(Protocol):
    """Repository port for persisted imported text."""

    def save_imported_text(self, imported_text: RawCourseText) -> PersistedImportRecord:
        """Persist imported text and source metadata."""
        ...

    def get_latest_imported_text(self) -> PersistedImportRecord | None:
        """Return latest persisted imported text."""
        ...

    def list_imported_courses(self) -> list[ImportedCourseSummary]:
        """Return persisted imported courses ordered by newest first."""
        ...

    def delete_course(self, course_id: str) -> bool:
        """Delete course with related import data."""
        ...


class ImportUnitOfWork(Protocol):
    """Unit-of-work port around import persistence operations."""

    imports: ImportedCourseRepository

    def __enter__(self) -> ImportUnitOfWork:
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
        """Commit current transaction."""
        ...

    def rollback(self) -> None:
        """Rollback current transaction."""
        ...


ImportUnitOfWorkFactory = Callable[[], ImportUnitOfWork]


class PersistImportedCourseUseCase:
    """Persist import preview result to durable storage."""

    def __init__(self, uow_factory: ImportUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def execute(self, imported_text: RawCourseText) -> PersistedImportRecord:
        """Persist imported text and return persisted identifiers."""
        correlation_id = str(uuid4())
        try:
            with self._uow_factory() as uow:
                record = uow.imports.save_imported_text(imported_text)
                uow.commit()
        except Exception as exc:
            LOGGER.exception(
                (
                    "event=import_persist_failed correlation_id=%s course_id=- module_id=- "
                    "llm_call_id=- source_type=%s content_hash=%s length=%s error_type=%s"
                ),
                correlation_id,
                imported_text.source.source_type.value,
                imported_text.content_hash,
                imported_text.length,
                exc.__class__.__name__,
            )
            raise

        LOGGER.info(
            (
                "event=import_persisted correlation_id=%s course_id=%s module_id=- llm_call_id=- "
                "source_id=%s raw_text_id=%s source_type=%s content_hash=%s length=%s"
            ),
            correlation_id,
            record.course_id,
            record.source_id,
            record.raw_text_id,
            record.raw_text.source.source_type.value,
            record.raw_text.content_hash,
            record.raw_text.length,
        )
        return record


class GetLatestImportedCourseUseCase:
    """Read latest imported text from persistence."""

    def __init__(self, uow_factory: ImportUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def execute(self) -> PersistedImportRecord | None:
        """Return latest persisted import record if available."""
        correlation_id = str(uuid4())
        with self._uow_factory() as uow:
            record = uow.imports.get_latest_imported_text()

        if record is None:
            LOGGER.info(
                (
                    "event=import_latest_not_found correlation_id=%s course_id=- module_id=- "
                    "llm_call_id=-"
                ),
                correlation_id,
            )
            return None

        LOGGER.info(
            (
                "event=import_latest_loaded correlation_id=%s "
                "course_id=%s module_id=- llm_call_id=- "
                "source_id=%s raw_text_id=%s source_type=%s content_hash=%s length=%s"
            ),
            correlation_id,
            record.course_id,
            record.source_id,
            record.raw_text_id,
            record.raw_text.source.source_type.value,
            record.raw_text.content_hash,
            record.raw_text.length,
        )
        return record


class ListImportedCoursesUseCase:
    """Read all imported courses from persistence."""

    def __init__(self, uow_factory: ImportUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def execute(self) -> list[ImportedCourseSummary]:
        """Return imported course summaries sorted by latest import timestamp."""
        correlation_id = str(uuid4())
        with self._uow_factory() as uow:
            items = uow.imports.list_imported_courses()

        LOGGER.info(
            (
                "event=import_courses_listed correlation_id=%s course_id=- module_id=- "
                "llm_call_id=- items_count=%s"
            ),
            correlation_id,
            len(items),
        )
        return items


class DeleteImportedCourseUseCase:
    """Delete persisted course and related import data."""

    def __init__(self, uow_factory: ImportUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def execute(self, course_id: str) -> bool:
        """Delete course by id. Returns True when course existed and was deleted."""
        if not course_id:
            raise ValueError("course_id is required")

        correlation_id = str(uuid4())
        try:
            with self._uow_factory() as uow:
                deleted = uow.imports.delete_course(course_id)
                if deleted:
                    uow.commit()
                else:
                    uow.rollback()
        except Exception as exc:
            LOGGER.exception(
                (
                    "event=import_course_delete_failed correlation_id=%s course_id=%s "
                    "module_id=- llm_call_id=- error_type=%s"
                ),
                correlation_id,
                course_id,
                exc.__class__.__name__,
            )
            raise

        LOGGER.info(
            (
                "event=import_course_delete_completed correlation_id=%s course_id=%s "
                "module_id=- llm_call_id=- deleted=%s"
            ),
            correlation_id,
            course_id,
            deleted,
        )
        return deleted
