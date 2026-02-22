"""Tests for MainWindow startup behavior with persisted imports."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QListWidget

from praktikum_app.application.import_persistence import PersistImportedCourseUseCase
from praktikum_app.domain.import_text import CourseSource, CourseSourceType, RawCourseText
from praktikum_app.infrastructure.db.base import Base
from praktikum_app.infrastructure.db.config import DB_PATH_ENV_VAR
from praktikum_app.infrastructure.db.session import create_session_factory, create_sqlite_engine
from praktikum_app.infrastructure.db.unit_of_work import SqlAlchemyImportUnitOfWork
from praktikum_app.presentation.qt.main_window import MainWindow


def test_main_window_restores_latest_import_from_database_on_startup(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Main window should load latest persisted import after app restart."""
    db_path = Path("tests") / f"_runtime_startup_restore_{uuid4().hex}.db"
    monkeypatch.setenv(DB_PATH_ENV_VAR, str(db_path.resolve()))

    engine = create_sqlite_engine(db_path)
    session_factory = create_session_factory(engine)
    Base.metadata.create_all(engine)
    window: MainWindow | None = None

    try:
        monkeypatch.setattr(
            "praktikum_app.presentation.qt.main_window.create_default_session_factory",
            lambda: session_factory,
        )
        persist_use_case = PersistImportedCourseUseCase(
            lambda: SqlAlchemyImportUnitOfWork(session_factory),
        )
        imported_text = _make_imported_text(
            source_type=CourseSourceType.PASTE,
            content="Recovered after restart",
            filename=None,
        )
        persist_use_case.execute(imported_text)

        window = MainWindow()
        today_hint = window.findChild(QLabel, "todayHintLabel")
        courses_list = window.findChild(QListWidget, "coursesList")

        assert today_hint is not None
        assert courses_list is not None
        assert courses_list.count() == 1
        assert "Тип источника: Вставка" in today_hint.text()
        assert "Длина текста: 23" in today_hint.text()
    finally:
        if window is not None:
            window.close()
            application.processEvents()
        engine.dispose()
        db_path.unlink(missing_ok=True)


def _make_imported_text(
    source_type: CourseSourceType,
    content: str,
    filename: str | None,
) -> RawCourseText:
    source = CourseSource(
        source_type=source_type,
        filename=filename,
        imported_at=datetime(2026, 2, 22, 12, 0, tzinfo=UTC),
    )
    return RawCourseText(
        content=content,
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        length=len(content),
        source=source,
    )
