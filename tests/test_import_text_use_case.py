"""Unit tests for ImportCourseTextUseCase."""

from __future__ import annotations

import hashlib

import pytest

from praktikum_app.application.import_text_use_case import (
    ImportCourseTextCommand,
    ImportCourseTextUseCase,
)
from praktikum_app.domain.import_text import CourseSourceType


def test_import_use_case_returns_normalized_result_with_metadata() -> None:
    use_case = ImportCourseTextUseCase()
    command = ImportCourseTextCommand(
        source_type=CourseSourceType.PASTE,
        content="  • Lesson one  \n\n",
        filename=None,
    )

    result = use_case.execute(command)

    assert result.content == "- Lesson one"
    assert result.length == len("- Lesson one")
    assert result.source.source_type is CourseSourceType.PASTE
    assert result.source.filename is None
    assert result.content_hash == hashlib.sha256(b"- Lesson one").hexdigest()


def test_import_use_case_requires_filename_for_text_file_source() -> None:
    use_case = ImportCourseTextUseCase()
    command = ImportCourseTextCommand(
        source_type=CourseSourceType.TEXT_FILE,
        content="Module text",
        filename=None,
    )

    with pytest.raises(ValueError, match="Filename is required"):
        use_case.execute(command)


def test_import_use_case_rejects_empty_content_after_normalization() -> None:
    use_case = ImportCourseTextUseCase()
    command = ImportCourseTextCommand(
        source_type=CourseSourceType.PASTE,
        content="\n\n\t  \r\n",
    )

    with pytest.raises(ValueError, match="empty after normalization"):
        use_case.execute(command)
