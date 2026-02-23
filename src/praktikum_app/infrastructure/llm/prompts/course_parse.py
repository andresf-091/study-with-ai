"""Prompt specification and schema for course parsing use-case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

TSchema = TypeVar("TSchema", bound=BaseModel)


@dataclass(frozen=True)
class PromptSpec(Generic[TSchema]):
    """Governed prompt definition with schema and version metadata."""

    prompt_id: str
    purpose: str
    version: str
    system_prompt: str
    expected_schema: type[TSchema]


class CourseParseModuleSchema(BaseModel):
    """Schema for one parsed module in course decomposition output."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)


class CourseParseSchema(BaseModel):
    """Structured output schema for initial course parsing."""

    model_config = ConfigDict(extra="forbid")

    course_title: str = Field(min_length=1)
    modules: list[CourseParseModuleSchema]


COURSE_PARSE_PROMPT = PromptSpec[CourseParseSchema](
    prompt_id="course_parse",
    purpose="Convert imported course text into JSON with course title and module stubs.",
    version="v1",
    system_prompt=(
        "You are a strict parser. Return only JSON that matches the expected schema. "
        "Do not add markdown, explanations, or extra keys."
    ),
    expected_schema=CourseParseSchema,
)


def build_course_parse_user_prompt(raw_course_text: str) -> str:
    """Compose user prompt payload for course parsing."""
    return (
        "Parse the following course text into JSON by the required schema.\n"
        "Keep module summaries concise.\n\n"
        f"{raw_course_text}"
    )
