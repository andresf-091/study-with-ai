"""Qt application bootstrap."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from praktikum_app.presentation.qt.main_window import MainWindow


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
    application = create_application(argv)
    window = MainWindow()
    window.show()
    return application.exec()
