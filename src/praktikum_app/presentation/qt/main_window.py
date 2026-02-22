"""Main window for course import and persisted course list management."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from praktikum_app.application.import_persistence import (
    DeleteImportedCourseUseCase,
    GetLatestImportedCourseUseCase,
    ImportedCourseSummary,
    ListImportedCoursesUseCase,
    PersistImportedCourseUseCase,
)
from praktikum_app.application.import_text_use_case import ImportCourseTextUseCase
from praktikum_app.application.in_memory_import_store import InMemoryImportStore
from praktikum_app.domain.import_text import CourseSourceType
from praktikum_app.infrastructure.db.session import create_default_session_factory
from praktikum_app.infrastructure.db.unit_of_work import SqlAlchemyImportUnitOfWork
from praktikum_app.presentation.qt.import_dialog import ImportCourseDialog

LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main shell with persisted courses list and deletion actions."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Текущие курсы")
        self.resize(1120, 720)

        self._import_use_case = ImportCourseTextUseCase()
        self._import_store = InMemoryImportStore()
        self._session_factory: sessionmaker[Session] | None = None

        self._persist_import_use_case = PersistImportedCourseUseCase(self._create_import_uow)
        self._latest_import_use_case = GetLatestImportedCourseUseCase(self._create_import_uow)
        self._list_courses_use_case = ListImportedCoursesUseCase(self._create_import_uow)
        self._delete_course_use_case = DeleteImportedCourseUseCase(self._create_import_uow)

        self._courses_by_id: dict[str, ImportedCourseSummary] = {}
        self._selected_course_id: str | None = None

        self._courses_list = QListWidget()
        self._empty_state_label = QLabel()
        self._course_details_label = QLabel()
        self._import_button = QPushButton("Импортировать курс...")
        self._refresh_button = QPushButton("Обновить из БД")
        self._delete_button = QPushButton("Удалить выбранный курс")

        self._build_ui()
        self._restore_courses_on_startup()

    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(18)

        title_label = QLabel("Текущие курсы", root)
        title_label.setObjectName("mainTitleLabel")
        subtitle_label = QLabel(
            "Здесь отображаются все импортированные курсы из локальной базы данных.",
            root,
        )
        subtitle_label.setObjectName("mainSubtitleLabel")
        subtitle_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

        separator = QFrame(root)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("headerSeparator")
        layout.addWidget(separator)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(20)
        content_layout.addWidget(self._build_courses_panel(root), stretch=3)
        content_layout.addWidget(self._build_actions_panel(root), stretch=2)
        layout.addLayout(content_layout)

        self._courses_list.currentItemChanged.connect(self._on_course_selection_changed)
        self._import_button.clicked.connect(self._on_import_course_clicked)
        self._refresh_button.clicked.connect(self._on_refresh_clicked)
        self._delete_button.clicked.connect(self._on_delete_selected_course_clicked)

        self.setCentralWidget(root)
        self.statusBar().showMessage("Готово", 2000)

    def _build_courses_panel(self, parent: QWidget) -> QGroupBox:
        panel = QGroupBox("Загруженные курсы", parent)
        panel.setObjectName("modulesPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 24, 16, 16)
        panel_layout.setSpacing(10)

        self._empty_state_label.setObjectName("coursesEmptyStateLabel")
        self._empty_state_label.setWordWrap(True)

        self._courses_list.setObjectName("coursesList")
        self._courses_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._courses_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        panel_layout.addWidget(self._courses_list, stretch=1)
        panel_layout.addWidget(self._empty_state_label)
        return panel

    def _build_actions_panel(self, parent: QWidget) -> QGroupBox:
        panel = QGroupBox("Действия", parent)
        panel.setObjectName("todayPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 24, 16, 16)
        panel_layout.setSpacing(12)

        selected_label = QLabel("Выбранный курс", panel)
        panel_layout.addWidget(selected_label)

        self._course_details_label.setObjectName("todayHintLabel")
        self._course_details_label.setWordWrap(True)
        panel_layout.addWidget(self._course_details_label)

        self._refresh_button.setObjectName("refreshCoursesButton")
        self._import_button.setObjectName("importCourseButton")
        self._delete_button.setObjectName("deleteCourseButton")
        self._delete_button.setEnabled(False)

        panel_layout.addStretch(1)
        panel_layout.addWidget(self._refresh_button)
        panel_layout.addWidget(self._import_button)
        panel_layout.addWidget(self._delete_button)
        return panel

    def _restore_courses_on_startup(self) -> None:
        """Restore list state from DB when app starts."""
        correlation_id = str(uuid4())
        latest_course_id: str | None = None
        try:
            latest_record = self._latest_import_use_case.execute()
        except Exception as exc:
            LOGGER.exception(
                (
                    "event=import_restore_startup_failed correlation_id=%s "
                    "course_id=- module_id=- llm_call_id=- error_type=%s"
                ),
                correlation_id,
                exc.__class__.__name__,
            )
            self._set_db_error_state(
                "Локальная БД недоступна. Выполните миграции: alembic upgrade head."
            )
            return

        if latest_record is not None:
            latest_course_id = latest_record.course_id
            self._import_store.save(latest_record.raw_text)

        self._load_courses_from_db(select_course_id=latest_course_id, show_error_dialog=False)

    def _on_refresh_clicked(self) -> None:
        correlation_id = str(uuid4())
        LOGGER.info(
            "event=courses_refresh_clicked correlation_id=%s course_id=- module_id=- llm_call_id=-",
            correlation_id,
        )
        if self._load_courses_from_db(show_error_dialog=True):
            self.statusBar().showMessage("Список курсов обновлён.", 3000)

    def _on_import_course_clicked(self) -> None:
        correlation_id = str(uuid4())
        LOGGER.info(
            "event=import_course_clicked correlation_id=%s course_id=- module_id=- llm_call_id=-",
            correlation_id,
        )
        try:
            dialog = ImportCourseDialog(
                use_case=self._import_use_case,
                store=self._import_store,
                persist_use_case=self._persist_import_use_case,
                parent=self,
            )
            result_code = dialog.exec()
            if result_code != QDialog.DialogCode.Accepted:
                LOGGER.info(
                    (
                        "event=import_dialog_cancelled correlation_id=%s "
                        "course_id=- module_id=- llm_call_id=-"
                    ),
                    correlation_id,
                )
                return

            latest_record = self._latest_import_use_case.execute()
            if latest_record is None:
                self._load_courses_from_db(show_error_dialog=False)
                self.statusBar().showMessage("Импорт завершён, но курс не найден в БД.", 4000)
                return

            self._import_store.save(latest_record.raw_text)
            self._load_courses_from_db(
                select_course_id=latest_record.course_id,
                show_error_dialog=False,
            )
            self.statusBar().showMessage("Курс импортирован и сохранён в локальную БД.", 5000)
            LOGGER.info(
                (
                    "event=import_dialog_completed correlation_id=%s course_id=%s "
                    "module_id=- llm_call_id=- source_type=%s content_hash=%s length=%s"
                ),
                correlation_id,
                latest_record.course_id,
                latest_record.raw_text.source.source_type.value,
                latest_record.raw_text.content_hash,
                latest_record.raw_text.length,
            )
        except Exception as exc:
            LOGGER.exception(
                (
                    "event=import_dialog_failed correlation_id=%s "
                    "course_id=- module_id=- llm_call_id=- error_type=%s"
                ),
                correlation_id,
                exc.__class__.__name__,
            )
            QMessageBox.warning(
                self,
                "Ошибка импорта",
                "Не удалось завершить импорт. Проверьте БД и попробуйте снова.",
            )

    def _on_delete_selected_course_clicked(self) -> None:
        course_id = self._selected_course_id
        if course_id is None:
            self.statusBar().showMessage("Выберите курс для удаления.", 3000)
            return

        summary = self._courses_by_id.get(course_id)
        if summary is None:
            self.statusBar().showMessage("Выбранный курс не найден.", 3000)
            return

        source_label = _source_type_label(summary.source_type)
        filename = summary.filename or _fallback_filename(summary.source_type)
        correlation_id = str(uuid4())
        LOGGER.info(
            (
                "event=course_delete_requested correlation_id=%s course_id=%s module_id=- "
                "llm_call_id=- source_type=%s length=%s content_hash=%s"
            ),
            correlation_id,
            summary.course_id,
            summary.source_type.value,
            summary.length,
            summary.content_hash,
        )

        confirmation = QMessageBox.question(
            self,
            "Подтверждение удаления",
            (
                "Удалить выбранный курс?\n\n"
                f"ID: {summary.course_id}\n"
                f"Источник: {source_label}\n"
                f"Файл: {filename}"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            LOGGER.info(
                (
                    "event=course_delete_cancelled correlation_id=%s "
                    "course_id=%s module_id=- llm_call_id=-"
                ),
                correlation_id,
                summary.course_id,
            )
            return

        try:
            deleted = self._delete_course_use_case.execute(summary.course_id)
        except Exception as exc:
            LOGGER.exception(
                (
                    "event=course_delete_failed correlation_id=%s course_id=%s module_id=- "
                    "llm_call_id=- error_type=%s"
                ),
                correlation_id,
                summary.course_id,
                exc.__class__.__name__,
            )
            QMessageBox.warning(
                self,
                "Ошибка базы данных",
                "Не удалось удалить курс из локальной БД.",
            )
            return

        if not deleted:
            self.statusBar().showMessage("Курс уже был удалён.", 4000)
            self._load_courses_from_db(show_error_dialog=False)
            return

        self._import_store.clear()
        self._load_courses_from_db(show_error_dialog=False)
        self.statusBar().showMessage("Курс удалён.", 4000)

    def _on_course_selection_changed(
        self,
        current_item: QListWidgetItem | None,
        _: QListWidgetItem | None,
    ) -> None:
        if current_item is None:
            self._selected_course_id = None
            self._delete_button.setEnabled(False)
            self._set_no_selection_state()
            return

        course_id_value = current_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(course_id_value, str):
            self._selected_course_id = None
            self._delete_button.setEnabled(False)
            self._set_no_selection_state()
            return

        summary = self._courses_by_id.get(course_id_value)
        if summary is None:
            self._selected_course_id = None
            self._delete_button.setEnabled(False)
            self._set_no_selection_state()
            return

        self._selected_course_id = summary.course_id
        self._delete_button.setEnabled(True)
        self._course_details_label.setText(_format_course_details(summary))
        correlation_id = str(uuid4())
        LOGGER.info(
            (
                "event=course_selected correlation_id=%s course_id=%s module_id=- llm_call_id=- "
                "source_type=%s length=%s content_hash=%s"
            ),
            correlation_id,
            summary.course_id,
            summary.source_type.value,
            summary.length,
            summary.content_hash,
        )

    def _load_courses_from_db(
        self,
        select_course_id: str | None = None,
        show_error_dialog: bool = False,
    ) -> bool:
        correlation_id = str(uuid4())
        try:
            courses = self._list_courses_use_case.execute()
        except Exception as exc:
            LOGGER.exception(
                (
                    "event=courses_load_failed correlation_id=%s course_id=- module_id=- "
                    "llm_call_id=- error_type=%s"
                ),
                correlation_id,
                exc.__class__.__name__,
            )
            self._set_db_error_state("Не удалось загрузить список курсов из локальной БД.")
            if show_error_dialog:
                QMessageBox.warning(
                    self,
                    "Ошибка базы данных",
                    "Не удалось загрузить список курсов из локальной БД.",
                )
            return False

        self._render_courses(courses, select_course_id=select_course_id)
        LOGGER.info(
            (
                "event=courses_load_success correlation_id=%s course_id=- module_id=- "
                "llm_call_id=- items_count=%s"
            ),
            correlation_id,
            len(courses),
        )
        return True

    def _render_courses(
        self,
        courses: list[ImportedCourseSummary],
        select_course_id: str | None = None,
    ) -> None:
        self._courses_by_id = {course.course_id: course for course in courses}

        self._courses_list.blockSignals(True)
        self._courses_list.clear()
        for course in courses:
            item = QListWidgetItem(_format_course_item(course))
            item.setData(Qt.ItemDataRole.UserRole, course.course_id)
            self._courses_list.addItem(item)
        self._courses_list.blockSignals(False)
        self._courses_list.setEnabled(True)

        if not courses:
            self._selected_course_id = None
            self._delete_button.setEnabled(False)
            self._empty_state_label.setText(
                "Курсы пока не загружены. Нажмите «Импортировать курс...»."
            )
            self._empty_state_label.setVisible(True)
            self._set_no_selection_state(is_empty=True)
            return

        self._empty_state_label.setVisible(False)
        selection_target = select_course_id
        if selection_target is None and self._selected_course_id in self._courses_by_id:
            selection_target = self._selected_course_id

        if selection_target is not None:
            for row_index in range(self._courses_list.count()):
                item = self._courses_list.item(row_index)
                if item.data(Qt.ItemDataRole.UserRole) == selection_target:
                    self._courses_list.setCurrentRow(row_index)
                    return

        self._courses_list.setCurrentRow(0)

    def _set_db_error_state(self, message: str) -> None:
        self._courses_by_id.clear()
        self._selected_course_id = None
        self._courses_list.clear()
        self._courses_list.setEnabled(False)
        self._delete_button.setEnabled(False)
        self._empty_state_label.setText(message)
        self._empty_state_label.setVisible(True)
        self._course_details_label.setText("Данные о курсе недоступны из-за ошибки БД.")
        self.statusBar().showMessage(message, 5000)

    def _set_no_selection_state(self, is_empty: bool = False) -> None:
        if is_empty:
            self._course_details_label.setText("Список курсов пуст.")
            return

        self._course_details_label.setText("Курс не выбран.")

    def _create_import_uow(self) -> SqlAlchemyImportUnitOfWork:
        session_factory = self._session_factory
        if session_factory is None:
            session_factory = create_default_session_factory()
            self._session_factory = session_factory
        return SqlAlchemyImportUnitOfWork(session_factory)


def _format_course_item(course: ImportedCourseSummary) -> str:
    imported_at = _format_datetime(course.imported_at)
    source_label = _source_type_label(course.source_type)
    filename = course.filename or _fallback_filename(course.source_type)
    short_hash = course.content_hash[:10]
    return (
        f"ID: {course.course_id}\n"
        f"Источник: {source_label} | Файл: {filename}\n"
        f"Импорт: {imported_at} | Длина: {course.length} | Хеш: {short_hash}"
    )


def _format_course_details(course: ImportedCourseSummary) -> str:
    imported_at = _format_datetime(course.imported_at)
    source_label = _source_type_label(course.source_type)
    filename = course.filename or _fallback_filename(course.source_type)
    short_hash = course.content_hash[:10]
    return (
        f"ID курса: {course.course_id}\n"
        f"Тип источника: {source_label}\n"
        f"Файл: {filename}\n"
        f"Импортирован: {imported_at}\n"
        f"Длина текста: {course.length}\n"
        f"Короткий хеш: {short_hash}"
    )


def _source_type_label(source_type: CourseSourceType) -> str:
    labels = {
        CourseSourceType.TEXT_FILE: "Текстовый файл",
        CourseSourceType.PASTE: "Вставка",
        CourseSourceType.PDF: "PDF",
    }
    return labels[source_type]


def _fallback_filename(source_type: CourseSourceType) -> str:
    labels = {
        CourseSourceType.TEXT_FILE: "без имени файла",
        CourseSourceType.PASTE: "вставленный текст",
        CourseSourceType.PDF: "PDF без имени",
    }
    return labels[source_type]


def _format_datetime(value: datetime) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M")
