"""Composite PDF extraction strategy with fallback selection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from praktikum_app.infrastructure.pdf.extractors import (
    ExtractedPdfContent,
    TextExtractor,
)
from praktikum_app.infrastructure.pdf.quality import (
    PdfExtractionQuality,
    evaluate_pdf_extraction_quality,
)


@dataclass(frozen=True)
class CompositePdfExtractionResult:
    """Selected extraction and decision metadata."""

    selected: ExtractedPdfContent
    selected_quality: PdfExtractionQuality
    used_fallback: bool


class CompositePdfExtractor:
    """Orchestrate primary/fallback extractors using quality heuristics."""

    def __init__(self, primary: TextExtractor, fallback: TextExtractor) -> None:
        self._primary = primary
        self._fallback = fallback

    def extract(self, pdf_path: Path) -> CompositePdfExtractionResult:
        primary_result = self._primary.extract(pdf_path)
        primary_quality = evaluate_pdf_extraction_quality(
            text=primary_result.text,
            page_count=primary_result.page_count,
        )

        if not _should_try_fallback(primary_quality):
            return CompositePdfExtractionResult(
                selected=primary_result,
                selected_quality=primary_quality,
                used_fallback=False,
            )

        fallback_result = self._fallback.extract(pdf_path)
        fallback_quality = evaluate_pdf_extraction_quality(
            text=fallback_result.text,
            page_count=fallback_result.page_count,
        )
        if _prefer_fallback(primary_quality, fallback_quality):
            return CompositePdfExtractionResult(
                selected=fallback_result,
                selected_quality=fallback_quality,
                used_fallback=True,
            )

        return CompositePdfExtractionResult(
            selected=primary_result,
            selected_quality=primary_quality,
            used_fallback=False,
        )


def _should_try_fallback(quality: PdfExtractionQuality) -> bool:
    return quality.is_empty or quality.low_text_density or quality.high_garbage_ratio


def _prefer_fallback(
    primary_quality: PdfExtractionQuality,
    fallback_quality: PdfExtractionQuality,
) -> bool:
    if fallback_quality.is_empty:
        return False
    if primary_quality.is_empty:
        return True
    return fallback_quality.score > primary_quality.score * 1.1
