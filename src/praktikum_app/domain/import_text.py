"""Domain models for text-based course import."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class CourseSourceType(StrEnum):
    """Supported source types for text import flow."""

    TEXT_FILE = "text_file"
    PASTE = "paste"
    PDF = "pdf"


@dataclass(frozen=True)
class CourseSource:
    """Metadata about where imported course text came from."""

    source_type: CourseSourceType
    filename: str | None
    imported_at: datetime
    page_count: int | None = None
    extraction_strategy: str | None = None
    likely_scanned: bool = False


@dataclass(frozen=True)
class RawCourseText:
    """Normalized imported text and deterministic metadata."""

    content: str
    content_hash: str
    length: int
    source: CourseSource
