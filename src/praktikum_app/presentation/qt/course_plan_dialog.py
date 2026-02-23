"""Review/edit dialog for CoursePlan v1 parsing and saving."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Protocol
from uuid import uuid4

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from praktikum_app.application.course_decomposition import (
    GetCoursePlanUseCase,
    ParseCourseCommand,
    ParseCourseResult,
    ParseCourseUseCase,
    SaveCoursePlanCommand,
    SaveCoursePlanResult,
    SaveCoursePlanUseCase,
)
from praktikum_app.domain.course_plan import (
    CoursePlanCourse,
    CoursePlanDeadline,
    CoursePlanModule,
    CoursePlanV1,
)

LOGGER = logging.getLogger(__name__)


class ParseCourseUseCasePort(Protocol):
    """Port for parse action injection in UI tests."""

    def execute(self, command: ParseCourseCommand) -> ParseCourseResult:
        """Parse course from raw text and return validated plan."""
        ...


class SaveCoursePlanUseCasePort(Protocol):
    """Port for save action injection in UI tests."""

    def execute(self, command: SaveCoursePlanCommand) -> SaveCoursePlanResult:
        """Persist edited plan."""
        ...


class GetCoursePlanUseCasePort(Protocol):
    """Port for load action injection in UI tests."""

    def execute(self, course_id: str) -> CoursePlanV1 | None:
        """Load existing plan if already saved."""
        ...


class CoursePlanDialog(QDialog):
    """Dialog for parse -> review/edit -> save flow."""

    def __init__(
        self,
        *,
        course_id: str,
        parse_use_case: ParseCourseUseCasePort | ParseCourseUseCase,
        save_use_case: SaveCoursePlanUseCasePort | SaveCoursePlanUseCase,
        get_use_case: GetCoursePlanUseCasePort | GetCoursePlanUseCase,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._course_id = course_id
        self._parse_use_case = parse_use_case
        self._save_use_case = save_use_case
        self._get_use_case = get_use_case
        self._last_llm_call_id: str | None = None

        self._title_input = QLineEdit(self)
        self._description_input = QPlainTextEdit(self)
        self._start_date_input = QLineEdit(self)
        self._modules_table = QTableWidget(self)
        self._deadlines_table = QTableWidget(self)
        self._status_label = QLabel(self)
        self._generate_button = QPushButton("Сформировать план", self)
        self._save_button = QPushButton("Сохранить план", self)
        self._close_button = QPushButton("Закрыть", self)

        self._build_ui()
        self._load_existing_plan()

    def _build_ui(self) -> None:
        self.setWindowTitle("План курса")
        self.resize(1080, 760)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 18, 20, 18)
        root_layout.setSpacing(12)

        header_label = QLabel(f"Курс: {self._course_id}", self)
        header_label.setObjectName("coursePlanCourseIdLabel")
        root_layout.addWidget(header_label)

        form_layout = QFormLayout()
        form_layout.setSpacing(8)
        self._title_input.setObjectName("coursePlanTitleInput")
        self._description_input.setObjectName("coursePlanDescriptionInput")
        self._start_date_input.setObjectName("coursePlanStartDateInput")
        self._start_date_input.setPlaceholderText("YYYY-MM-DD (необязательно)")
        form_layout.addRow("Название курса", self._title_input)
        form_layout.addRow("Описание", self._description_input)
        form_layout.addRow("Дата старта", self._start_date_input)
        root_layout.addLayout(form_layout)

        modules_label = QLabel("Модули", self)
        root_layout.addWidget(modules_label)
        self._modules_table.setObjectName("coursePlanModulesTable")
        self._modules_table.setColumnCount(5)
        self._modules_table.setHorizontalHeaderLabels(
            ["Порядок", "Название", "Цели (через ;)", "Темы (через ;)", "Часы"]
        )
        self._modules_table.horizontalHeader().setStretchLastSection(True)
        root_layout.addWidget(self._modules_table, stretch=2)

        deadlines_label = QLabel("Дедлайны", self)
        root_layout.addWidget(deadlines_label)
        self._deadlines_table.setObjectName("coursePlanDeadlinesTable")
        self._deadlines_table.setColumnCount(5)
        self._deadlines_table.setHorizontalHeaderLabels(
            ["Порядок", "Модуль", "Срок (ISO)", "Тип", "Заметки"]
        )
        self._deadlines_table.horizontalHeader().setStretchLastSection(True)
        root_layout.addWidget(self._deadlines_table, stretch=2)

        self._status_label.setObjectName("coursePlanStatusLabel")
        self._status_label.setWordWrap(True)
        self._status_label.setText(
            "Нажмите «Сформировать план» для декомпозиции курса."
        )
        root_layout.addWidget(self._status_label)

        actions_layout = QHBoxLayout()
        actions_layout.addWidget(self._generate_button)
        actions_layout.addWidget(self._save_button)
        actions_layout.addStretch(1)
        actions_layout.addWidget(self._close_button)
        root_layout.addLayout(actions_layout)

        self._generate_button.setObjectName("generateCoursePlanButton")
        self._save_button.setObjectName("saveCoursePlanButton")
        self._close_button.setObjectName("closeCoursePlanButton")

        self._generate_button.clicked.connect(self._on_generate_clicked)
        self._save_button.clicked.connect(self._on_save_clicked)
        self._close_button.clicked.connect(self.reject)

    def _load_existing_plan(self) -> None:
        correlation_id = str(uuid4())
        try:
            existing_plan = self._get_use_case.execute(self._course_id)
        except Exception as exc:
            LOGGER.exception(
                (
                    "event=course_plan_ui_load_failed correlation_id=%s course_id=%s module_id=- "
                    "llm_call_id=- error_type=%s"
                ),
                correlation_id,
                self._course_id,
                exc.__class__.__name__,
            )
            self._status_label.setText("Не удалось загрузить сохранённый план курса из БД.")
            return

        if existing_plan is None:
            return

        self._fill_form(existing_plan)
        self._status_label.setText("Загружен ранее сохранённый план курса.")

    def _on_generate_clicked(self) -> None:
        correlation_id = str(uuid4())
        try:
            result = self._parse_use_case.execute(
                ParseCourseCommand(course_id=self._course_id)
            )
        except Exception as exc:
            LOGGER.exception(
                (
                    "event=course_plan_ui_generate_failed correlation_id=%s course_id=%s "
                    "module_id=- "
                    "llm_call_id=- error_type=%s"
                ),
                correlation_id,
                self._course_id,
                exc.__class__.__name__,
            )
            QMessageBox.warning(
                self,
                "Ошибка декомпозиции",
                str(exc),
            )
            return

        self._last_llm_call_id = result.llm_call_id
        self._fill_form(result.plan)
        self._status_label.setText(
            f"План сформирован. Попыток: {result.attempts}. LLM call: {result.llm_call_id[:8]}."
        )
        LOGGER.info(
            (
                "event=course_plan_ui_generated correlation_id=%s course_id=%s module_id=- "
                "llm_call_id=%s modules_count=%s deadlines_count=%s attempts=%s"
            ),
            correlation_id,
            self._course_id,
            result.llm_call_id,
            len(result.plan.modules),
            len(result.plan.deadlines),
            result.attempts,
        )

    def _on_save_clicked(self) -> None:
        correlation_id = str(uuid4())
        try:
            plan = self._collect_plan_from_form()
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Ошибка валидации",
                str(exc),
            )
            return

        try:
            save_result = self._save_use_case.execute(
                SaveCoursePlanCommand(course_id=self._course_id, plan=plan)
            )
        except Exception as exc:
            LOGGER.exception(
                (
                    "event=course_plan_ui_save_failed correlation_id=%s course_id=%s module_id=- "
                    "llm_call_id=%s error_type=%s"
                ),
                correlation_id,
                self._course_id,
                self._last_llm_call_id or "-",
                exc.__class__.__name__,
            )
            QMessageBox.warning(
                self,
                "Ошибка сохранения",
                "Не удалось сохранить план курса в локальную БД.",
            )
            return

        self._status_label.setText(
            "План сохранён: "
            f"модулей {save_result.modules_count}, дедлайнов {save_result.deadlines_count}."
        )
        LOGGER.info(
            (
                "event=course_plan_ui_saved correlation_id=%s course_id=%s module_id=- "
                "llm_call_id=%s modules_count=%s deadlines_count=%s"
            ),
            correlation_id,
            self._course_id,
            self._last_llm_call_id or "-",
            save_result.modules_count,
            save_result.deadlines_count,
        )

    def _fill_form(self, plan: CoursePlanV1) -> None:
        self._title_input.setText(plan.course.title)
        self._description_input.setPlainText(plan.course.description)
        self._start_date_input.setText(
            plan.course.start_date.isoformat() if plan.course.start_date else ""
        )

        self._modules_table.setRowCount(len(plan.modules))
        for row_index, module in enumerate(plan.modules):
            self._modules_table.setItem(row_index, 0, QTableWidgetItem(str(module.order)))
            self._modules_table.setItem(row_index, 1, QTableWidgetItem(module.title))
            self._modules_table.setItem(row_index, 2, QTableWidgetItem("; ".join(module.goals)))
            self._modules_table.setItem(row_index, 3, QTableWidgetItem("; ".join(module.topics)))
            self._modules_table.setItem(row_index, 4, QTableWidgetItem(str(module.estimated_hours)))

        self._deadlines_table.setRowCount(len(plan.deadlines))
        for row_index, deadline in enumerate(plan.deadlines):
            self._deadlines_table.setItem(row_index, 0, QTableWidgetItem(str(deadline.order)))
            self._deadlines_table.setItem(row_index, 1, QTableWidgetItem(str(deadline.module_ref)))
            self._deadlines_table.setItem(
                row_index,
                2,
                QTableWidgetItem(deadline.due_at.isoformat() if deadline.due_at else ""),
            )
            self._deadlines_table.setItem(row_index, 3, QTableWidgetItem(deadline.kind))
            self._deadlines_table.setItem(row_index, 4, QTableWidgetItem(deadline.notes or ""))

    def _collect_plan_from_form(self) -> CoursePlanV1:
        title = self._title_input.text().strip()
        description = self._description_input.toPlainText().strip()
        if not title:
            raise ValueError("Заполните поле «Название курса».")
        if not description:
            raise ValueError("Заполните поле «Описание».")

        start_date_value: date | None = None
        start_date_text = self._start_date_input.text().strip()
        if start_date_text:
            try:
                start_date_value = date.fromisoformat(start_date_text)
            except ValueError as exc:
                raise ValueError("Дата старта должна быть в формате YYYY-MM-DD.") from exc

        modules: list[CoursePlanModule] = []
        for row_index in range(self._modules_table.rowCount()):
            order_text = _table_text(self._modules_table, row_index, 0)
            title_text = _table_text(self._modules_table, row_index, 1)
            goals_text = _table_text(self._modules_table, row_index, 2)
            topics_text = _table_text(self._modules_table, row_index, 3)
            hours_text = _table_text(self._modules_table, row_index, 4)

            if (
                not order_text
                and not title_text
                and not goals_text
                and not topics_text
                and not hours_text
            ):
                continue

            modules.append(
                CoursePlanModule(
                    order=_parse_int(order_text, "порядок модуля"),
                    title=title_text,
                    goals=_split_semicolon_list(goals_text),
                    topics=_split_semicolon_list(topics_text),
                    estimated_hours=_parse_int(hours_text, "оценка часов модуля"),
                    submission_criteria=None,
                )
            )

        deadlines: list[CoursePlanDeadline] = []
        for row_index in range(self._deadlines_table.rowCount()):
            order_text = _table_text(self._deadlines_table, row_index, 0)
            module_ref_text = _table_text(self._deadlines_table, row_index, 1)
            due_at_text = _table_text(self._deadlines_table, row_index, 2)
            kind_text = _table_text(self._deadlines_table, row_index, 3)
            notes_text = _table_text(self._deadlines_table, row_index, 4)

            if (
                not order_text
                and not module_ref_text
                and not due_at_text
                and not kind_text
                and not notes_text
            ):
                continue

            deadlines.append(
                CoursePlanDeadline(
                    order=_parse_int(order_text, "порядок дедлайна"),
                    module_ref=_parse_int(module_ref_text, "ссылка на модуль"),
                    due_at=_parse_datetime_optional(due_at_text),
                    kind=kind_text,
                    notes=notes_text or None,
                )
            )

        return CoursePlanV1(
            schema_version="v1",
            course=CoursePlanCourse(
                title=title,
                description=description,
                start_date=start_date_value,
            ),
            modules=modules,
            deadlines=deadlines,
        )


def _table_text(table: QTableWidget, row: int, col: int) -> str:
    item = table.item(row, col)
    return item.text().strip() if item is not None else ""


def _split_semicolon_list(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(";") if part.strip()]


def _parse_int(value: str, field_name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"Некорректное значение поля «{field_name}»: нужно целое число.") from exc
    if parsed < 1:
        raise ValueError(f"Поле «{field_name}» должно быть >= 1.")
    return parsed


def _parse_datetime_optional(value: str) -> datetime | None:
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(
            "Дата дедлайна должна быть в ISO-формате, например 2026-03-01T12:00:00."
        ) from exc
