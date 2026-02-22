"""Quality heuristics for extracted PDF text."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PdfExtractionQuality:
    """Heuristic quality assessment for extracted PDF text."""

    score: float
    text_length: int
    garbage_ratio: float
    is_empty: bool
    low_text_density: bool
    high_garbage_ratio: bool
    likely_scanned: bool


def evaluate_pdf_extraction_quality(text: str, page_count: int) -> PdfExtractionQuality:
    """Evaluate extraction quality using lightweight deterministic heuristics."""
    stripped = text.strip()
    text_length = len(stripped)
    is_empty = text_length == 0

    non_whitespace = [char for char in stripped if not char.isspace()]
    total_non_whitespace = len(non_whitespace)
    garbage_count = sum(
        1
        for char in non_whitespace
        if (not char.isprintable()) or char == "\ufffd"
    )
    garbage_ratio = (
        garbage_count / total_non_whitespace
        if total_non_whitespace > 0
        else 1.0
    )

    pages = max(page_count, 1)
    characters_per_page = text_length / pages
    low_text_density = characters_per_page < 60
    high_garbage_ratio = garbage_ratio > 0.2
    likely_scanned = is_empty or low_text_density

    penalty = garbage_ratio * 100
    score = max(text_length - penalty, 0.0)
    if is_empty:
        score = 0.0

    return PdfExtractionQuality(
        score=score,
        text_length=text_length,
        garbage_ratio=garbage_ratio,
        is_empty=is_empty,
        low_text_density=low_text_density,
        high_garbage_ratio=high_garbage_ratio,
        likely_scanned=likely_scanned,
    )
