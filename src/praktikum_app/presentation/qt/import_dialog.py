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

from praktikum_app.application.import_pdf_use_case import (
    ImportCoursePdfCommand,
    ImportCoursePdfUseCase,
)
from praktikum_app.application.import_persistence import (
    PersistImportedCourseUseCase,
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
        pdf_use_case: ImportCoursePdfUseCase | None = None,
        persist_use_case: PersistImportedCourseUseCase | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._use_case = use_case
        self._pdf_use_case = pdf_use_case or ImportCoursePdfUseCase()
        self._persist_use_case = persist_use_case
        self._store = store
        self._latest_preview: RawCourseText | None = None
        self._is_preview_dirty = True

        self._tabs = QTabWidget(self)
        self._file_path_input = QLineEdit(self)
        self._paste_input = QPlainTextEdit(self)
        self._pdf_path_input = QLineEdit(self)
        self._preview_output = QPlainTextEdit(self)
        self._preview_button = QPushButton("Предпросмотр", self)
        self._continue_button = QPushButton("Продолжить", self)
        self._cancel_button = QPushButton("Отмена", self)
        self._ocr_hint_label = QLabel(self)

        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("Импорт курса")
        self.resize(820, 620)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(12)

        self._tabs.setObjectName("importSourceTabs")
        self._tabs.addTab(self._build_file_tab(), "Текстовый файл")
        self._tabs.addTab(self._build_paste_tab(), "Вставка")
        self._tabs.addTab(self._build_pdf_tab(), "PDF")
        self._tabs.currentChanged.connect(self._on_source_changed)
        root_layout.addWidget(self._tabs)

        preview_label = QLabel("Предпросмотр (нормализованный текст)", self)
        root_layout.addWidget(preview_label)

        self._preview_output.setObjectName("importPreviewTextEdit")
        self._preview_output.setReadOnly(True)
        self._preview_output.setPlaceholderText(
            "Нажмите «Предпросмотр», чтобы увидеть результат."
        )
        root_layout.addWidget(self._preview_output, stretch=1)
        self._ocr_hint_label.setObjectName("ocrHintLabel")
        self._ocr_hint_label.setWordWrap(True)
        self._ocr_hint_label.setVisible(False)
        root_layout.addWidget(self._ocr_hint_label)

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
        self._file_path_input.textChanged.connect(self._on_file_path_changed)
        self._paste_input.textChanged.connect(self._on_paste_text_changed)
        self._pdf_path_input.textChanged.connect(self._on_pdf_path_changed)

    def _build_file_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        hint = QLabel("Выберите локальный файл .txt или .md.", tab)
        layout.addWidget(hint)

        file_row = QHBoxLayout()
        self._file_path_input.setObjectName("importFilePathInput")
        self._file_path_input.setPlaceholderText("Путь к файлу курса")
        browse_button = QPushButton("Обзор...", tab)
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

        hint = QLabel("Вставьте текст курса ниже.", tab)
        layout.addWidget(hint)

        self._paste_input.setObjectName("importPasteTextEdit")
        self._paste_input.setPlaceholderText(
            "Вставьте описание курса, программу или детали задания."
        )
        layout.addWidget(self._paste_input, stretch=1)
        return tab

    def _build_pdf_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        hint = QLabel("Выберите локальный файл .pdf.", tab)
        layout.addWidget(hint)

        file_row = QHBoxLayout()
        self._pdf_path_input.setObjectName("importPdfPathInput")
        self._pdf_path_input.setPlaceholderText("Путь к PDF-файлу")
        browse_button = QPushButton("Обзор...", tab)
        browse_button.setObjectName("importPdfBrowseButton")
        browse_button.clicked.connect(self._on_browse_pdf_clicked)

        file_row.addWidget(self._pdf_path_input, stretch=1)
        file_row.addWidget(browse_button)
        layout.addLayout(file_row)
        layout.addStretch(1)
        return tab

    def _on_browse_file_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите текстовый файл",
            "",
            "Текстовые файлы (*.txt *.md);;Все файлы (*)",
        )
        if file_path:
            self._file_path_input.setText(file_path)

    def _on_browse_pdf_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите PDF-файл",
            "",
            "PDF-файлы (*.pdf);;Все файлы (*)",
        )
        if file_path:
            self._pdf_path_input.setText(file_path)

    def _on_source_changed(self, _: int) -> None:
        self._invalidate_preview(reason="source_changed")

    def _on_file_path_changed(self, _: str) -> None:
        self._invalidate_preview(reason="file_path_changed")

    def _on_paste_text_changed(self) -> None:
        self._invalidate_preview(reason="paste_text_changed")

    def _on_pdf_path_changed(self, _: str) -> None:
        self._invalidate_preview(reason="pdf_path_changed")

    def set_active_source(self, source_type: CourseSourceType) -> None:
        """Select source tab programmatically for tests."""
        index_by_source = {
            CourseSourceType.TEXT_FILE: 0,
            CourseSourceType.PASTE: 1,
            CourseSourceType.PDF: 2,
        }
        index = index_by_source[source_type]
        self._tabs.setCurrentIndex(index)

    def set_file_path(self, file_path: str) -> None:
        """Set selected file path programmatically for tests."""
        self._file_path_input.setText(file_path)

    def set_paste_text(self, text: str) -> None:
        """Set pasted source text programmatically for tests."""
        self._paste_input.setPlainText(text)

    def set_pdf_path(self, file_path: str) -> None:
        """Set selected PDF path programmatically for tests."""
        self._pdf_path_input.setText(file_path)

    def preview_text(self) -> str:
        """Return current preview text."""
        return self._preview_output.toPlainText()

    def latest_preview(self) -> RawCourseText | None:
        """Return current preview result."""
        return self._latest_preview

    def is_preview_dirty(self) -> bool:
        """Return whether preview is outdated relative to current input."""
        return self._is_preview_dirty

    def ocr_hint_text(self) -> str:
        """Return current OCR hint text when visible."""
        return self._ocr_hint_label.text()

    def preview_import(self) -> None:
        """Generate normalized preview from selected source."""
        correlation_id = str(uuid4())
        source_type = self._active_source_type()
        if source_type is CourseSourceType.PDF:
            self._preview_pdf_import(correlation_id=correlation_id)
            return

        self._preview_text_import(correlation_id=correlation_id, source_type=source_type)

    def _preview_text_import(
        self,
        correlation_id: str,
        source_type: CourseSourceType,
    ) -> None:
        try:
            command = self._build_text_command(source_type=source_type)
            result = self._use_case.execute(command)
        except Exception as exc:
            self._invalidate_preview(reason="preview_failed")
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
                "Ошибка импорта",
                "Не удалось подготовить предпросмотр. Проверьте данные и попробуйте снова.",
            )
            return

        self._apply_preview_result(result=result)
        self._set_ocr_hint(is_likely_scanned=False)
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

    def _preview_pdf_import(self, correlation_id: str) -> None:
        try:
            command = ImportCoursePdfCommand(pdf_path=self._pdf_path_input.text().strip())
            result = self._pdf_use_case.execute(command)
        except Exception as exc:
            self._invalidate_preview(reason="pdf_preview_failed")
            LOGGER.exception(
                (
                    "event=import_pdf_preview_failed correlation_id=%s "
                    "course_id=- module_id=- llm_call_id=- "
                    "error_type=%s"
                ),
                correlation_id,
                exc.__class__.__name__,
            )
            message = (
                str(exc)
                if isinstance(exc, ValueError)
                else "Не удалось подготовить предпросмотр PDF."
            )
            QMessageBox.warning(self, "Ошибка импорта", message)
            return

        self._apply_preview_result(result=result.raw_text)
        self._set_ocr_hint(is_likely_scanned=result.likely_scanned)
        LOGGER.info(
            (
                "event=import_pdf_preview_ready correlation_id=%s "
                "course_id=- module_id=- llm_call_id=- extraction_strategy=%s "
                "page_count=%s used_fallback=%s likely_scanned=%s content_hash=%s length=%s"
            ),
            correlation_id,
            result.extraction_strategy,
            result.page_count,
            result.used_fallback,
            result.likely_scanned,
            result.raw_text.content_hash,
            result.raw_text.length,
        )

    def continue_import(self) -> None:
        """Persist preview result to storage and close dialog on success."""
        if self._latest_preview is None or self._is_preview_dirty:
            self.preview_import()
            if self._latest_preview is None or self._is_preview_dirty:
                return

        correlation_id = str(uuid4())
        imported = self._latest_preview
        assert imported is not None

        course_id = "-"
        source_id = "-"
        raw_text_id = "-"
        if self._persist_use_case is not None:
            try:
                persisted_record = self._persist_use_case.execute(imported)
            except Exception as exc:
                LOGGER.exception(
                    (
                        "event=import_continue_persist_failed correlation_id=%s "
                        "course_id=- module_id=- llm_call_id=- source_type=%s "
                        "content_hash=%s length=%s error_type=%s"
                    ),
                    correlation_id,
                    imported.source.source_type.value,
                    imported.content_hash,
                    imported.length,
                    exc.__class__.__name__,
                )
                QMessageBox.warning(
                    self,
                    "Ошибка импорта",
                    "Не удалось сохранить импорт в локальную БД. Выполните миграции и повторите.",
                )
                return

            course_id = persisted_record.course_id
            source_id = persisted_record.source_id
            raw_text_id = persisted_record.raw_text_id

        self._store.save(imported)
        LOGGER.info(
            (
                "event=import_continue_saved correlation_id=%s "
                "course_id=%s module_id=- llm_call_id=- source_id=%s raw_text_id=%s "
                "source_type=%s content_hash=%s length=%s"
            ),
            correlation_id,
            course_id,
            source_id,
            raw_text_id,
            imported.source.source_type.value,
            imported.content_hash,
            imported.length,
        )
        self.accept()

    def _invalidate_preview(self, reason: str) -> None:
        """Mark preview as stale after source changes."""
        if self._latest_preview is None and self._is_preview_dirty:
            return

        correlation_id = str(uuid4())
        self._latest_preview = None
        self._is_preview_dirty = True
        self._continue_button.setEnabled(False)
        self._preview_output.clear()
        self._set_ocr_hint(is_likely_scanned=False)
        LOGGER.info(
            (
                "event=import_preview_invalidated correlation_id=%s "
                "course_id=- module_id=- llm_call_id=- reason=%s source_type=%s"
            ),
            correlation_id,
            reason,
            self._active_source_type().value,
        )

    def _active_source_type(self) -> CourseSourceType:
        return (
            CourseSourceType.TEXT_FILE
            if self._tabs.currentIndex() == 0
            else (
                CourseSourceType.PASTE
                if self._tabs.currentIndex() == 1
                else CourseSourceType.PDF
            )
        )

    def _build_text_command(self, source_type: CourseSourceType) -> ImportCourseTextCommand:
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

    def _apply_preview_result(self, result: RawCourseText) -> None:
        self._latest_preview = result
        self._is_preview_dirty = False
        self._continue_button.setEnabled(True)
        self._preview_output.setPlainText(result.content)

    def _set_ocr_hint(self, is_likely_scanned: bool) -> None:
        if not is_likely_scanned:
            self._ocr_hint_label.setVisible(False)
            self._ocr_hint_label.clear()
            return

        self._ocr_hint_label.setText(
            "Этот PDF похож на скан или содержит мало текста. OCR может улучшить результат."
        )
        self._ocr_hint_label.setVisible(True)


def _read_text_file(file_path: str) -> str:
    """Read UTF-8 .txt/.md file for import flow."""
    if not file_path:
        raise ValueError("Файл не выбран.")

    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise ValueError("Выбранный файл не найден.")
    if path.suffix.lower() not in {".txt", ".md"}:
        raise ValueError("Неподдерживаемый тип файла. Выберите .txt или .md.")

    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig")
