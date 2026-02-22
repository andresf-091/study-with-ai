"""Unit tests for text normalization flow."""

from __future__ import annotations

from praktikum_app.application.text_normalizer import normalize_course_text


def test_normalize_course_text_trims_whitespace_and_unifies_bullets() -> None:
    raw_text = "  •   Introduction \r\n\t--   Install dependencies  \r\n"

    normalized = normalize_course_text(raw_text)

    assert normalized == "- Introduction\n- Install dependencies"


def test_normalize_course_text_collapses_repeated_empty_lines() -> None:
    raw_text = "Course overview\n\n\n\nModule details\n\n\n"

    normalized = normalize_course_text(raw_text)

    assert normalized == "Course overview\n\nModule details"
