"""Application use-case for PDF import flow."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from praktikum_app.application.text_normalizer import normalize_course_text
from praktikum_app.domain.import_text import CourseSource, CourseSourceType, RawCourseText
from praktikum_app.infrastructure.pdf.composite import (
    CompositePdfExtractor,
)
from praktikum_app.infrastructure.pdf.extractors import PdfMinerExtractor, PyPdfExtractor

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImportCoursePdfCommand:
    """Input contract for importing a PDF file."""

    pdf_path: str
    imported_at: datetime | None = None


@dataclass(frozen=True)
class ImportCoursePdfResult:
    """PDF import result with quality metadata."""

    raw_text: RawCourseText
    likely_scanned: bool
    extraction_strategy: str
    page_count: int
    used_fallback: bool


class ImportCoursePdfUseCase:
    """Extract PDF text with fallback and convert to import domain model."""

    def __init__(self, extractor: CompositePdfExtractor | None = None) -> None:
        self._extractor = extractor or CompositePdfExtractor(
            primary=PyPdfExtractor(),
            fallback=PdfMinerExtractor(),
        )

    def execute(self, command: ImportCoursePdfCommand) -> ImportCoursePdfResult:
        """Import PDF file and return normalized text with metadata."""
        pdf_path = Path(command.pdf_path)
        _validate_pdf_path(pdf_path)

        try:
            extraction_result = self._extractor.extract(pdf_path)
        except Exception as exc:
            raise ValueError("Could not read PDF file.") from exc

        normalized_content = normalize_course_text(extraction_result.selected.text)
        if not normalized_content:
            raise ValueError("PDF contains no extractable text.")

        imported_at = command.imported_at or datetime.now(tz=UTC)
        content_hash = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()

        source = CourseSource(
            source_type=CourseSourceType.PDF,
            filename=pdf_path.name,
            imported_at=imported_at,
            page_count=extraction_result.selected.page_count,
            extraction_strategy=extraction_result.selected.strategy,
            likely_scanned=extraction_result.selected_quality.likely_scanned,
        )
        raw_text = RawCourseText(
            content=normalized_content,
            content_hash=content_hash,
            length=len(normalized_content),
            source=source,
        )

        result = ImportCoursePdfResult(
            raw_text=raw_text,
            likely_scanned=extraction_result.selected_quality.likely_scanned,
            extraction_strategy=extraction_result.selected.strategy,
            page_count=extraction_result.selected.page_count,
            used_fallback=extraction_result.used_fallback,
        )
        _log_pdf_import_success(result=result)
        return result


def _validate_pdf_path(pdf_path: Path) -> None:
    if not pdf_path.exists() or not pdf_path.is_file():
        raise ValueError("PDF file does not exist.")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Unsupported file type. Choose .pdf.")


def _log_pdf_import_success(result: ImportCoursePdfResult) -> None:
    correlation_id = str(uuid4())
    LOGGER.info(
        (
            "event=import_pdf_completed correlation_id=%s course_id=- module_id=- llm_call_id=- "
            "source_type=%s extraction_strategy=%s page_count=%s "
            "used_fallback=%s likely_scanned=%s content_hash=%s length=%s"
        ),
        correlation_id,
        result.raw_text.source.source_type.value,
        result.extraction_strategy,
        result.page_count,
        result.used_fallback,
        result.likely_scanned,
        result.raw_text.content_hash,
        result.raw_text.length,
    )
