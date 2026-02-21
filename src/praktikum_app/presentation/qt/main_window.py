"""Main window shell for MVP bootstrap."""

from __future__ import annotations

import logging
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main shell with module placeholders and daily panel."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Study with AI")
        self.resize(1080, 680)
        self._modules_list = QListWidget()
        self._today_list = QListWidget()
        self._import_button = QPushButton("Import course...")
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(18)

        title_label = QLabel("Praktikum of the Day", root)
        title_label.setObjectName("mainTitleLabel")
        subtitle_label = QLabel(
            "A composed study space: modules on the left, today's ritual on the right.",
            root,
        )
        subtitle_label.setObjectName("mainSubtitleLabel")
        subtitle_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

        separator = QFrame(root)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("headerSeparator")
        layout.addWidget(separator)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(20)
        content_layout.addWidget(self._build_modules_panel(root), stretch=3)
        content_layout.addWidget(self._build_today_panel(root), stretch=2)
        layout.addLayout(content_layout)

        self._import_button.setObjectName("importCourseButton")
        self._import_button.clicked.connect(self._on_import_course_clicked)
        layout.addWidget(self._import_button, alignment=Qt.AlignmentFlag.AlignRight)

        self.setCentralWidget(root)
        self.statusBar().showMessage("Ready", 2000)

    def _build_modules_panel(self, parent: QWidget) -> QGroupBox:
        panel = QGroupBox("Modules", parent)
        panel.setObjectName("modulesPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 24, 16, 16)
        panel_layout.setSpacing(10)

        self._modules_list.setObjectName("modulesList")
        self._modules_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._modules_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        module_items = (
            "Module I — Orientation and goals",
            "Module II — Deep work session",
            "Module III — Practice and reflection",
        )
        for module_text in module_items:
            self._modules_list.addItem(QListWidgetItem(module_text))

        panel_layout.addWidget(self._modules_list)
        return panel

    def _build_today_panel(self, parent: QWidget) -> QGroupBox:
        panel = QGroupBox("Today", parent)
        panel.setObjectName("todayPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 24, 16, 16)
        panel_layout.setSpacing(10)

        today_hint = QLabel(
            "No active course imported yet. Use Import course... to begin your plan.",
            panel,
        )
        today_hint.setObjectName("todayHintLabel")
        today_hint.setWordWrap(True)
        panel_layout.addWidget(today_hint)

        self._today_list.setObjectName("todayList")
        self._today_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._today_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        today_items = (
            "Read module brief",
            "Complete one focused practice block",
            "Log a short reflection",
        )
        for item_text in today_items:
            self._today_list.addItem(QListWidgetItem(item_text))
        panel_layout.addWidget(self._today_list)
        return panel

    def _on_import_course_clicked(self) -> None:
        correlation_id = str(uuid4())
        LOGGER.info(
            "event=import_course_clicked correlation_id=%s course_id=- module_id=- llm_call_id=-",
            correlation_id,
        )
        self.statusBar().showMessage(
            "Import flow will be implemented in a next PR.", 3000
        )
