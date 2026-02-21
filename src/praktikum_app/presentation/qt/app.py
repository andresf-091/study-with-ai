"""Qt application bootstrap."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from uuid import uuid4

from PySide6.QtWidgets import QApplication

from praktikum_app.presentation.qt.main_window import MainWindow
from praktikum_app.presentation.qt.theme import apply_theme
from praktikum_app.presentation.qt.tray import TrayController

LOGGER = logging.getLogger(__name__)


def create_application(argv: Sequence[str] | None = None) -> QApplication:
    """Create or return the singleton QApplication instance."""
    existing_app = QApplication.instance()
    if isinstance(existing_app, QApplication):
        return existing_app

    resolved_argv = list(argv) if argv is not None else []
    application = QApplication(resolved_argv)
    application.setApplicationName("Study with AI")
    application.setOrganizationName("Praktikum")
    return application


def run(argv: Sequence[str] | None = None) -> int:
    """Run Qt event loop with the main window."""
    correlation_id = str(uuid4())
    LOGGER.info(
        "event=app_start correlation_id=%s course_id=- module_id=- llm_call_id=-",
        correlation_id,
    )
    application = create_application(argv)
    apply_theme(application)
    window = MainWindow()
    tray_controller = TrayController(application=application, window=window)
    tray_controller.initialize()
    window.show()
    exit_code = application.exec()
    LOGGER.info(
        "event=app_exit correlation_id=%s course_id=- module_id=- llm_call_id=- exit_code=%s",
        correlation_id,
        exit_code,
    )
    return exit_code
