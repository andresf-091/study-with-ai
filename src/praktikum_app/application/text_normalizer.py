"""Text normalization helpers for course import."""

from __future__ import annotations

import re

_MULTISPACE_PATTERN = re.compile(r"[ \t]+")
_BULLET_PATTERN = re.compile(r"^([*\-•●◦▪▫‣⁃–—]+)\s*")


def normalize_course_text(raw_text: str) -> str:
    """Normalize raw text without changing semantic meaning."""
    normalized_newlines = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    input_lines = normalized_newlines.split("\n")

    result_lines: list[str] = []
    previous_empty = False

    for line in input_lines:
        stripped = line.strip()
        if not stripped:
            if result_lines and not previous_empty:
                result_lines.append("")
            previous_empty = True
            continue

        previous_empty = False
        compact = _MULTISPACE_PATTERN.sub(" ", stripped)
        compact = _BULLET_PATTERN.sub("- ", compact, count=1)
        result_lines.append(compact)

    while result_lines and result_lines[0] == "":
        result_lines.pop(0)
    while result_lines and result_lines[-1] == "":
        result_lines.pop()

    return "\n".join(result_lines)
