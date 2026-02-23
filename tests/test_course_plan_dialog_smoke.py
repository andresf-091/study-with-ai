"""Headless UI smoke tests for course plan review/edit dialog."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton, QTableWidget

from praktikum_app.application.course_decomposition import (
    ParseCourseCommand,
    ParseCourseResult,
    SaveCoursePlanCommand,
    SaveCoursePlanResult,
)
from praktikum_app.domain.course_plan import (
    CoursePlanCourse,
    CoursePlanDeadline,
    CoursePlanModule,
    CoursePlanV1,
)
from praktikum_app.presentation.qt.course_plan_dialog import CoursePlanDialog


@dataclass
class FakeParseUseCase:
    """Fake parse use-case for deterministic dialog tests."""

    result_plan: CoursePlanV1

    def __post_init__(self) -> None:
        self.calls: list[ParseCourseCommand] = []

    def execute(self, command: ParseCourseCommand) -> ParseCourseResult:
        self.calls.append(command)
        return ParseCourseResult(
            course_id=command.course_id,
            raw_text_id="raw-1",
            plan=self.result_plan,
            llm_call_id="llm-call-1",
            attempts=1,
        )


@dataclass
class FakeSaveUseCase:
    """Fake save use-case that captures plans passed from UI."""

    def __post_init__(self) -> None:
        self.commands: list[SaveCoursePlanCommand] = []

    def execute(self, command: SaveCoursePlanCommand) -> SaveCoursePlanResult:
        self.commands.append(command)
        return SaveCoursePlanResult(
            course_id=command.course_id,
            modules_count=len(command.plan.modules),
            deadlines_count=len(command.plan.deadlines),
        )


@dataclass
class FakeGetUseCase:
    """Fake loader for pre-existing plan data."""

    plan: CoursePlanV1 | None

    def execute(self, course_id: str) -> CoursePlanV1 | None:  # noqa: ARG002
        return self.plan


def test_course_plan_dialog_loads_existing_plan_and_saves_edited_values(
    application: QApplication,
) -> None:
    existing_plan = _build_plan()
    parse_use_case = FakeParseUseCase(result_plan=existing_plan)
    save_use_case = FakeSaveUseCase()
    get_use_case = FakeGetUseCase(plan=existing_plan)

    dialog = CoursePlanDialog(
        course_id="course-1",
        parse_use_case=parse_use_case,
        save_use_case=save_use_case,
        get_use_case=get_use_case,
    )

    title_input = dialog.findChild(QLineEdit, "coursePlanTitleInput")
    save_button = dialog.findChild(QPushButton, "saveCoursePlanButton")
    modules_table = dialog.findChild(QTableWidget, "coursePlanModulesTable")
    assert title_input is not None
    assert save_button is not None
    assert modules_table is not None

    assert title_input.text() == "Курс Python"
    assert modules_table.rowCount() == 1

    title_input.setText("Курс Python обновлён")
    save_button.click()

    assert len(save_use_case.commands) == 1
    saved_plan = save_use_case.commands[0].plan
    assert saved_plan.course.title == "Курс Python обновлён"


def test_course_plan_dialog_generates_plan_via_parse_use_case(application: QApplication) -> None:
    generated_plan = _build_plan()
    parse_use_case = FakeParseUseCase(result_plan=generated_plan)
    save_use_case = FakeSaveUseCase()
    get_use_case = FakeGetUseCase(plan=None)

    dialog = CoursePlanDialog(
        course_id="course-1",
        parse_use_case=parse_use_case,
        save_use_case=save_use_case,
        get_use_case=get_use_case,
    )

    generate_button = dialog.findChild(QPushButton, "generateCoursePlanButton")
    modules_table = dialog.findChild(QTableWidget, "coursePlanModulesTable")
    deadlines_table = dialog.findChild(QTableWidget, "coursePlanDeadlinesTable")
    assert generate_button is not None
    assert modules_table is not None
    assert deadlines_table is not None

    generate_button.click()

    assert len(parse_use_case.calls) == 1
    assert modules_table.rowCount() == 1
    assert deadlines_table.rowCount() == 1


def _build_plan() -> CoursePlanV1:
    return CoursePlanV1(
        course=CoursePlanCourse(
            title="Курс Python",
            description="Описание курса",
            start_date=None,
        ),
        modules=[
            CoursePlanModule(
                order=1,
                title="Основы",
                goals=["Синтаксис"],
                topics=["Переменные"],
                estimated_hours=5,
            )
        ],
        deadlines=[
            CoursePlanDeadline(
                order=1,
                module_ref=1,
                due_at=datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
                kind="домашнее задание",
                notes="Сдать до обеда",
            )
        ],
    )
