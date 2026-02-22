"""Temporary in-memory store for imported course text.

NOTE:
    This is process-local and intentionally non-persistent.
    Database persistence is planned for PR#5.
"""

from __future__ import annotations

from praktikum_app.domain.import_text import RawCourseText


class InMemoryImportStore:
    """Store the most recent import result for current app process."""

    def __init__(self) -> None:
        self._latest_import: RawCourseText | None = None

    def save(self, imported_text: RawCourseText) -> None:
        """Save latest imported text in process memory."""
        self._latest_import = imported_text

    def get_latest(self) -> RawCourseText | None:
        """Return latest imported text if available."""
        return self._latest_import

    def clear(self) -> None:
        """Clear stored imported text."""
        self._latest_import = None
