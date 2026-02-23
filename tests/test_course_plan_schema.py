"""Unit tests for CoursePlan v1 schema validators."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from praktikum_app.domain.course_plan import (
    CoursePlanCourse,
    CoursePlanDeadline,
    CoursePlanModule,
    CoursePlanV1,
)


def test_course_plan_schema_accepts_valid_payload() -> None:
    plan = CoursePlanV1(
        course=CoursePlanCourse(
            title="Python Basics",
            description="Introductory course",
            start_date=None,
        ),
        modules=[
            CoursePlanModule(
                order=1,
                title="Module 1",
                goals=["Understand syntax"],
                topics=["Variables", "Types"],
                estimated_hours=4,
            ),
            CoursePlanModule(
                order=2,
                title="Module 2",
                goals=["Practice control flow"],
                topics=["if", "for"],
                estimated_hours=3,
            ),
        ],
        deadlines=[
            CoursePlanDeadline(
                order=1,
                module_ref=2,
                due_at=datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
                kind="домашнее задание",
                notes="Сдать до полудня",
            )
        ],
    )

    assert plan.schema_version == "v1"
    assert len(plan.modules) == 2
    assert len(plan.deadlines) == 1


def test_course_plan_schema_rejects_duplicate_module_order() -> None:
    with pytest.raises(ValidationError, match="Module order values must be unique"):
        CoursePlanV1(
            course=CoursePlanCourse(title="T", description="D"),
            modules=[
                CoursePlanModule(
                    order=1,
                    title="Module 1",
                    goals=[],
                    topics=[],
                    estimated_hours=1,
                ),
                CoursePlanModule(
                    order=1,
                    title="Module 2",
                    goals=[],
                    topics=[],
                    estimated_hours=1,
                ),
            ],
            deadlines=[],
        )


def test_course_plan_schema_rejects_unknown_deadline_module_ref() -> None:
    with pytest.raises(ValidationError, match="references unknown module_ref"):
        CoursePlanV1(
            course=CoursePlanCourse(title="T", description="D"),
            modules=[
                CoursePlanModule(
                    order=1,
                    title="Module 1",
                    goals=[],
                    topics=[],
                    estimated_hours=1,
                )
            ],
            deadlines=[
                CoursePlanDeadline(
                    order=1,
                    module_ref=2,
                    due_at=None,
                    kind="экзамен",
                    notes=None,
                )
            ],
        )
