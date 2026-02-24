"""Headless smoke tests for practice generation dialog UI flow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
)

from praktikum_app.application.practice_generation import (
    GeneratePracticeCommand,
    GeneratePracticeResult,
    PracticeModuleSummary,
    PracticeTaskState,
)
from praktikum_app.domain.practice import PracticeDifficulty, PracticeTask
from praktikum_app.presentation.qt.practice_dialog import PracticeDialog


@dataclass
class InMemoryPracticeBackend:
    """Shared fake backend for dialog smoke tests."""

    modules: list[PracticeModuleSummary]
    history_by_module: dict[str, list[PracticeTask]] = field(default_factory=dict)
    generate_calls: list[GeneratePracticeCommand] = field(default_factory=list)

    def generate(self, command: GeneratePracticeCommand) -> GeneratePracticeResult:
        self.generate_calls.append(command)
        history = self.history_by_module.setdefault(command.module_id, [])
        generation_number = len(self.generate_calls)
        created_at = datetime(2026, 3, 5, 10, 0, tzinfo=UTC) + timedelta(minutes=generation_number)

        batch: list[PracticeTask] = []
        for index in range(1, command.candidate_count + 1):
            batch.append(
                PracticeTask(
                    id=f"task-{generation_number}-{index}",
                    course_id="course-1",
                    module_id=command.module_id,
                    difficulty=command.difficulty,
                    statement=f"Практика {generation_number}.{index}",
                    expected_outline=f"План {generation_number}.{index}",
                    candidate_index=index,
                    created_at=created_at,
                    generation_id=f"generation-{generation_number}",
                    llm_call_id=f"llm-{generation_number}",
                )
            )

        history.extend(batch)
        current_task = batch[0]
        return GeneratePracticeResult(
            course_id="course-1",
            module_id=command.module_id,
            generated_count=len(batch),
            history_count=len(history),
            current_task=current_task,
            llm_call_id=current_task.llm_call_id,
            attempts=1,
        )

    def list_modules(self, course_id: str) -> list[PracticeModuleSummary]:  # noqa: ARG002
        return self.modules

    def state(self, module_id: str) -> PracticeTaskState:
        history = self.history_by_module.get(module_id, [])
        if not history:
            return PracticeTaskState(current_task=None, history=[])

        latest_generation = history[-1].generation_id
        current_batch = [task for task in history if task.generation_id == latest_generation]
        current_batch.sort(key=lambda task: task.candidate_index)
        return PracticeTaskState(
            current_task=current_batch[0],
            history=list(reversed(history)),
        )


@dataclass
class FakeGenerateUseCase:
    backend: InMemoryPracticeBackend

    def execute(self, command: GeneratePracticeCommand) -> GeneratePracticeResult:
        return self.backend.generate(command)


@dataclass
class FakeListModulesUseCase:
    backend: InMemoryPracticeBackend

    def execute(self, course_id: str) -> list[PracticeModuleSummary]:
        return self.backend.list_modules(course_id)


@dataclass
class FakeStateUseCase:
    backend: InMemoryPracticeBackend

    def execute(self, module_id: str) -> PracticeTaskState:
        return self.backend.state(module_id)


def test_practice_dialog_generates_and_regenerates_with_history(
    application: QApplication,
) -> None:
    backend = InMemoryPracticeBackend(
        modules=[
            PracticeModuleSummary(
                module_id="module-1",
                course_id="course-1",
                module_order=1,
                module_title="Асинхронность",
            )
        ]
    )
    dialog = PracticeDialog(
        course_id="course-1",
        generate_use_case=FakeGenerateUseCase(backend),
        list_modules_use_case=FakeListModulesUseCase(backend),
        state_use_case=FakeStateUseCase(backend),
    )

    module_combo = dialog.findChild(QComboBox, "practiceModuleCombo")
    generate_button = dialog.findChild(QPushButton, "generatePracticeButton")
    regenerate_button = dialog.findChild(QPushButton, "regeneratePracticeButton")
    history_list = dialog.findChild(QListWidget, "practiceHistoryList")
    statement_preview = dialog.findChild(QPlainTextEdit, "practiceStatementPreview")
    assert module_combo is not None
    assert generate_button is not None
    assert regenerate_button is not None
    assert history_list is not None
    assert statement_preview is not None

    assert module_combo.count() == 1

    generate_button.click()
    assert len(backend.generate_calls) == 1
    assert backend.generate_calls[0].difficulty is PracticeDifficulty.MEDIUM
    assert history_list.count() == 3
    assert "Практика 1.1" in statement_preview.toPlainText()

    regenerate_button.click()
    assert len(backend.generate_calls) == 2
    assert history_list.count() == 6
    assert "Практика 2.1" in statement_preview.toPlainText()


def test_practice_dialog_shows_empty_modules_state(application: QApplication) -> None:
    backend = InMemoryPracticeBackend(modules=[])
    dialog = PracticeDialog(
        course_id="course-1",
        generate_use_case=FakeGenerateUseCase(backend),
        list_modules_use_case=FakeListModulesUseCase(backend),
        state_use_case=FakeStateUseCase(backend),
    )

    status_label = dialog.findChild(QLabel, "practiceStatusLabel")
    generate_button = dialog.findChild(QPushButton, "generatePracticeButton")
    regenerate_button = dialog.findChild(QPushButton, "regeneratePracticeButton")
    module_combo = dialog.findChild(QComboBox, "practiceModuleCombo")
    assert status_label is not None
    assert generate_button is not None
    assert regenerate_button is not None
    assert module_combo is not None

    assert "Сначала сформируйте и сохраните план курса" in status_label.text()
    assert module_combo.isEnabled() is False
    assert generate_button.isEnabled() is False
    assert regenerate_button.isEnabled() is False
