"""UI tests for courses list, deletion flow, and key states in MainWindow."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar
from uuid import uuid4

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QListWidget, QMessageBox, QPushButton
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from praktikum_app.application.import_persistence import (
    PersistImportedCourseUseCase,
)
from praktikum_app.domain.import_text import CourseSource, CourseSourceType, RawCourseText
from praktikum_app.infrastructure.db.base import Base
from praktikum_app.infrastructure.db.config import DB_PATH_ENV_VAR
from praktikum_app.infrastructure.db.session import create_session_factory, create_sqlite_engine
from praktikum_app.infrastructure.db.unit_of_work import SqlAlchemyImportUnitOfWork
from praktikum_app.presentation.qt.main_window import MainWindow

TWidget = TypeVar("TWidget")


def test_main_window_shows_loaded_courses_from_db(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = Path("tests") / f"_runtime_courses_loaded_{uuid4().hex}.db"
    session_factory, engine = _seed_database(
        db_path,
        [
            _make_raw_text(
                source_type=CourseSourceType.TEXT_FILE,
                content="Курс один",
                filename="one.md",
                imported_at=datetime(2026, 2, 22, 9, 30, tzinfo=UTC),
            ),
            _make_raw_text(
                source_type=CourseSourceType.PDF,
                content="Курс два",
                filename="two.pdf",
                imported_at=datetime(2026, 2, 22, 10, 30, tzinfo=UTC),
            ),
        ],
    )
    window: MainWindow | None = None
    try:
        monkeypatch.setenv(DB_PATH_ENV_VAR, str(db_path.resolve()))
        monkeypatch.setattr(
            "praktikum_app.presentation.qt.main_window.create_default_session_factory",
            lambda: session_factory,
        )
        window = MainWindow()

        courses_list = _require_widget(window, QListWidget, "coursesList")
        assert courses_list.count() == 2
        assert "Файл: two.pdf" in courses_list.item(0).text()
        assert "Файл: one.md" in courses_list.item(1).text()
    finally:
        _dispose_window_and_db(application, window, engine, db_path)


def test_main_window_empty_state_when_no_courses(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = Path("tests") / f"_runtime_courses_empty_{uuid4().hex}.db"
    session_factory, engine = _seed_database(db_path, [])
    window: MainWindow | None = None
    try:
        monkeypatch.setenv(DB_PATH_ENV_VAR, str(db_path.resolve()))
        monkeypatch.setattr(
            "praktikum_app.presentation.qt.main_window.create_default_session_factory",
            lambda: session_factory,
        )
        window = MainWindow()

        empty_label = _require_widget(window, QLabel, "coursesEmptyStateLabel")
        delete_button = _require_widget(window, QPushButton, "deleteCourseButton")
        details_label = _require_widget(window, QLabel, "todayHintLabel")

        assert "Курсы пока не загружены" in empty_label.text()
        assert delete_button.isEnabled() is False
        assert details_label.text() == "Список курсов пуст."
    finally:
        _dispose_window_and_db(application, window, engine, db_path)


def test_main_window_delete_selected_course(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = Path("tests") / f"_runtime_courses_delete_{uuid4().hex}.db"
    session_factory, engine = _seed_database(
        db_path,
        [
            _make_raw_text(CourseSourceType.PASTE, "Курс A", None),
            _make_raw_text(CourseSourceType.PDF, "Курс B", "b.pdf"),
        ],
    )
    window: MainWindow | None = None
    try:
        monkeypatch.setenv(DB_PATH_ENV_VAR, str(db_path.resolve()))
        monkeypatch.setattr(
            "praktikum_app.presentation.qt.main_window.create_default_session_factory",
            lambda: session_factory,
        )
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        )

        window = MainWindow()
        courses_list = _require_widget(window, QListWidget, "coursesList")
        initial_ids = {
            str(courses_list.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(courses_list.count())
        }
        assert len(initial_ids) == 2

        courses_list.setCurrentRow(0)
        window._on_delete_selected_course_clicked()
        application.processEvents()

        remaining_ids = {
            str(courses_list.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(courses_list.count())
        }
        assert courses_list.count() == 1
        assert len(initial_ids - remaining_ids) == 1
        assert "Курс удалён." in window.statusBar().currentMessage()
    finally:
        _dispose_window_and_db(application, window, engine, db_path)


def test_main_window_delete_last_course_switches_to_empty_state(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = Path("tests") / f"_runtime_courses_delete_last_{uuid4().hex}.db"
    session_factory, engine = _seed_database(
        db_path,
        [_make_raw_text(CourseSourceType.TEXT_FILE, "Единственный курс", "single.md")],
    )
    window: MainWindow | None = None
    try:
        monkeypatch.setenv(DB_PATH_ENV_VAR, str(db_path.resolve()))
        monkeypatch.setattr(
            "praktikum_app.presentation.qt.main_window.create_default_session_factory",
            lambda: session_factory,
        )
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        )

        window = MainWindow()
        courses_list = _require_widget(window, QListWidget, "coursesList")
        empty_label = _require_widget(window, QLabel, "coursesEmptyStateLabel")
        details_label = _require_widget(window, QLabel, "todayHintLabel")
        courses_list.setCurrentRow(0)
        window._on_delete_selected_course_clicked()
        application.processEvents()

        assert courses_list.count() == 0
        assert "Курсы пока не загружены" in empty_label.text()
        assert details_label.text() == "Список курсов пуст."
    finally:
        _dispose_window_and_db(application, window, engine, db_path)


def test_main_window_delete_without_selection_shows_status_message(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = Path("tests") / f"_runtime_courses_no_selection_{uuid4().hex}.db"
    session_factory, engine = _seed_database(
        db_path,
        [_make_raw_text(CourseSourceType.PASTE, "Курс без выбора", None)],
    )
    window: MainWindow | None = None
    try:
        monkeypatch.setenv(DB_PATH_ENV_VAR, str(db_path.resolve()))
        monkeypatch.setattr(
            "praktikum_app.presentation.qt.main_window.create_default_session_factory",
            lambda: session_factory,
        )

        window = MainWindow()
        courses_list = _require_widget(window, QListWidget, "coursesList")
        courses_list.setCurrentRow(-1)
        window._on_delete_selected_course_clicked()

        assert "Выберите курс для удаления." in window.statusBar().currentMessage()
    finally:
        _dispose_window_and_db(application, window, engine, db_path)


def test_main_window_open_course_plan_without_selection_shows_status_message(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = Path("tests") / f"_runtime_courses_plan_no_selection_{uuid4().hex}.db"
    session_factory, engine = _seed_database(
        db_path,
        [_make_raw_text(CourseSourceType.PASTE, "Курс без выбора", None)],
    )
    window: MainWindow | None = None
    try:
        monkeypatch.setenv(DB_PATH_ENV_VAR, str(db_path.resolve()))
        monkeypatch.setattr(
            "praktikum_app.presentation.qt.main_window.create_default_session_factory",
            lambda: session_factory,
        )

        window = MainWindow()
        courses_list = _require_widget(window, QListWidget, "coursesList")
        courses_list.setCurrentRow(-1)
        window._on_open_course_plan_clicked()

        assert "Выберите курс для декомпозиции." in window.statusBar().currentMessage()
    finally:
        _dispose_window_and_db(application, window, engine, db_path)


def test_main_window_open_course_plan_dialog_for_selected_course(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = Path("tests") / f"_runtime_courses_plan_open_{uuid4().hex}.db"
    session_factory, engine = _seed_database(
        db_path,
        [_make_raw_text(CourseSourceType.PASTE, "Курс для плана", None)],
    )
    window: MainWindow | None = None
    calls: list[str] = []

    class FakeCoursePlanDialog:
        def __init__(self, *, course_id: str, **_: object) -> None:
            calls.append(course_id)

        def exec(self) -> int:
            return 0

    try:
        monkeypatch.setenv(DB_PATH_ENV_VAR, str(db_path.resolve()))
        monkeypatch.setattr(
            "praktikum_app.presentation.qt.main_window.create_default_session_factory",
            lambda: session_factory,
        )
        monkeypatch.setattr(
            "praktikum_app.presentation.qt.main_window.CoursePlanDialog",
            FakeCoursePlanDialog,
        )

        window = MainWindow()
        courses_list = _require_widget(window, QListWidget, "coursesList")
        courses_list.setCurrentRow(0)
        selected_course_id = str(courses_list.item(0).data(Qt.ItemDataRole.UserRole))
        window._on_open_course_plan_clicked()

        assert calls == [selected_course_id]
    finally:
        _dispose_window_and_db(application, window, engine, db_path)


def test_main_window_delete_shows_error_on_db_failure(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = Path("tests") / f"_runtime_courses_delete_error_{uuid4().hex}.db"
    session_factory, engine = _seed_database(
        db_path,
        [_make_raw_text(CourseSourceType.PASTE, "Ошибка удаления", None)],
    )
    window: MainWindow | None = None
    try:
        monkeypatch.setenv(DB_PATH_ENV_VAR, str(db_path.resolve()))
        monkeypatch.setattr(
            "praktikum_app.presentation.qt.main_window.create_default_session_factory",
            lambda: session_factory,
        )
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        )
        warnings: list[str] = []
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args, **kwargs: warnings.append("shown")
            or QMessageBox.StandardButton.Ok,
        )

        window = MainWindow()
        courses_list = _require_widget(window, QListWidget, "coursesList")
        courses_list.setCurrentRow(0)
        window._delete_course_use_case.execute = _raise_db_error
        window._on_delete_selected_course_clicked()

        assert warnings == ["shown"]
        assert courses_list.count() == 1
    finally:
        _dispose_window_and_db(application, window, engine, db_path)


def test_main_window_sets_error_state_when_course_loading_fails(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = Path("tests") / f"_runtime_courses_load_error_{uuid4().hex}.db"
    session_factory, engine = _seed_database(db_path, [])
    window: MainWindow | None = None
    try:
        monkeypatch.setenv(DB_PATH_ENV_VAR, str(db_path.resolve()))
        monkeypatch.setattr(
            "praktikum_app.presentation.qt.main_window.create_default_session_factory",
            lambda: session_factory,
        )
        window = MainWindow()
        window._list_courses_use_case.execute = lambda: (_ for _ in ()).throw(RuntimeError("db"))
        assert window._load_courses_from_db(show_error_dialog=False) is False

        empty_label = _require_widget(window, QLabel, "coursesEmptyStateLabel")
        assert "Не удалось загрузить список курсов из локальной БД." in empty_label.text()
    finally:
        _dispose_window_and_db(application, window, engine, db_path)


def _raise_db_error(course_id: str) -> bool:
    raise RuntimeError(f"db down for {course_id}")


def _require_widget(
    window: MainWindow,
    widget_type: type[TWidget],
    object_name: str,
) -> TWidget:
    widget = window.findChild(widget_type, object_name)
    assert widget is not None
    return widget


def _seed_database(
    db_path: Path,
    imports: list[RawCourseText],
) -> tuple[sessionmaker[Session], Engine]:
    engine = create_sqlite_engine(db_path)
    session_factory = create_session_factory(engine)
    Base.metadata.create_all(engine)
    persist_use_case = PersistImportedCourseUseCase(
        lambda: SqlAlchemyImportUnitOfWork(session_factory),
    )
    for imported in imports:
        persist_use_case.execute(imported)

    return session_factory, engine


def _dispose_window_and_db(
    application: QApplication,
    window: MainWindow | None,
    engine: Engine,
    db_path: Path,
) -> None:
    if window is not None:
        window.close()
        application.processEvents()
    engine.dispose()
    db_path.unlink(missing_ok=True)


def _make_raw_text(
    source_type: CourseSourceType,
    content: str,
    filename: str | None,
    imported_at: datetime | None = None,
) -> RawCourseText:
    imported_at_value = imported_at or datetime(2026, 2, 22, 12, 0, tzinfo=UTC)
    source = CourseSource(
        source_type=source_type,
        filename=filename,
        imported_at=imported_at_value,
    )
    return RawCourseText(
        content=content,
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        length=len(content),
        source=source,
    )
