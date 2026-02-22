"""SQLAlchemy repository implementation for imported course text."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from praktikum_app.application.import_persistence import (
    ImportedCourseRepository,
    ImportedCourseSummary,
    PersistedImportRecord,
)
from praktikum_app.domain.import_text import CourseSource, CourseSourceType, RawCourseText
from praktikum_app.infrastructure.db.models import (
    CourseModel,
    CourseSourceModel,
    DeadlineModel,
    LlmCallModel,
    ModuleModel,
    RawTextModel,
)


class SqlAlchemyImportedCourseRepository(ImportedCourseRepository):
    """Persist and read imported course raw text via SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save_imported_text(self, imported_text: RawCourseText) -> PersistedImportRecord:
        course_id = _new_id()
        source_id = _new_id()
        raw_text_id = _new_id()

        course = CourseModel(
            id=course_id,
            title=_derive_course_title(imported_text),
            created_at=imported_text.source.imported_at,
        )
        source = CourseSourceModel(
            id=source_id,
            course_id=course_id,
            source_type=imported_text.source.source_type.value,
            filename=imported_text.source.filename,
            imported_at=imported_text.source.imported_at,
            page_count=imported_text.source.page_count,
            extraction_strategy=imported_text.source.extraction_strategy,
            likely_scanned=imported_text.source.likely_scanned,
        )
        raw_text = RawTextModel(
            id=raw_text_id,
            course_id=course_id,
            source_id=source_id,
            content=imported_text.content,
            content_hash=imported_text.content_hash,
            length=imported_text.length,
            created_at=imported_text.source.imported_at,
        )

        self._session.add(course)
        self._session.add(source)
        self._session.add(raw_text)

        return PersistedImportRecord(
            course_id=course_id,
            source_id=source_id,
            raw_text_id=raw_text_id,
            raw_text=imported_text,
        )

    def get_latest_imported_text(self) -> PersistedImportRecord | None:
        statement = (
            select(RawTextModel)
            .options(joinedload(RawTextModel.source))
            .order_by(RawTextModel.created_at.desc())
            .limit(1)
        )
        raw_text_model = self._session.execute(statement).scalars().first()
        if raw_text_model is None:
            return None

        source_model = raw_text_model.source
        source = CourseSource(
            source_type=CourseSourceType(source_model.source_type),
            filename=source_model.filename,
            imported_at=source_model.imported_at,
            page_count=source_model.page_count,
            extraction_strategy=source_model.extraction_strategy,
            likely_scanned=source_model.likely_scanned,
        )
        raw_text = RawCourseText(
            content=raw_text_model.content,
            content_hash=raw_text_model.content_hash,
            length=raw_text_model.length,
            source=source,
        )
        return PersistedImportRecord(
            course_id=raw_text_model.course_id,
            source_id=raw_text_model.source_id,
            raw_text_id=raw_text_model.id,
            raw_text=raw_text,
        )

    def list_imported_courses(self) -> list[ImportedCourseSummary]:
        statement = (
            select(RawTextModel, CourseSourceModel)
            .join(CourseSourceModel, RawTextModel.source_id == CourseSourceModel.id)
            .order_by(RawTextModel.created_at.desc())
        )
        rows = self._session.execute(statement).all()

        summaries: list[ImportedCourseSummary] = []
        seen_course_ids: set[str] = set()
        for raw_text_model, source_model in rows:
            course_id = raw_text_model.course_id
            if course_id in seen_course_ids:
                continue

            seen_course_ids.add(course_id)
            summaries.append(
                ImportedCourseSummary(
                    course_id=course_id,
                    source_type=CourseSourceType(source_model.source_type),
                    filename=source_model.filename,
                    imported_at=source_model.imported_at,
                    length=raw_text_model.length,
                    content_hash=raw_text_model.content_hash,
                )
            )

        return summaries

    def delete_course(self, course_id: str) -> bool:
        if self._session.get(CourseModel, course_id) is None:
            return False

        module_ids = list(
            self._session.execute(
                select(ModuleModel.id).where(ModuleModel.course_id == course_id)
            ).scalars()
        )

        if module_ids:
            self._session.execute(
                delete(LlmCallModel).where(LlmCallModel.module_id.in_(module_ids))
            )

        self._session.execute(delete(LlmCallModel).where(LlmCallModel.course_id == course_id))
        self._session.execute(delete(DeadlineModel).where(DeadlineModel.course_id == course_id))
        self._session.execute(delete(ModuleModel).where(ModuleModel.course_id == course_id))
        self._session.execute(delete(RawTextModel).where(RawTextModel.course_id == course_id))
        self._session.execute(
            delete(CourseSourceModel).where(CourseSourceModel.course_id == course_id)
        )
        self._session.execute(delete(CourseModel).where(CourseModel.id == course_id))

        return True


def _derive_course_title(imported_text: RawCourseText) -> str | None:
    filename = imported_text.source.filename
    if not filename:
        return None
    return Path(filename).stem


def _new_id() -> str:
    return str(uuid4())
