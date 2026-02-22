"""Shared pytest fixtures for headless Qt tests."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from praktikum_app.presentation.qt.app import create_application


@pytest.fixture(scope="session")
def application() -> QApplication:
    """Create a single QApplication for the full test session."""
    app = create_application(["pytest"])
    yield app
    app.closeAllWindows()
    app.processEvents()


@pytest.fixture(autouse=True)
def _cleanup_qt_windows(application: QApplication) -> None:
    """Ensure Qt windows are closed between tests to reduce teardown crashes."""
    yield
    application.closeAllWindows()
    application.processEvents()
