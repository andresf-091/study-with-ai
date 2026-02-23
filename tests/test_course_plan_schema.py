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


def test_course_plan_schema_accepts_deadline_description_alias() -> None:
    payload = {
        "course": {
            "title": "Python Basics",
            "description": "Introductory course",
        },
        "modules": [
            {
                "order": 1,
                "title": "Module 1",
                "estimated_hours": 4,
            }
        ],
        "deadlines": [
            {
                "order": 1,
                "module_ref": 1,
                "kind": "project",
                "description": "Сдать до пятницы",
            }
        ],
    }

    plan = CoursePlanV1.model_validate(payload)

    assert len(plan.deadlines) == 1
    assert plan.deadlines[0].notes == "Сдать до пятницы"

def test_course_plan_schema_accepts_legacy_payload_shape() -> None:
    payload = {
        "course_name": "Practicum PRO: Middle Python",
        "modules": [
            {
                "order": 1,
                "title": "Onboarding",
                "estimated_hours": 20,
            }
        ],
        "deadlines": [
            {
                "order": 1,
                "module_ref": 1,
                "description_short": "Approve diploma project",
                "date": None,
                "notes": "Onboarding takes 4-8 weeks.",
            }
        ],
    }

    plan = CoursePlanV1.model_validate(payload)

    assert plan.course.title == "Practicum PRO: Middle Python"
    assert plan.course.description == "Practicum PRO: Middle Python"
    assert len(plan.deadlines) == 1
    assert plan.deadlines[0].kind == "deadline"
    assert plan.deadlines[0].notes == "Onboarding takes 4-8 weeks."


def test_course_plan_schema_accepts_module_description_alias() -> None:
    payload = {
        "course": {
            "title": "Python Basics",
            "description": "Introductory course",
        },
        "modules": [
            {
                "order": 1,
                "title": "Module 1",
                "description": "Legacy module description",
                "estimated_hours": 4,
            }
        ],
        "deadlines": [],
    }

    plan = CoursePlanV1.model_validate(payload)

    assert len(plan.modules) == 1
    assert plan.modules[0].goals == ["Legacy module description"]
