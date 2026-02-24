"""Prompt governance spec for practice generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel

from praktikum_app.domain.practice import PracticeDifficulty, PracticeGenerationV1

TSchema = TypeVar("TSchema", bound=BaseModel)


@dataclass(frozen=True)
class PromptSpec(Generic[TSchema]):
    """Governed prompt definition with schema and version metadata."""

    prompt_id: str
    purpose: str
    version: str
    system_prompt: str
    expected_schema: type[TSchema]


PRACTICE_GENERATION_PROMPT = PromptSpec[PracticeGenerationV1](
    prompt_id="practice_generation",
    purpose=(
        "Сгенерировать несколько кандидатов практических заданий "
        "по выбранному модулю курса."
    ),
    version="v1",
    system_prompt=(
        "Ты создаёшь практические задания для обучения. "
        "Верни только валидный JSON по схеме PracticeGenerationV1. "
        "Не добавляй markdown и комментарии вне JSON."
    ),
    expected_schema=PracticeGenerationV1,
)


def build_practice_generation_user_prompt(
    *,
    course_title: str | None,
    module_title: str,
    module_order: int,
    goals: list[str],
    topics: list[str],
    estimated_hours: int | None,
    difficulty: PracticeDifficulty,
    candidate_count: int,
) -> str:
    """Build first-pass prompt for practice generation."""
    course_title_value = course_title or "Курс"
    goals_text = "\n".join(f"- {goal}" for goal in goals) if goals else "- не указаны"
    topics_text = "\n".join(f"- {topic}" for topic in topics) if topics else "- не указаны"
    hours_text = str(estimated_hours) if estimated_hours is not None else "не указано"

    return (
        "Сгенерируй практические задания по модулю.\n"
        "Требования:\n"
        f"- Верни ровно {candidate_count} кандидатов.\n"
        "- Каждый кандидат должен иметь statement и expected_outline.\n"
        "- Statement должен быть конкретным и выполнимым.\n"
        "- expected_outline должен описывать критерии успешного решения.\n"
        "- Не возвращай ничего вне JSON.\n\n"
        f"Курс: {course_title_value}\n"
        f"Модуль #{module_order}: {module_title}\n"
        f"Сложность: {difficulty.value}\n"
        f"Оценка часов: {hours_text}\n"
        "Цели:\n"
        f"{goals_text}\n"
        "Темы:\n"
        f"{topics_text}"
    )


def build_practice_generation_repair_prompt(
    *,
    invalid_output: str,
    validation_errors: str,
    candidate_count: int,
) -> str:
    """Build explicit repair prompt for invalid JSON/schema output."""
    return (
        "Исправь предыдущий ответ и верни только валидный JSON "
        "по схеме PracticeGenerationV1.\n"
        f"Нужно вернуть ровно {candidate_count} кандидатов.\n"
        "Нельзя добавлять пояснения вне JSON.\n\n"
        "Ошибки валидации:\n"
        f"{validation_errors}\n\n"
        "Невалидный ответ:\n"
        f"{invalid_output}"
    )
