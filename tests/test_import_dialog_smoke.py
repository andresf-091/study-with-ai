"""Headless-friendly UI smoke tests for text import dialog."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from praktikum_app.application.import_pdf_use_case import (
    ImportCoursePdfCommand,
    ImportCoursePdfResult,
)
from praktikum_app.application.import_persistence import PersistedImportRecord
from praktikum_app.application.import_text_use_case import ImportCourseTextUseCase
from praktikum_app.application.in_memory_import_store import InMemoryImportStore
from praktikum_app.domain.import_text import CourseSource, CourseSourceType, RawCourseText
from praktikum_app.presentation.qt.import_dialog import ImportCourseDialog
from tests.pdf_fixture_utils import write_simple_text_pdf


def test_import_dialog_paste_flow_preview_and_continue(application: QApplication) -> None:
    """Paste flow should produce preview and save in temporary store."""
    use_case = ImportCourseTextUseCase()
    store = InMemoryImportStore()
    dialog = ImportCourseDialog(use_case=use_case, store=store)

    dialog.set_active_source(CourseSourceType.PASTE)
    dialog.set_paste_text("  • Topic one  \n\n• Topic two")
    dialog.preview_import()

    preview = dialog.preview_text()
    assert preview == "- Topic one\n\n- Topic two"

    dialog.continue_import()
    imported = store.get_latest()

    assert imported is not None
    assert imported.source.source_type is CourseSourceType.PASTE
    assert imported.length == len(imported.content)


def test_import_dialog_continue_uses_latest_paste_after_preview(
    application: QApplication,
) -> None:
    """Continue should persist current input, not stale preview."""
    use_case = ImportCourseTextUseCase()
    store = InMemoryImportStore()
    dialog = ImportCourseDialog(use_case=use_case, store=store)

    dialog.set_active_source(CourseSourceType.PASTE)
    dialog.set_paste_text("A")
    dialog.preview_import()
    assert dialog.preview_text() == "A"
    assert dialog.is_preview_dirty() is False

    dialog.set_paste_text("B")
    assert dialog.is_preview_dirty() is True

    dialog.continue_import()
    imported = store.get_latest()

    assert imported is not None
    assert imported.content == "B"
    assert imported.source.source_type is CourseSourceType.PASTE


def test_import_dialog_text_file_flow_preview_and_continue(
    application: QApplication,
) -> None:
    """Text file flow should load source, normalize it and save to temporary store."""
    import_file = Path("tests") / "_import_source_runtime.md"
    import_file.write_text("  • Lesson one\n\n* Lesson two  ", encoding="utf-8")
    try:
        use_case = ImportCourseTextUseCase()
        store = InMemoryImportStore()
        dialog = ImportCourseDialog(use_case=use_case, store=store)

        dialog.set_active_source(CourseSourceType.TEXT_FILE)
        dialog.set_file_path(str(import_file))
        dialog.preview_import()

        assert dialog.preview_text() == "- Lesson one\n\n- Lesson two"

        dialog.continue_import()
        imported = store.get_latest()

        assert imported is not None
        assert imported.source.source_type is CourseSourceType.TEXT_FILE
        assert imported.source.filename == "_import_source_runtime.md"
    finally:
        import_file.unlink(missing_ok=True)


def test_import_dialog_continue_uses_latest_file_after_preview(
    application: QApplication,
) -> None:
    """Continue should recompute preview when file path changes after preview."""
    file_a = Path("tests") / "_import_source_a.md"
    file_b = Path("tests") / "_import_source_b.md"
    file_a.write_text("Module A", encoding="utf-8")
    file_b.write_text("Module B", encoding="utf-8")

    try:
        use_case = ImportCourseTextUseCase()
        store = InMemoryImportStore()
        dialog = ImportCourseDialog(use_case=use_case, store=store)

        dialog.set_active_source(CourseSourceType.TEXT_FILE)
        dialog.set_file_path(str(file_a))
        dialog.preview_import()
        assert dialog.preview_text() == "Module A"
        assert dialog.is_preview_dirty() is False

        dialog.set_file_path(str(file_b))
        assert dialog.is_preview_dirty() is True

        dialog.continue_import()
        imported = store.get_latest()

        assert imported is not None
        assert imported.content == "Module B"
        assert imported.source.filename == "_import_source_b.md"
    finally:
        file_a.unlink(missing_ok=True)
        file_b.unlink(missing_ok=True)


def test_import_dialog_pdf_flow_preview_and_continue(application: QApplication) -> None:
    """PDF tab should extract preview text and save into in-memory store."""
    pdf_file = Path("tests") / "_import_pdf_runtime.pdf"
    write_simple_text_pdf(pdf_file, "PDF import lesson outline")
    try:
        use_case = ImportCourseTextUseCase()
        store = InMemoryImportStore()
        dialog = ImportCourseDialog(use_case=use_case, store=store)

        dialog.set_active_source(CourseSourceType.PDF)
        dialog.set_pdf_path(str(pdf_file))
        dialog.preview_import()

        assert "PDF import lesson outline" in dialog.preview_text()

        dialog.continue_import()
        imported = store.get_latest()
        assert imported is not None
        assert imported.source.source_type is CourseSourceType.PDF
        assert imported.source.filename == "_import_pdf_runtime.pdf"
    finally:
        pdf_file.unlink(missing_ok=True)


def test_import_dialog_pdf_flow_shows_ocr_hint_for_low_text(application: QApplication) -> None:
    """Low-text PDF preview should show OCR hint without breaking flow."""
    class FakePdfUseCase:
        def execute(self, command: ImportCoursePdfCommand) -> ImportCoursePdfResult:
            source = CourseSource(
                source_type=CourseSourceType.PDF,
                filename="scan_like.pdf",
                imported_at=datetime.now(tz=UTC),
            )
            raw_text = RawCourseText(
                content="x",
                content_hash="hash",
                length=1,
                source=source,
            )
            return ImportCoursePdfResult(
                raw_text=raw_text,
                likely_scanned=True,
                extraction_strategy="pypdf",
                page_count=1,
                used_fallback=False,
            )

    use_case = ImportCourseTextUseCase()
    store = InMemoryImportStore()
    dialog = ImportCourseDialog(
        use_case=use_case,
        store=store,
        pdf_use_case=FakePdfUseCase(),
    )

    dialog.set_active_source(CourseSourceType.PDF)
    dialog.set_pdf_path("scan_like.pdf")
    dialog.preview_import()

    assert "OCR may improve extraction quality" in dialog.ocr_hint_text()


def test_import_dialog_continue_calls_persistence_use_case(application: QApplication) -> None:
    """Continue should call persistence use-case before closing dialog."""

    class FakePersistUseCase:
        def __init__(self) -> None:
            self.saved: RawCourseText | None = None

        def execute(self, imported_text: RawCourseText) -> PersistedImportRecord:
            self.saved = imported_text
            return PersistedImportRecord(
                course_id="course-1",
                source_id="source-1",
                raw_text_id="raw-1",
                raw_text=imported_text,
            )

    persist_use_case = FakePersistUseCase()
    use_case = ImportCourseTextUseCase()
    store = InMemoryImportStore()
    dialog = ImportCourseDialog(
        use_case=use_case,
        store=store,
        persist_use_case=persist_use_case,
    )

    dialog.set_active_source(CourseSourceType.PASTE)
    dialog.set_paste_text("Persist this import")
    dialog.preview_import()
    dialog.continue_import()

    assert persist_use_case.saved is not None
    assert persist_use_case.saved.content == "Persist this import"
    assert dialog.result() == dialog.DialogCode.Accepted


def test_import_dialog_shows_message_when_persistence_fails(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persistence failure should keep dialog open and show concise user message."""

    class FailingPersistUseCase:
        def execute(self, imported_text: RawCourseText) -> PersistedImportRecord:
            raise RuntimeError("database unavailable")

    warnings: list[str] = []

    def _fake_warning(*_: object) -> int:
        warnings.append("shown")
        return 0

    monkeypatch.setattr(
        "praktikum_app.presentation.qt.import_dialog.QMessageBox.warning",
        _fake_warning,
    )

    use_case = ImportCourseTextUseCase()
    store = InMemoryImportStore()
    dialog = ImportCourseDialog(
        use_case=use_case,
        store=store,
        persist_use_case=FailingPersistUseCase(),
    )
    dialog.set_active_source(CourseSourceType.PASTE)
    dialog.set_paste_text("DB error sample")
    dialog.preview_import()
    dialog.continue_import()

    assert warnings == ["shown"]
    assert store.get_latest() is None
    assert dialog.result() != dialog.DialogCode.Accepted
