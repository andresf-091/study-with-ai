"""Smoke test for application startup."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from praktikum_app.presentation.qt.main_window import MainWindow


def test_main_window_startup_and_close(application: QApplication) -> None:
    """Main window should open and close without exceptions."""
    window = MainWindow()
    window.show()
    application.processEvents()

    assert window.isVisible()
    assert window.windowTitle() == "Текущие курсы"

    window.close()
    application.processEvents()

    assert not window.isVisible()
