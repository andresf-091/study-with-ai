"""Tests for UI shell layout, theme setup and tray fallback."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QListWidget, QPushButton

from praktikum_app.presentation.qt.main_window import MainWindow
from praktikum_app.presentation.qt.theme import apply_theme
from praktikum_app.presentation.qt.tray import TrayController


def test_main_window_has_target_shell_components(application: QApplication) -> None:
    """Main window should expose placeholder modules, today panel and import button."""
    window = MainWindow()

    modules_list = window.findChild(QListWidget, "modulesList")
    today_list = window.findChild(QListWidget, "todayList")
    import_button = window.findChild(QPushButton, "importCourseButton")
    today_hint = window.findChild(QLabel, "todayHintLabel")

    assert modules_list is not None
    assert modules_list.count() == 3
    assert today_list is not None
    assert today_list.count() == 3
    assert import_button is not None
    assert import_button.text() == "Import course..."
    assert today_hint is not None


def test_theme_application_loads_stylesheet(application: QApplication) -> None:
    """Theme setup should apply non-empty stylesheet to the QApplication."""
    apply_theme(application)
    style_sheet = application.styleSheet()
    assert "QMainWindow" in style_sheet
    assert "QPushButton" in style_sheet


def test_tray_controller_graceful_fallback(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tray controller should fallback when system tray is unavailable."""
    window = MainWindow()
    controller = TrayController(application=application, window=window)

    monkeypatch.setattr(controller, "_is_system_tray_available", lambda: False)
    controller.initialize()
    delivered_to_tray = controller.notify("Reminder", "Practice session in 10 minutes")

    assert controller.is_enabled is False
    assert delivered_to_tray is False
    assert "Reminder" in window.statusBar().currentMessage()
