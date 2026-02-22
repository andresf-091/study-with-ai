"""Headless-friendly UI smoke tests for text import dialog."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from praktikum_app.application.import_text_use_case import ImportCourseTextUseCase
from praktikum_app.application.in_memory_import_store import InMemoryImportStore
from praktikum_app.domain.import_text import CourseSourceType
from praktikum_app.presentation.qt.app import create_application
from praktikum_app.presentation.qt.import_dialog import ImportCourseDialog


@pytest.fixture
def application(monkeypatch: pytest.MonkeyPatch) -> QApplication:
    """Create QApplication using offscreen backend for UI tests."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = create_application([])
    yield app


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
