"""Utilities for building lightweight runtime PDF fixtures."""

from __future__ import annotations

from pathlib import Path


def write_simple_text_pdf(path: Path, text: str) -> None:
    """Write a minimal one-page PDF with plain text content."""
    escaped_text = (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )
    stream = f"BT /F1 14 Tf 72 720 Td ({escaped_text}) Tj ET".encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf_parts: list[bytes] = [b"%PDF-1.4\n"]
    offsets: list[int] = []

    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(part) for part in pdf_parts))
        pdf_parts.append(f"{index} 0 obj\n".encode("ascii"))
        pdf_parts.append(obj + b"\n")
        pdf_parts.append(b"endobj\n")

    xref_offset = sum(len(part) for part in pdf_parts)
    pdf_parts.append(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf_parts.append(b"0000000000 65535 f \n")
    for offset in offsets:
        pdf_parts.append(f"{offset:010d} 00000 n \n".encode("ascii"))

    pdf_parts.append(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("ascii"))
    pdf_parts.append(f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii"))

    path.write_bytes(b"".join(pdf_parts))
