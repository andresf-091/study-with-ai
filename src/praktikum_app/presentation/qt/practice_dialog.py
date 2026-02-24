"""Practice generation and regenerate dialog for selected course module."""

from __future__ import annotations

import logging
from typing import Protocol
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from praktikum_app.application.practice_generation import (
    GeneratePracticeCommand,
    GeneratePracticeResult,
    GeneratePracticeUseCase,
    GetPracticeTaskStateUseCase,
    ListPracticeModulesUseCase,
    PracticeModuleSummary,
    PracticeTaskState,
)
from praktikum_app.domain.practice import PracticeDifficulty, PracticeTask

LOGGER = logging.getLogger(__name__)


class GeneratePracticeUseCasePort(Protocol):
    """Port for generate/regenerate action injection in UI tests."""

    def execute(self, command: GeneratePracticeCommand) -> GeneratePracticeResult:
        """Generate and persist practice candidates."""
        ...


class ListPracticeModulesUseCasePort(Protocol):
    """Port for module list loading in practice screen."""

    def execute(self, course_id: str) -> list[PracticeModuleSummary]:
        """Load practice-ready modules for course."""
        ...


class GetPracticeTaskStateUseCasePort(Protocol):
    """Port for loading current task and history state."""

    def execute(self, module_id: str) -> PracticeTaskState:
        """Load current generated task and module history."""
        ...


class PracticeDialog(QDialog):
    """Dialog for generating and regenerating module practice tasks."""

    def __init__(
        self,
        *,
        course_id: str,
        generate_use_case: GeneratePracticeUseCasePort | GeneratePracticeUseCase,
        list_modules_use_case: ListPracticeModulesUseCasePort | ListPracticeModulesUseCase,
        state_use_case: GetPracticeTaskStateUseCasePort | GetPracticeTaskStateUseCase,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._course_id = course_id
        self._generate_use_case = generate_use_case
        self._list_modules_use_case = list_modules_use_case
        self._state_use_case = state_use_case
        self._last_llm_call_id: str | None = None

        self._module_combo = QComboBox(self)
        self._difficulty_combo = QComboBox(self)
        self._candidate_count_spin = QSpinBox(self)
        self._statement_preview = QPlainTextEdit(self)
        self._outline_preview = QPlainTextEdit(self)
        self._answer_input = QPlainTextEdit(self)
        self._history_list = QListWidget(self)
        self._status_label = QLabel(self)
        self._generate_button = QPushButton("Сгенерировать", self)
        self._regenerate_button = QPushButton("Перегенерировать", self)
        self._close_button = QPushButton("Закрыть", self)

        self._build_ui()
        self._load_modules()

    def _build_ui(self) -> None:
        self.setWindowTitle("Практика по модулю")
        self.resize(1080, 760)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 18, 20, 18)
        root_layout.setSpacing(12)

        header_label = QLabel(f"Курс: {self._course_id}", self)
        header_label.setObjectName("practiceCourseIdLabel")
        root_layout.addWidget(header_label)

        controls_layout = QFormLayout()
        controls_layout.setSpacing(8)
        self._module_combo.setObjectName("practiceModuleCombo")
        self._difficulty_combo.setObjectName("practiceDifficultyCombo")
        self._candidate_count_spin.setObjectName("practiceCandidateCountSpin")
        self._candidate_count_spin.setRange(1, 5)
        self._candidate_count_spin.setValue(3)
        self._difficulty_combo.addItem("Лёгкий", PracticeDifficulty.EASY.value)
        self._difficulty_combo.addItem("Средний", PracticeDifficulty.MEDIUM.value)
        self._difficulty_combo.addItem("Сложный", PracticeDifficulty.HARD.value)
        self._difficulty_combo.setCurrentIndex(1)

        controls_layout.addRow("Модуль", self._module_combo)
        controls_layout.addRow("Сложность", self._difficulty_combo)
        controls_layout.addRow("Количество вариантов", self._candidate_count_spin)
        root_layout.addLayout(controls_layout)

        current_task_label = QLabel("Текущее задание", self)
        root_layout.addWidget(current_task_label)
        self._statement_preview.setObjectName("practiceStatementPreview")
        self._statement_preview.setReadOnly(True)
        self._statement_preview.setPlaceholderText("Задание пока не сгенерировано.")
        root_layout.addWidget(self._statement_preview, stretch=2)

        outline_label = QLabel("Ожидаемый план решения", self)
        root_layout.addWidget(outline_label)
        self._outline_preview.setObjectName("practiceOutlinePreview")
        self._outline_preview.setReadOnly(True)
        self._outline_preview.setPlaceholderText("Структура решения появится после генерации.")
        root_layout.addWidget(self._outline_preview, stretch=1)

        answer_label = QLabel("Ваш ответ", self)
        root_layout.addWidget(answer_label)
        self._answer_input.setObjectName("practiceAnswerInput")
        self._answer_input.setPlaceholderText(
            "Введите ваш ответ или код. Проверка ответа появится в следующем этапе."
        )
        root_layout.addWidget(self._answer_input, stretch=2)

        history_label = QLabel("История генераций", self)
        root_layout.addWidget(history_label)
        self._history_list.setObjectName("practiceHistoryList")
        root_layout.addWidget(self._history_list, stretch=2)

        self._status_label.setObjectName("practiceStatusLabel")
        self._status_label.setWordWrap(True)
        self._status_label.setText("Выберите модуль и нажмите «Сгенерировать».")
        root_layout.addWidget(self._status_label)

        actions_layout = QHBoxLayout()
        actions_layout.addWidget(self._generate_button)
        actions_layout.addWidget(self._regenerate_button)
        actions_layout.addStretch(1)
        actions_layout.addWidget(self._close_button)
        root_layout.addLayout(actions_layout)

        self._generate_button.setObjectName("generatePracticeButton")
        self._regenerate_button.setObjectName("regeneratePracticeButton")
        self._close_button.setObjectName("closePracticeDialogButton")

        self._module_combo.currentIndexChanged.connect(self._on_module_changed)
        self._generate_button.clicked.connect(self._on_generate_clicked)
        self._regenerate_button.clicked.connect(self._on_regenerate_clicked)
        self._close_button.clicked.connect(self.reject)

    def _load_modules(self) -> None:
        correlation_id = str(uuid4())
        try:
            modules = self._list_modules_use_case.execute(self._course_id)
        except Exception as exc:
            LOGGER.exception(
                (
                    "event=practice_ui_modules_load_failed correlation_id=%s course_id=%s "
                    "module_id=- llm_call_id=- error_type=%s"
                ),
                correlation_id,
                self._course_id,
                exc.__class__.__name__,
            )
            self._set_modules_unavailable_state(
                "Не удалось загрузить список модулей для практики."
            )
            return

        self._module_combo.blockSignals(True)
        self._module_combo.clear()
        for module in modules:
            self._module_combo.addItem(
                f"{module.module_order}. {module.module_title}",
                module.module_id,
            )
        self._module_combo.blockSignals(False)

        if not modules:
            self._set_modules_unavailable_state(
                "Сначала сформируйте и сохраните план курса, чтобы открыть практику."
            )
            return

        self._module_combo.setEnabled(True)
        self._generate_button.setEnabled(True)
        self._regenerate_button.setEnabled(True)
        self._status_label.setText("Выберите модуль и нажмите «Сгенерировать»." )
        self._load_state_for_selected_module()

    def _set_modules_unavailable_state(self, message: str) -> None:
        self._module_combo.setEnabled(False)
        self._generate_button.setEnabled(False)
        self._regenerate_button.setEnabled(False)
        self._statement_preview.clear()
        self._outline_preview.clear()
        self._history_list.clear()
        self._status_label.setText(message)

    def _on_module_changed(self, _: int) -> None:
        self._load_state_for_selected_module()

    def _on_generate_clicked(self) -> None:
        self._generate_practice_flow(action_name="generate")

    def _on_regenerate_clicked(self) -> None:
        self._generate_practice_flow(action_name="regenerate")

    def _generate_practice_flow(self, *, action_name: str) -> None:
        module_id = self._selected_module_id()
        if module_id is None:
            self._status_label.setText("Выберите модуль для генерации практики.")
            return

        difficulty = _selected_difficulty(self._difficulty_combo)
        candidate_count = self._candidate_count_spin.value()
        correlation_id = str(uuid4())
        LOGGER.info(
            (
                "event=practice_ui_generate_clicked correlation_id=%s course_id=%s module_id=%s "
                "llm_call_id=- action=%s difficulty=%s candidate_count=%s"
            ),
            correlation_id,
            self._course_id,
            module_id,
            action_name,
            difficulty.value,
            candidate_count,
        )

        try:
            result = self._generate_use_case.execute(
                GeneratePracticeCommand(
                    module_id=module_id,
                    difficulty=difficulty,
                    candidate_count=candidate_count,
                )
            )
        except Exception as exc:
            LOGGER.exception(
                (
                    "event=practice_ui_generate_failed correlation_id=%s course_id=%s module_id=%s "
                    "llm_call_id=- error_type=%s"
                ),
                correlation_id,
                self._course_id,
                module_id,
                exc.__class__.__name__,
            )
            QMessageBox.warning(self, "Ошибка генерации", str(exc))
            return

        self._last_llm_call_id = result.llm_call_id
        self._status_label.setText(
            "Практика обновлена: "
            f"вариантов {result.generated_count}, "
            f"в истории {result.history_count}."
        )
        self._load_state_for_selected_module()
        LOGGER.info(
            (
                "event=practice_ui_generate_completed correlation_id=%s course_id=%s module_id=%s "
                "llm_call_id=%s generated_count=%s history_count=%s attempts=%s"
            ),
            correlation_id,
            self._course_id,
            module_id,
            result.llm_call_id,
            result.generated_count,
            result.history_count,
            result.attempts,
        )

    def _load_state_for_selected_module(self) -> None:
        module_id = self._selected_module_id()
        if module_id is None:
            self._statement_preview.clear()
            self._outline_preview.clear()
            self._history_list.clear()
            self._status_label.setText("Выберите модуль для просмотра практики.")
            return

        correlation_id = str(uuid4())
        try:
            state = self._state_use_case.execute(module_id)
        except Exception as exc:
            LOGGER.exception(
                (
                    "event=practice_ui_state_load_failed correlation_id=%s course_id=%s "
                    "module_id=%s llm_call_id=%s error_type=%s"
                ),
                correlation_id,
                self._course_id,
                module_id,
                self._last_llm_call_id or "-",
                exc.__class__.__name__,
            )
            self._statement_preview.clear()
            self._outline_preview.clear()
            self._history_list.clear()
            self._status_label.setText("Не удалось загрузить текущее состояние практики.")
            return

        current_task = state.current_task
        if current_task is None:
            self._statement_preview.setPlainText("Задание пока не сгенерировано.")
            self._outline_preview.setPlainText("План решения пока не сгенерирован.")
        else:
            self._statement_preview.setPlainText(current_task.statement)
            self._outline_preview.setPlainText(current_task.expected_outline)

        self._history_list.clear()
        for task in state.history:
            self._history_list.addItem(_format_history_item(task))

    def _selected_module_id(self) -> str | None:
        module_id_value = self._module_combo.currentData(Qt.ItemDataRole.UserRole)
        if isinstance(module_id_value, str) and module_id_value:
            return module_id_value
        return None


def _selected_difficulty(combo_box: QComboBox) -> PracticeDifficulty:
    raw_value = combo_box.currentData(Qt.ItemDataRole.UserRole)
    if isinstance(raw_value, str):
        return PracticeDifficulty(raw_value)
    return PracticeDifficulty.MEDIUM


def _format_history_item(task: PracticeTask) -> QListWidgetItem:
    created_at_text = task.created_at.astimezone().strftime("%Y-%m-%d %H:%M")
    statement = task.statement
    statement_preview = statement[:80] + ("..." if len(statement) > 80 else "")
    difficulty = task.difficulty.value
    candidate_index = task.candidate_index

    item = QListWidgetItem(
        f"{created_at_text} | {difficulty} | Вариант #{candidate_index}\n{statement_preview}"
    )
    return item
