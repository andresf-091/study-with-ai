"""Unit tests for PDF extraction strategies, quality, and use-case."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from praktikum_app.application.import_pdf_use_case import (
    ImportCoursePdfCommand,
    ImportCoursePdfUseCase,
)
from praktikum_app.domain.import_text import CourseSourceType
from praktikum_app.infrastructure.pdf.composite import CompositePdfExtractor
from praktikum_app.infrastructure.pdf.extractors import (
    ExtractedPdfContent,
    PdfMinerExtractor,
    PyPdfExtractor,
)
from praktikum_app.infrastructure.pdf.quality import evaluate_pdf_extraction_quality
from tests.pdf_fixture_utils import write_simple_text_pdf


def test_pypdf_extractor_reads_text_from_fixture() -> None:
    runtime_pdf = Path("tests") / f"_runtime_pypdf_{uuid4().hex}.pdf"
    write_simple_text_pdf(runtime_pdf, "Hello PDF Import")
    try:
        extracted = PyPdfExtractor().extract(runtime_pdf)
        assert "Hello PDF Import" in extracted.text
        assert extracted.page_count == 1
        assert extracted.strategy == "pypdf"
    finally:
        runtime_pdf.unlink(missing_ok=True)


def test_pdfminer_extractor_reads_text_from_fixture() -> None:
    runtime_pdf = Path("tests") / f"_runtime_pdfminer_{uuid4().hex}.pdf"
    write_simple_text_pdf(runtime_pdf, "Fallback capable text")
    try:
        extracted = PdfMinerExtractor().extract(runtime_pdf)
        assert "Fallback capable text" in extracted.text
        assert extracted.page_count == 1
        assert extracted.strategy == "pdfminer"
    finally:
        runtime_pdf.unlink(missing_ok=True)


def test_quality_heuristics_marks_low_text_as_scan_like() -> None:
    quality = evaluate_pdf_extraction_quality(text="x", page_count=1)
    assert quality.likely_scanned is True
    assert quality.low_text_density is True


def test_composite_extractor_uses_fallback_for_low_quality_primary() -> None:
    class FakePrimary:
        strategy_name = "pypdf"

        def extract(self, pdf_path: Path) -> ExtractedPdfContent:
            return ExtractedPdfContent(text="x", page_count=1, strategy=self.strategy_name)

    class FakeFallback:
        strategy_name = "pdfminer"

        def extract(self, pdf_path: Path) -> ExtractedPdfContent:
            return ExtractedPdfContent(
                text=(
                    "This is a complete extracted lesson plan with substantial details "
                    "covering objectives, milestones, assignments, and deadlines."
                ),
                page_count=1,
                strategy=self.strategy_name,
            )

    composite = CompositePdfExtractor(primary=FakePrimary(), fallback=FakeFallback())
    result = composite.extract(Path("dummy.pdf"))

    assert result.used_fallback is True
    assert result.selected.strategy == "pdfminer"
    assert result.selected_quality.score > 0


def test_import_pdf_use_case_returns_raw_course_text_with_metadata() -> None:
    runtime_pdf = Path("tests") / f"_runtime_use_case_{uuid4().hex}.pdf"
    write_simple_text_pdf(runtime_pdf, "Syllabus module content")
    try:
        use_case = ImportCoursePdfUseCase()
        result = use_case.execute(ImportCoursePdfCommand(pdf_path=str(runtime_pdf)))

        assert result.raw_text.source.source_type is CourseSourceType.PDF
        assert result.raw_text.source.filename == runtime_pdf.name
        assert result.page_count == 1
        assert result.extraction_strategy in {"pypdf", "pdfminer"}
        assert result.raw_text.length > 0
    finally:
        runtime_pdf.unlink(missing_ok=True)


def test_import_pdf_use_case_rejects_non_pdf_file() -> None:
    runtime_text = Path("tests") / f"_runtime_not_pdf_{uuid4().hex}.txt"
    runtime_text.write_text("not a pdf", encoding="utf-8")
    try:
        use_case = ImportCoursePdfUseCase()
        with pytest.raises(ValueError, match="Неподдерживаемый тип файла"):
            use_case.execute(ImportCoursePdfCommand(pdf_path=str(runtime_text)))
    finally:
        runtime_text.unlink(missing_ok=True)
