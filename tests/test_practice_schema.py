"""Unit tests for PracticeGenerationV1 schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from praktikum_app.domain.practice import (
    PracticeDifficulty,
    PracticeGenerationCandidateV1,
    PracticeGenerationV1,
)


def test_practice_generation_schema_accepts_valid_payload() -> None:
    payload = PracticeGenerationV1(
        module_title="Основы Python",
        difficulty=PracticeDifficulty.MEDIUM,
        candidates=[
            PracticeGenerationCandidateV1(
                statement="Напишите CLI-скрипт для анализа логов.",
                expected_outline="Используйте argparse, функции и обработку ошибок.",
            ),
            PracticeGenerationCandidateV1(
                statement="Реализуйте парсер CSV с фильтрацией.",
                expected_outline="Нужны чтение CSV, фильтр по колонке и unit-тесты.",
            ),
        ],
    )

    assert payload.difficulty is PracticeDifficulty.MEDIUM
    assert len(payload.candidates) == 2


def test_practice_generation_schema_rejects_duplicate_statements() -> None:
    with pytest.raises(ValidationError, match="distinct"):
        PracticeGenerationV1(
            module_title="Основы Python",
            difficulty=PracticeDifficulty.EASY,
            candidates=[
                PracticeGenerationCandidateV1(
                    statement="Сделайте упражнение",
                    expected_outline="Пункт 1",
                ),
                PracticeGenerationCandidateV1(
                    statement="Сделайте упражнение",
                    expected_outline="Пункт 2",
                ),
            ],
        )


def test_practice_generation_schema_requires_non_empty_candidates() -> None:
    with pytest.raises(ValidationError):
        PracticeGenerationV1(
            module_title="Основы Python",
            difficulty=PracticeDifficulty.HARD,
            candidates=[],
        )
