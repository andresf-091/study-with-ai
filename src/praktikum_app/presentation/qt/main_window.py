"""Main window shell for MVP bootstrap."""

from __future__ import annotations

import logging
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Minimal main window with import stub action."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Study with AI")
        self.resize(960, 640)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        import_button = QPushButton("Import course...", root)
        import_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        import_button.clicked.connect(self._on_import_course_clicked)

        layout.addWidget(import_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(root)
        self.statusBar().showMessage("Ready", 2000)

    def _on_import_course_clicked(self) -> None:
        correlation_id = str(uuid4())
        LOGGER.info(
            "event=import_course_clicked correlation_id=%s course_id=- module_id=- llm_call_id=-",
            correlation_id,
        )
        self.statusBar().showMessage("Import flow will be implemented in a next PR.", 3000)
