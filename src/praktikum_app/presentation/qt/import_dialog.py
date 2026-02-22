"""UI dialog for importing course text from file or paste."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from praktikum_app.application.import_text_use_case import (
    ImportCourseTextCommand,
    ImportCourseTextUseCase,
)
from praktikum_app.application.in_memory_import_store import InMemoryImportStore
from praktikum_app.domain.import_text import CourseSourceType, RawCourseText

LOGGER = logging.getLogger(__name__)


class ImportCourseDialog(QDialog):
    """Dialog to preview and continue text import."""

    def __init__(
        self,
        use_case: ImportCourseTextUseCase,
        store: InMemoryImportStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._use_case = use_case
        self._store = store
        self._latest_preview: RawCourseText | None = None

        self._tabs = QTabWidget(self)
        self._file_path_input = QLineEdit(self)
        self._paste_input = QPlainTextEdit(self)
        self._preview_output = QPlainTextEdit(self)
        self._preview_button = QPushButton("Preview", self)
        self._continue_button = QPushButton("Continue", self)
        self._cancel_button = QPushButton("Cancel", self)

        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("Import Course Text")
        self.resize(820, 620)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(12)

        self._tabs.setObjectName("importSourceTabs")
        self._tabs.addTab(self._build_file_tab(), "Text file")
        self._tabs.addTab(self._build_paste_tab(), "Paste")
        self._tabs.currentChanged.connect(self._on_source_changed)
        root_layout.addWidget(self._tabs)

        preview_label = QLabel("Preview (normalized text)", self)
        root_layout.addWidget(preview_label)

        self._preview_output.setObjectName("importPreviewTextEdit")
        self._preview_output.setReadOnly(True)
        self._preview_output.setPlaceholderText("Preview will appear here after clicking Preview.")
        root_layout.addWidget(self._preview_output, stretch=1)

        actions_layout = QHBoxLayout()
        actions_layout.addWidget(self._preview_button)
        actions_layout.addStretch(1)
        actions_layout.addWidget(self._continue_button)
        actions_layout.addWidget(self._cancel_button)
        root_layout.addLayout(actions_layout)

        self._preview_button.clicked.connect(self.preview_import)
        self._continue_button.clicked.connect(self.continue_import)
        self._cancel_button.clicked.connect(self.reject)
        self._continue_button.setEnabled(False)

    def _build_file_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        hint = QLabel("Choose a local .txt or .md file.", tab)
        layout.addWidget(hint)

        file_row = QHBoxLayout()
        self._file_path_input.setObjectName("importFilePathInput")
        self._file_path_input.setPlaceholderText("Path to course text file")
        browse_button = QPushButton("Browse...", tab)
        browse_button.setObjectName("importFileBrowseButton")
        browse_button.clicked.connect(self._on_browse_file_clicked)

        file_row.addWidget(self._file_path_input, stretch=1)
        file_row.addWidget(browse_button)
        layout.addLayout(file_row)
        layout.addStretch(1)
        return tab

    def _build_paste_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        hint = QLabel("Paste course text below.", tab)
        layout.addWidget(hint)

        self._paste_input.setObjectName("importPasteTextEdit")
        self._paste_input.setPlaceholderText(
            "Paste course description, syllabus, or assignment details."
        )
        layout.addWidget(self._paste_input, stretch=1)
        return tab

    def _on_browse_file_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select text file",
            "",
            "Text files (*.txt *.md);;All files (*)",
        )
        if file_path:
            self._file_path_input.setText(file_path)

    def _on_source_changed(self, _: int) -> None:
        self._latest_preview = None
        self._continue_button.setEnabled(False)
        self._preview_output.clear()

    def set_active_source(self, source_type: CourseSourceType) -> None:
        """Select source tab programmatically for tests."""
        index = 0 if source_type is CourseSourceType.TEXT_FILE else 1
        self._tabs.setCurrentIndex(index)

    def set_file_path(self, file_path: str) -> None:
        """Set selected file path programmatically for tests."""
        self._file_path_input.setText(file_path)

    def set_paste_text(self, text: str) -> None:
        """Set pasted source text programmatically for tests."""
        self._paste_input.setPlainText(text)

    def preview_text(self) -> str:
        """Return current preview text."""
        return self._preview_output.toPlainText()

    def latest_preview(self) -> RawCourseText | None:
        """Return current preview result."""
        return self._latest_preview

    def preview_import(self) -> None:
        """Generate normalized preview from selected source."""
        correlation_id = str(uuid4())
        source_type = self._active_source_type()
        try:
            command = self._build_command()
            result = self._use_case.execute(command)
        except Exception as exc:
            self._latest_preview = None
            self._continue_button.setEnabled(False)
            self._preview_output.clear()
            LOGGER.exception(
                (
                    "event=import_preview_failed correlation_id=%s "
                    "course_id=- module_id=- llm_call_id=- "
                    "source_type=%s error_type=%s"
                ),
                correlation_id,
                source_type.value,
                exc.__class__.__name__,
            )
            QMessageBox.warning(
                self,
                "Import Error",
                "Could not prepare import preview. Check input and try again.",
            )
            return

        self._latest_preview = result
        self._continue_button.setEnabled(True)
        self._preview_output.setPlainText(result.content)
        LOGGER.info(
            (
                "event=import_preview_ready correlation_id=%s "
                "course_id=- module_id=- llm_call_id=- "
                "source_type=%s content_hash=%s length=%s"
            ),
            correlation_id,
            result.source.source_type.value,
            result.content_hash,
            result.length,
        )

    def continue_import(self) -> None:
        """Persist preview result in temporary in-memory store and close dialog."""
        if self._latest_preview is None:
            self.preview_import()
            if self._latest_preview is None:
                return

        correlation_id = str(uuid4())
        imported = self._latest_preview
        assert imported is not None
        self._store.save(imported)
        LOGGER.info(
            (
                "event=import_continue_saved correlation_id=%s "
                "course_id=- module_id=- llm_call_id=- "
                "source_type=%s content_hash=%s length=%s"
            ),
            correlation_id,
            imported.source.source_type.value,
            imported.content_hash,
            imported.length,
        )
        self.accept()

    def _active_source_type(self) -> CourseSourceType:
        return (
            CourseSourceType.TEXT_FILE
            if self._tabs.currentIndex() == 0
            else CourseSourceType.PASTE
        )

    def _build_command(self) -> ImportCourseTextCommand:
        source_type = self._active_source_type()
        if source_type is CourseSourceType.TEXT_FILE:
            file_path = self._file_path_input.text().strip()
            file_content = _read_text_file(file_path)
            return ImportCourseTextCommand(
                source_type=source_type,
                content=file_content,
                filename=Path(file_path).name,
            )

        paste_content = self._paste_input.toPlainText()
        return ImportCourseTextCommand(
            source_type=source_type,
            content=paste_content,
            filename=None,
        )


def _read_text_file(file_path: str) -> str:
    """Read UTF-8 .txt/.md file for import flow."""
    if not file_path:
        raise ValueError("No file selected.")

    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise ValueError("Selected file does not exist.")
    if path.suffix.lower() not in {".txt", ".md"}:
        raise ValueError("Unsupported file type. Choose .txt or .md.")

    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig")
