"""Main window shell for MVP bootstrap."""

from __future__ import annotations

import logging
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
    GetLatestImportedCourseUseCase,
    PersistImportedCourseUseCase,
)
from praktikum_app.application.import_text_use_case import ImportCourseTextUseCase
from praktikum_app.application.in_memory_import_store import InMemoryImportStore
from praktikum_app.infrastructure.db.session import create_default_session_factory
from praktikum_app.infrastructure.db.unit_of_work import SqlAlchemyImportUnitOfWork
from praktikum_app.presentation.qt.import_dialog import ImportCourseDialog

LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main shell with module placeholders and daily panel."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Study with AI")
        self.resize(1080, 680)
        self._modules_list = QListWidget()
        self._today_list = QListWidget()
        self._import_button = QPushButton("Import course...")
        self._today_hint_label: QLabel | None = None
        self._import_use_case = ImportCourseTextUseCase()
        self._import_store = InMemoryImportStore()
        self._session_factory: sessionmaker[Session] | None = None
        self._persist_import_use_case = PersistImportedCourseUseCase(self._create_import_uow)
        self._latest_import_use_case = GetLatestImportedCourseUseCase(self._create_import_uow)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(18)

        title_label = QLabel("Praktikum of the Day", root)
        title_label.setObjectName("mainTitleLabel")
        subtitle_label = QLabel(
            "A composed study space: modules on the left, today's ritual on the right.",
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
        content_layout.addWidget(self._build_modules_panel(root), stretch=3)
        content_layout.addWidget(self._build_today_panel(root), stretch=2)
        layout.addLayout(content_layout)

        self._import_button.setObjectName("importCourseButton")
        self._import_button.clicked.connect(self._on_import_course_clicked)
        layout.addWidget(self._import_button, alignment=Qt.AlignmentFlag.AlignRight)

        self.setCentralWidget(root)
        self.statusBar().showMessage("Ready", 2000)

    def _build_modules_panel(self, parent: QWidget) -> QGroupBox:
        panel = QGroupBox("Modules", parent)
        panel.setObjectName("modulesPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 24, 16, 16)
        panel_layout.setSpacing(10)

        self._modules_list.setObjectName("modulesList")
        self._modules_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._modules_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        module_items = (
            "Module I — Orientation and goals",
            "Module II — Deep work session",
            "Module III — Practice and reflection",
        )
        for module_text in module_items:
            self._modules_list.addItem(QListWidgetItem(module_text))

        panel_layout.addWidget(self._modules_list)
        return panel

    def _build_today_panel(self, parent: QWidget) -> QGroupBox:
        panel = QGroupBox("Today", parent)
        panel.setObjectName("todayPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 24, 16, 16)
        panel_layout.setSpacing(10)

        today_hint = QLabel(
            "No active course imported yet. Use Import course... to begin your plan.",
            panel,
        )
        today_hint.setObjectName("todayHintLabel")
        today_hint.setWordWrap(True)
        self._today_hint_label = today_hint
        panel_layout.addWidget(today_hint)

        self._today_list.setObjectName("todayList")
        self._today_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._today_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        today_items = (
            "Read module brief",
            "Complete one focused practice block",
            "Log a short reflection",
        )
        for item_text in today_items:
            self._today_list.addItem(QListWidgetItem(item_text))
        panel_layout.addWidget(self._today_list)
        return panel

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

            try:
                persisted_import = self._latest_import_use_case.execute()
            except Exception as exc:
                LOGGER.exception(
                    (
                        "event=import_latest_read_failed correlation_id=%s "
                        "course_id=- module_id=- llm_call_id=- error_type=%s"
                    ),
                    correlation_id,
                    exc.__class__.__name__,
                )
                QMessageBox.warning(
                    self,
                    "Import Error",
                    "Could not load imported data from local database.",
                )
                return

            if persisted_import is None:
                self.statusBar().showMessage("No import data saved to local database.", 3000)
                return

            imported = persisted_import.raw_text
            self._import_store.save(imported)
            self.statusBar().showMessage(
                "Text imported and saved to local database.",
                5000,
            )
            self._update_today_hint(
                source_label=imported.source.filename or imported.source.source_type.value,
                content_hash=imported.content_hash,
                length=imported.length,
            )
            LOGGER.info(
                (
                    "event=import_dialog_completed correlation_id=%s "
                    "course_id=%s module_id=- llm_call_id=- "
                    "source_type=%s content_hash=%s length=%s"
                ),
                correlation_id,
                persisted_import.course_id,
                imported.source.source_type.value,
                imported.content_hash,
                imported.length,
            )
        except Exception as exc:
            LOGGER.exception(
                (
                    "event=import_dialog_failed correlation_id=%s "
                    "course_id=- module_id=- llm_call_id=- "
                    "error_type=%s"
                ),
                correlation_id,
                exc.__class__.__name__,
            )
            QMessageBox.warning(
                self,
                "Import Error",
                "Could not complete import. Please try again.",
            )

    def _create_import_uow(self) -> SqlAlchemyImportUnitOfWork:
        session_factory = self._session_factory
        if session_factory is None:
            session_factory = create_default_session_factory()
            self._session_factory = session_factory

        return SqlAlchemyImportUnitOfWork(session_factory)

    def _update_today_hint(self, source_label: str, content_hash: str, length: int) -> None:
        if self._today_hint_label is None:
            return

        short_hash = content_hash[:10]
        self._today_hint_label.setText(
            f"Imported source: {source_label}\nLength: {length} chars | Hash: {short_hash}"
        )
