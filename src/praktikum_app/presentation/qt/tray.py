"""System tray integration for the Qt presentation shell."""

from __future__ import annotations

import logging
from uuid import uuid4

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QStyle, QSystemTrayIcon

LOGGER = logging.getLogger(__name__)


class TrayController:
    """Manage system tray icon, context menu and notifications."""

    def __init__(self, application: QApplication, window: QMainWindow) -> None:
        self._application = application
        self._window = window
        self._tray_icon: QSystemTrayIcon | None = None
        self._context_menu: QMenu | None = None

    @property
    def is_enabled(self) -> bool:
        """Return whether tray is active in current environment."""
        return self._tray_icon is not None

    def initialize(self) -> None:
        """Initialize tray integration when available."""
        correlation_id = str(uuid4())
        if not self._is_system_tray_available():
            LOGGER.info(
                "event=tray_unavailable correlation_id=%s course_id=- module_id=- llm_call_id=-",
                correlation_id,
            )
            return

        tray_icon = QSystemTrayIcon(
            self._window.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon),
            self._window,
        )
        context_menu = QMenu(self._window)

        open_action = QAction("Открыть", context_menu)
        open_action.triggered.connect(self.open_main_window)
        quit_action = QAction("Выход", context_menu)
        quit_action.triggered.connect(self.quit_application)

        context_menu.addAction(open_action)
        context_menu.addSeparator()
        context_menu.addAction(quit_action)

        tray_icon.setContextMenu(context_menu)
        tray_icon.setToolTip("Практикум с ИИ")
        tray_icon.activated.connect(self._on_activated)
        tray_icon.show()

        self._tray_icon = tray_icon
        self._context_menu = context_menu
        LOGGER.info(
            "event=tray_initialized correlation_id=%s course_id=- module_id=- llm_call_id=-",
            correlation_id,
        )

    def notify(self, title: str, text: str) -> bool:
        """Show notification in tray; fallback to status bar when unavailable."""
        correlation_id = str(uuid4())
        if self._tray_icon is None:
            self._window.statusBar().showMessage(f"{title}: {text}", 4000)
            LOGGER.info(
                (
                    "event=tray_notify_fallback correlation_id=%s course_id=- "
                    "module_id=- llm_call_id=-"
                ),
                correlation_id,
            )
            return False

        self._tray_icon.showMessage(
            title,
            text,
            QSystemTrayIcon.MessageIcon.Information,
            4000,
        )
        LOGGER.info(
            "event=tray_notify_sent correlation_id=%s course_id=- module_id=- llm_call_id=-",
            correlation_id,
        )
        return True

    def open_main_window(self) -> None:
        """Bring the main window to foreground."""
        correlation_id = str(uuid4())
        self._window.show()
        self._window.showNormal()
        self._window.raise_()
        self._window.activateWindow()
        LOGGER.info(
            "event=tray_open_clicked correlation_id=%s course_id=- module_id=- llm_call_id=-",
            correlation_id,
        )

    def quit_application(self) -> None:
        """Quit the Qt application from tray action."""
        correlation_id = str(uuid4())
        LOGGER.info(
            "event=tray_quit_clicked correlation_id=%s course_id=- module_id=- llm_call_id=-",
            correlation_id,
        )
        self._application.quit()

    def _is_system_tray_available(self) -> bool:
        """Protected wrapper to simplify deterministic tests."""
        return QSystemTrayIcon.isSystemTrayAvailable()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle click activation from tray icon."""
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.open_main_window()
