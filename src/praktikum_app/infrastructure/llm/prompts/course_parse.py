"""Prompt governance spec for course decomposition into CoursePlan v1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel

from praktikum_app.domain.course_plan import CoursePlanV1

TSchema = TypeVar("TSchema", bound=BaseModel)


@dataclass(frozen=True)
class PromptSpec(Generic[TSchema]):
    """Governed prompt definition with schema and version metadata."""

    prompt_id: str
    purpose: str
    version: str
    system_prompt: str
    expected_schema: type[TSchema]


COURSE_PARSE_PROMPT = PromptSpec[CoursePlanV1](
    prompt_id="course_parse",
    purpose=(
        "Преобразовать импортированный текст курса в структурированный CoursePlan v1 "
        "для ревью и последующего сохранения."
    ),
    version="v1",
    system_prompt=(
        "Ты парсер учебного курса. Верни только валидный JSON по схеме CoursePlan v1. "
        "Не добавляй markdown, комментарии и дополнительные поля."
    ),
    expected_schema=CoursePlanV1,
)


def build_course_parse_user_prompt(raw_course_text: str) -> str:
    """Build first-pass parsing prompt using imported raw text."""
    return (
        "Разбери текст курса и верни структуру CoursePlan v1.\n"
        "Требования:\n"
        "- module.order и deadline.order начинаются с 1 и уникальны;\n"
        "- deadline.module_ref должен ссылаться на module.order;\n"
        "- estimated_hours > 0;\n"
        "- если даты не определены явно, используй null.\n\n"
        "Текст курса:\n"
        f"{raw_course_text}"
    )


def build_course_parse_repair_prompt(
    *,
    invalid_output: str,
    validation_errors: str,
) -> str:
    """Build explicit repair prompt for invalid JSON/schema output."""
    return (
        "Исправь предыдущий ответ и верни только валидный JSON по CoursePlan v1.\n"
        "Нельзя добавлять пояснения вне JSON.\n\n"
        "Ошибки валидации:\n"
        f"{validation_errors}\n\n"
        "Невалидный ответ:\n"
        f"{invalid_output}"
    )
