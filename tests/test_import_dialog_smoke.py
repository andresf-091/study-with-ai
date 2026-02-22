"""Headless-friendly UI smoke tests for text import dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from praktikum_app.application.import_text_use_case import ImportCourseTextUseCase
from praktikum_app.application.in_memory_import_store import InMemoryImportStore
from praktikum_app.domain.import_text import CourseSourceType
from praktikum_app.presentation.qt.import_dialog import ImportCourseDialog


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
