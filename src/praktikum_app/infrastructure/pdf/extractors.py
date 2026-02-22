"""Primary/fallback extractors for PDF text."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pdfminer.high_level import extract_text as pdfminer_extract_text
from pdfminer.pdfpage import PDFPage
from pypdf import PdfReader


@dataclass(frozen=True)
class ExtractedPdfContent:
    """Extracted text plus extraction metadata."""

    text: str
    page_count: int
    strategy: str


class TextExtractor(Protocol):
    """Protocol for PDF text extractors."""

    strategy_name: str

    def extract(self, pdf_path: Path) -> ExtractedPdfContent:
        """Extract text from PDF path."""
        ...


class PyPdfExtractor:
    """Primary extractor using pypdf."""

    strategy_name = "pypdf"

    def extract(self, pdf_path: Path) -> ExtractedPdfContent:
        reader = PdfReader(str(pdf_path))
        page_count = len(reader.pages)
        chunks: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            chunks.append(page_text)
        text = "\n\n".join(chunks).strip()
        return ExtractedPdfContent(
            text=text,
            page_count=page_count,
            strategy=self.strategy_name,
        )


class PdfMinerExtractor:
    """Fallback extractor using pdfminer.six."""

    strategy_name = "pdfminer"

    def extract(self, pdf_path: Path) -> ExtractedPdfContent:
        text = pdfminer_extract_text(str(pdf_path)).strip()
        page_count = _count_pages(pdf_path)
        return ExtractedPdfContent(
            text=text,
            page_count=page_count,
            strategy=self.strategy_name,
        )


def _count_pages(pdf_path: Path) -> int:
    with pdf_path.open("rb") as handle:
        return sum(1 for _ in PDFPage.get_pages(handle))
