"""Theme and typography configuration for Qt presentation layer."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

LOGGER = logging.getLogger(__name__)
_DEFAULT_SERIF_FAMILY = "Times New Roman"
_ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"


def apply_theme(application: QApplication) -> None:
    """Apply typography and style sheet for the application."""
    correlation_id = str(uuid4())
    chosen_font_family = _configure_typography(
        application=application,
        correlation_id=correlation_id,
    )
    stylesheet_loaded = _apply_stylesheet(application=application, correlation_id=correlation_id)
    LOGGER.info(
        (
            "event=ui_theme_applied correlation_id=%s course_id=- module_id=- llm_call_id=- "
            "font_family=%s stylesheet_loaded=%s"
        ),
        correlation_id,
        chosen_font_family,
        stylesheet_loaded,
    )


def _configure_typography(application: QApplication, correlation_id: str) -> str:
    """Load optional local fonts and configure serif fallback."""
    loaded_families = _load_local_fonts(correlation_id=correlation_id)
    chosen_family = loaded_families[0] if loaded_families else _DEFAULT_SERIF_FAMILY

    font = QFont(chosen_family)
    font.setStyleHint(QFont.StyleHint.Serif)
    font.setPointSize(11)
    application.setFont(font)
    return chosen_family


def _load_local_fonts(correlation_id: str) -> list[str]:
    """Load local font assets when they are available."""
    font_files = _font_asset_files()
    loaded_families: list[str] = []

    for font_file in font_files:
        family = _register_font(font_file)
        if family is not None:
            loaded_families.append(family)

    LOGGER.info(
        (
            "event=ui_fonts_loaded correlation_id=%s course_id=- module_id=- llm_call_id=- "
            "font_files=%s loaded_families=%s"
        ),
        correlation_id,
        len(font_files),
        len(loaded_families),
    )
    return loaded_families


def _font_asset_files() -> list[Path]:
    """Return font files from local package assets."""
    fonts_dir = _ASSETS_DIR / "fonts"
    if not fonts_dir.exists():
        return []

    fonts: list[Path] = []
    for entry in fonts_dir.iterdir():
        if entry.is_file() and entry.name.lower().endswith((".ttf", ".otf")):
            fonts.append(entry)
    return sorted(fonts, key=lambda font: font.name)


def _register_font(font_path: Path) -> str | None:
    """Register a single font file and return first family if loaded."""
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id == -1:
        return None

    families = QFontDatabase.applicationFontFamilies(font_id)
    return families[0] if families else None


def _apply_stylesheet(application: QApplication, correlation_id: str) -> bool:
    """Apply QSS stylesheet from package assets."""
    stylesheet_file = _ASSETS_DIR / "theme" / "app.qss"
    if not stylesheet_file.exists():
        LOGGER.warning(
            "event=ui_stylesheet_missing correlation_id=%s course_id=- module_id=- llm_call_id=-",
            correlation_id,
        )
        return False

    style_sheet = stylesheet_file.read_text(encoding="utf-8")
    application.setStyleSheet(style_sheet)
    return True
