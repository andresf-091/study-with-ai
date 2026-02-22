"""Application use-case for text import flow."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from praktikum_app.application.text_normalizer import normalize_course_text
from praktikum_app.domain.import_text import CourseSource, CourseSourceType, RawCourseText

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImportCourseTextCommand:
    """Input contract for importing text from file or paste."""

    source_type: CourseSourceType
    content: str
    filename: str | None = None
    imported_at: datetime | None = None


class ImportCourseTextUseCase:
    """Normalize imported text and produce deterministic metadata."""

    def execute(self, command: ImportCourseTextCommand) -> RawCourseText:
        """Process raw source text and return normalized domain object."""
        self._validate(command)
        normalized_content = normalize_course_text(command.content)
        if not normalized_content:
            raise ValueError("Imported text is empty after normalization.")

        imported_at = command.imported_at or datetime.now(tz=UTC)
        content_hash = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()

        source = CourseSource(
            source_type=command.source_type,
            filename=command.filename,
            imported_at=imported_at,
        )
        result = RawCourseText(
            content=normalized_content,
            content_hash=content_hash,
            length=len(normalized_content),
            source=source,
        )
        correlation_id = str(uuid4())
        LOGGER.info(
            (
                "event=import_text_completed correlation_id=%s "
                "course_id=- module_id=- llm_call_id=- "
                "source_type=%s content_hash=%s length=%s"
            ),
            correlation_id,
            result.source.source_type.value,
            result.content_hash,
            result.length,
        )
        return result

    def _validate(self, command: ImportCourseTextCommand) -> None:
        if command.source_type is CourseSourceType.TEXT_FILE and not command.filename:
            raise ValueError("Filename is required for text file import.")
