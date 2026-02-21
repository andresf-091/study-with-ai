"""Smoke test for application startup."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from praktikum_app.presentation.qt.app import create_application
from praktikum_app.presentation.qt.main_window import MainWindow


@pytest.fixture
def application(monkeypatch: pytest.MonkeyPatch) -> QApplication:
    """Create QApplication using offscreen backend for CI."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = create_application([])
    yield app


def test_main_window_startup_and_close(application: QApplication) -> None:
    """Main window should open and close without exceptions."""
    window = MainWindow()
    window.show()
    application.processEvents()

    assert window.isVisible()
    assert window.windowTitle() == "Study with AI"

    window.close()
    application.processEvents()

    assert not window.isVisible()
