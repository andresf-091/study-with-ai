"""Domain contracts for generated practice tasks and LLM response schema."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PracticeDifficulty(StrEnum):
    """Supported difficulty levels for generated practice."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass(frozen=True)
class PracticeTask:
    """Persisted practice task candidate bound to one module."""

    id: str
    course_id: str
    module_id: str
    difficulty: PracticeDifficulty
    statement: str
    expected_outline: str
    candidate_index: int
    created_at: datetime
    generation_id: str
    llm_call_id: str


class PracticeGenerationCandidateV1(BaseModel):
    """One candidate returned by LLM practice generation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    statement: str = Field(min_length=1, max_length=8000)
    expected_outline: str = Field(min_length=1, max_length=4000)


class PracticeGenerationV1(BaseModel):
    """Strict schema for LLM practice generation payload."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    module_title: str = Field(min_length=1, max_length=255)
    difficulty: PracticeDifficulty
    candidates: list[PracticeGenerationCandidateV1] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def validate_candidates_are_distinct(self) -> PracticeGenerationV1:
        normalized_statements = {
            candidate.statement.casefold().strip() for candidate in self.candidates
        }
        if len(normalized_statements) != len(self.candidates):
            raise ValueError("Practice candidates must be distinct by statement.")

        return self
