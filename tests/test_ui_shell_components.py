"""Tests for UI shell layout, theme setup and tray fallback."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QListWidget, QPushButton

from praktikum_app.presentation.qt.main_window import MainWindow
from praktikum_app.presentation.qt.theme import apply_theme
from praktikum_app.presentation.qt.tray import TrayController


def test_main_window_has_target_shell_components(application: QApplication) -> None:
    """Main window should expose courses list and action panel widgets."""
    window = MainWindow()

    courses_list = window.findChild(QListWidget, "coursesList")
    import_button = window.findChild(QPushButton, "importCourseButton")
    refresh_button = window.findChild(QPushButton, "refreshCoursesButton")
    delete_button = window.findChild(QPushButton, "deleteCourseButton")
    course_plan_button = window.findChild(QPushButton, "coursePlanButton")
    llm_keys_button = window.findChild(QPushButton, "llmKeysButton")
    details_label = window.findChild(QLabel, "todayHintLabel")
    empty_label = window.findChild(QLabel, "coursesEmptyStateLabel")

    assert window.windowTitle() == "Текущие курсы"
    assert courses_list is not None
    assert import_button is not None
    assert import_button.text() == "Импортировать курс..."
    assert refresh_button is not None
    assert refresh_button.text() == "Обновить из БД"
    assert delete_button is not None
    assert delete_button.text() == "Удалить выбранный курс"
    assert course_plan_button is not None
    assert course_plan_button.text() == "План курса..."
    assert llm_keys_button is not None
    assert llm_keys_button.text() == "Ключи LLM..."
    assert details_label is not None
    assert empty_label is not None


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
    delivered_to_tray = controller.notify("Напоминание", "Практика начнётся через 10 минут")

    assert controller.is_enabled is False
    assert delivered_to_tray is False
    assert "Напоминание" in window.statusBar().currentMessage()
