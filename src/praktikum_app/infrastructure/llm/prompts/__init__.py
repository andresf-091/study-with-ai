"""Governed prompt specifications."""

from praktikum_app.infrastructure.llm.prompts.course_parse import (
    COURSE_PARSE_PROMPT,
    CourseParseSchema,
    PromptSpec,
    build_course_parse_user_prompt,
)

__all__ = [
    "COURSE_PARSE_PROMPT",
    "CourseParseSchema",
    "PromptSpec",
    "build_course_parse_user_prompt",
]
