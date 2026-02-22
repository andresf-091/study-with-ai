"""Repository/UoW tests for SQLite import persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from praktikum_app.application.import_persistence import (
    GetLatestImportedCourseUseCase,
    PersistImportedCourseUseCase,
)
from praktikum_app.domain.import_text import CourseSource, CourseSourceType, RawCourseText
from praktikum_app.infrastructure.db.base import Base
from praktikum_app.infrastructure.db.session import create_session_factory, create_sqlite_engine
from praktikum_app.infrastructure.db.unit_of_work import SqlAlchemyImportUnitOfWork


def test_import_persistence_roundtrip_on_sqlite() -> None:
    db_path = Path("tests") / f"_runtime_import_roundtrip_{uuid4().hex}.db"
    session_factory, engine = _create_test_session_factory(db_path)
    try:
        persist_use_case = PersistImportedCourseUseCase(
            lambda: SqlAlchemyImportUnitOfWork(session_factory),
        )
        get_latest_use_case = GetLatestImportedCourseUseCase(
            lambda: SqlAlchemyImportUnitOfWork(session_factory),
        )

        imported = _make_raw_text(
            source_type=CourseSourceType.PASTE,
            content="Normalized import payload",
            content_hash="abc123",
            filename=None,
        )
        persisted = persist_use_case.execute(imported)
        latest = get_latest_use_case.execute()

        assert latest is not None
        assert latest.course_id == persisted.course_id
        assert latest.source_id == persisted.source_id
        assert latest.raw_text_id == persisted.raw_text_id
        assert latest.raw_text.content == "Normalized import payload"
        assert latest.raw_text.source.source_type is CourseSourceType.PASTE
    finally:
        engine.dispose()
        db_path.unlink(missing_ok=True)


def test_import_persistence_keeps_pdf_source_metadata() -> None:
    db_path = Path("tests") / f"_runtime_import_pdf_metadata_{uuid4().hex}.db"
    session_factory, engine = _create_test_session_factory(db_path)
    try:
        persist_use_case = PersistImportedCourseUseCase(
            lambda: SqlAlchemyImportUnitOfWork(session_factory),
        )
        get_latest_use_case = GetLatestImportedCourseUseCase(
            lambda: SqlAlchemyImportUnitOfWork(session_factory),
        )

        imported = _make_raw_text(
            source_type=CourseSourceType.PDF,
            content="PDF text",
            content_hash="hash-pdf",
            filename="course.pdf",
            page_count=7,
            extraction_strategy="pdfminer",
            likely_scanned=True,
        )
        persist_use_case.execute(imported)
        latest = get_latest_use_case.execute()

        assert latest is not None
        assert latest.raw_text.source.source_type is CourseSourceType.PDF
        assert latest.raw_text.source.page_count == 7
        assert latest.raw_text.source.extraction_strategy == "pdfminer"
        assert latest.raw_text.source.likely_scanned is True
    finally:
        engine.dispose()
        db_path.unlink(missing_ok=True)


def test_get_latest_import_returns_none_for_empty_database() -> None:
    db_path = Path("tests") / f"_runtime_import_empty_{uuid4().hex}.db"
    session_factory, engine = _create_test_session_factory(db_path)
    try:
        get_latest_use_case = GetLatestImportedCourseUseCase(
            lambda: SqlAlchemyImportUnitOfWork(session_factory),
        )
        assert get_latest_use_case.execute() is None
    finally:
        engine.dispose()
        db_path.unlink(missing_ok=True)


def _create_test_session_factory(database_path: Path) -> tuple[sessionmaker[Session], Engine]:
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    return create_session_factory(engine), engine


def _make_raw_text(
    source_type: CourseSourceType,
    content: str,
    content_hash: str,
    filename: str | None,
    page_count: int | None = None,
    extraction_strategy: str | None = None,
    likely_scanned: bool = False,
) -> RawCourseText:
    imported_at = datetime(2026, 2, 22, 12, 0, tzinfo=UTC)
    source = CourseSource(
        source_type=source_type,
        filename=filename,
        imported_at=imported_at,
        page_count=page_count,
        extraction_strategy=extraction_strategy,
        likely_scanned=likely_scanned,
    )
    return RawCourseText(
        content=content,
        content_hash=content_hash,
        length=len(content),
        source=source,
    )
