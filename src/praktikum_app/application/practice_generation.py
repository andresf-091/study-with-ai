"""Application use-cases and ports for practice generation and history."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from types import TracebackType
from typing import Protocol
from uuid import uuid4

from praktikum_app.application.llm import (
    LLMRequest,
    LLMRequestRejectedError,
    LLMResponse,
    LLMResponseSchemaError,
    LLMTaskType,
    LLMTemporaryError,
    MissingApiKeyLLMError,
)
from praktikum_app.domain.practice import (
    PracticeDifficulty,
    PracticeGenerationV1,
    PracticeTask,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PracticeModuleContext:
    """Module payload used as generation context for practice tasks."""

    module_id: str
    course_id: str
    course_title: str | None
    module_title: str
    module_order: int
    goals: list[str]
    topics: list[str]
    estimated_hours: int | None


@dataclass(frozen=True)
class PracticeModuleSummary:
    """Compact module metadata for practice module selection UI."""

    module_id: str
    course_id: str
    module_order: int
    module_title: str


@dataclass(frozen=True)
class PracticeTaskDraft:
    """Transient candidate data before persistence."""

    candidate_index: int
    statement: str
    expected_outline: str


@dataclass(frozen=True)
class PracticeTaskState:
    """Current practice task and persisted history for one module."""

    current_task: PracticeTask | None
    history: list[PracticeTask]


class PracticeRepository(Protocol):
    """Repository port for practice generation context and persistence."""

    def get_module_context(self, module_id: str) -> PracticeModuleContext | None:
        """Return generation context for selected module."""
        ...

    def list_modules_for_course(self, course_id: str) -> list[PracticeModuleSummary]:
        """Return modules available for practice generation."""
        ...

    def save_generated_batch(
        self,
        *,
        module_context: PracticeModuleContext,
        difficulty: PracticeDifficulty,
        llm_call_id: str,
        generation_id: str,
        created_at: datetime,
        candidates: list[PracticeTaskDraft],
    ) -> list[PracticeTask]:
        """Persist one regenerate batch and return saved tasks."""
        ...

    def get_current_task(self, module_id: str) -> PracticeTask | None:
        """Return latest selected task for module."""
        ...

    def list_task_history(self, module_id: str) -> list[PracticeTask]:
        """Return full regenerate history for module."""
        ...


class PracticeUnitOfWork(Protocol):
    """Unit-of-work port for practice generation/read flows."""

    practice: PracticeRepository

    def __enter__(self) -> PracticeUnitOfWork:
        """Start transactional scope."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Finalize transactional scope."""
        ...

    def commit(self) -> None:
        """Commit transaction."""
        ...

    def rollback(self) -> None:
        """Rollback transaction."""
        ...


PracticeUnitOfWorkFactory = Callable[[], PracticeUnitOfWork]
PracticeGenerationUserPromptBuilder = Callable[
    [PracticeModuleContext, PracticeDifficulty, int],
    str,
]


class PracticeGenerationRepairPromptBuilder(Protocol):
    """Build repair prompt from invalid output and diagnostics."""

    def __call__(
        self,
        *,
        invalid_output: str,
        validation_errors: str,
        candidate_count: int,
    ) -> str:
        """Return repaired prompt payload."""
        ...


class LLMRouterPort(Protocol):
    """Router protocol used by practice generation use-case."""

    def execute(
        self,
        request: LLMRequest[PracticeGenerationV1],
    ) -> LLMResponse[PracticeGenerationV1]:
        """Execute routed request and return validated response."""
        ...


@dataclass(frozen=True)
class GeneratePracticeCommand:
    """Input contract for practice generation request."""

    module_id: str
    difficulty: PracticeDifficulty
    candidate_count: int = 3
    max_repair_attempts: int = 2


@dataclass(frozen=True)
class GeneratePracticeResult:
    """Output contract for persisted generated practice batch."""

    course_id: str
    module_id: str
    generated_count: int
    history_count: int
    current_task: PracticeTask
    llm_call_id: str
    attempts: int


class GeneratePracticeUseCase:
    """Generate and persist practice candidates with bounded repair loop."""

    def __init__(
        self,
        uow_factory: PracticeUnitOfWorkFactory,
        llm_router: LLMRouterPort,
        *,
        system_prompt: str,
        response_schema: type[PracticeGenerationV1],
        build_user_prompt: PracticeGenerationUserPromptBuilder,
        build_repair_prompt: PracticeGenerationRepairPromptBuilder,
    ) -> None:
        self._uow_factory = uow_factory
        self._llm_router = llm_router
        self._system_prompt = system_prompt
        self._response_schema = response_schema
        self._build_user_prompt = build_user_prompt
        self._build_repair_prompt = build_repair_prompt

    def execute(self, command: GeneratePracticeCommand) -> GeneratePracticeResult:
        """Generate practice candidates and persist them into history."""
        if not command.module_id:
            raise ValueError("module_id is required")
        if command.candidate_count < 1:
            raise ValueError("candidate_count must be >= 1")
        if command.max_repair_attempts < 0:
            raise ValueError("max_repair_attempts must be >= 0")

        correlation_id = str(uuid4())
        with self._uow_factory() as uow:
            module_context = uow.practice.get_module_context(command.module_id)

        if module_context is None:
            raise ValueError("Не удалось найти выбранный модуль для генерации практики.")

        LOGGER.info(
            (
                "event=practice_generation_started correlation_id=%s course_id=%s "
                "module_id=%s llm_call_id=- difficulty=%s candidate_count=%s"
            ),
            correlation_id,
            module_context.course_id,
            command.module_id,
            command.difficulty.value,
            command.candidate_count,
        )

        prompt_for_attempt = self._build_user_prompt(
            module_context,
            command.difficulty,
            command.candidate_count,
        )
        max_attempts = command.max_repair_attempts + 1

        for attempt_index in range(max_attempts):
            attempt_number = attempt_index + 1
            try:
                response = self._llm_router.execute(
                    LLMRequest(
                        task_type=LLMTaskType.PRACTICE_GEN,
                        system_prompt=self._system_prompt,
                        user_prompt=prompt_for_attempt,
                        response_schema=self._response_schema,
                        correlation_id=correlation_id,
                        course_id=module_context.course_id,
                        module_id=command.module_id,
                        max_output_tokens=4096,
                        temperature=0.3,
                    )
                )
            except MissingApiKeyLLMError as exc:
                LOGGER.warning(
                    (
                        "event=practice_generation_missing_key correlation_id=%s course_id=%s "
                        "module_id=%s llm_call_id=- error_type=%s"
                    ),
                    correlation_id,
                    module_context.course_id,
                    command.module_id,
                    exc.__class__.__name__,
                )
                raise ValueError(
                    "Не найден API-ключ LLM. "
                    "Откройте «Ключи LLM...» и сохраните ключ."
                ) from exc
            except LLMRequestRejectedError as exc:
                LOGGER.warning(
                    (
                        "event=practice_generation_request_rejected correlation_id=%s "
                        "course_id=%s module_id=%s llm_call_id=- error_type=%s"
                    ),
                    correlation_id,
                    module_context.course_id,
                    command.module_id,
                    exc.__class__.__name__,
                )
                raise ValueError(str(exc)) from exc
            except LLMTemporaryError as exc:
                LOGGER.warning(
                    (
                        "event=practice_generation_temporary_error correlation_id=%s "
                        "course_id=%s module_id=%s llm_call_id=- error_type=%s"
                    ),
                    correlation_id,
                    module_context.course_id,
                    command.module_id,
                    exc.__class__.__name__,
                )
                raise ValueError(str(exc)) from exc
            except LLMResponseSchemaError as exc:
                LOGGER.warning(
                    (
                        "event=practice_generation_schema_invalid correlation_id=%s "
                        "course_id=%s module_id=%s llm_call_id=%s "
                        "attempt=%s/%s error_type=%s"
                    ),
                    correlation_id,
                    module_context.course_id,
                    command.module_id,
                    exc.llm_call_id,
                    attempt_number,
                    max_attempts,
                    exc.__class__.__name__,
                )
                if attempt_number >= max_attempts:
                    raise ValueError(
                        "Не удалось сформировать корректное практическое задание. "
                        "Попробуйте снова позже."
                    ) from exc

                prompt_for_attempt = self._build_repair_prompt(
                    invalid_output=exc.invalid_output,
                    validation_errors=exc.validation_errors,
                    candidate_count=command.candidate_count,
                )
                continue

            candidate_drafts = _build_candidate_drafts(
                response=response,
                candidate_count=command.candidate_count,
            )
            if candidate_drafts is None:
                validation_error = (
                    "Модель вернула недостаточно кандидатов: "
                    f"ожидалось {command.candidate_count}, "
                    f"получено {len(response.parsed.candidates)}."
                )
                LOGGER.warning(
                    (
                        "event=practice_generation_candidates_insufficient "
                        "correlation_id=%s course_id=%s module_id=%s llm_call_id=%s "
                        "attempt=%s/%s validation_error=%s"
                    ),
                    correlation_id,
                    module_context.course_id,
                    command.module_id,
                    response.llm_call_id,
                    attempt_number,
                    max_attempts,
                    validation_error,
                )
                if attempt_number >= max_attempts:
                    raise ValueError(
                        "Не удалось получить нужное количество вариантов практики. "
                        "Попробуйте снова."
                    )

                prompt_for_attempt = self._build_repair_prompt(
                    invalid_output=response.output_text,
                    validation_errors=validation_error,
                    candidate_count=command.candidate_count,
                )
                continue

            try:
                with self._uow_factory() as uow:
                    saved_tasks = uow.practice.save_generated_batch(
                        module_context=module_context,
                        difficulty=command.difficulty,
                        llm_call_id=response.llm_call_id,
                        generation_id=str(uuid4()),
                        created_at=datetime.now(tz=UTC),
                        candidates=candidate_drafts,
                    )
                    current_task = uow.practice.get_current_task(command.module_id)
                    history = uow.practice.list_task_history(command.module_id)
                    uow.commit()
            except Exception as exc:
                LOGGER.exception(
                    (
                        "event=practice_generation_persist_failed correlation_id=%s "
                        "course_id=%s module_id=%s llm_call_id=%s generated_count=%s "
                        "error_type=%s"
                    ),
                    correlation_id,
                    module_context.course_id,
                    command.module_id,
                    response.llm_call_id,
                    len(candidate_drafts),
                    exc.__class__.__name__,
                )
                raise

            if current_task is None:
                raise RuntimeError("Persisted practice task is missing after save operation.")

            LOGGER.info(
                (
                    "event=practice_generation_completed correlation_id=%s course_id=%s "
                    "module_id=%s llm_call_id=%s generated_count=%s history_count=%s "
                    "attempt=%s"
                ),
                correlation_id,
                module_context.course_id,
                command.module_id,
                response.llm_call_id,
                len(saved_tasks),
                len(history),
                attempt_number,
            )
            return GeneratePracticeResult(
                course_id=module_context.course_id,
                module_id=command.module_id,
                generated_count=len(saved_tasks),
                history_count=len(history),
                current_task=current_task,
                llm_call_id=response.llm_call_id,
                attempts=attempt_number,
            )

        raise AssertionError("Unreachable practice generation loop termination")


class ListPracticeModulesUseCase:
    """Load modules for selected course on practice screen."""

    def __init__(self, uow_factory: PracticeUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def execute(self, course_id: str) -> list[PracticeModuleSummary]:
        """Return persisted modules for practice selection."""
        if not course_id:
            raise ValueError("course_id is required")

        correlation_id = str(uuid4())
        with self._uow_factory() as uow:
            modules = uow.practice.list_modules_for_course(course_id)

        LOGGER.info(
            (
                "event=practice_modules_loaded correlation_id=%s course_id=%s module_id=- "
                "llm_call_id=- modules_count=%s"
            ),
            correlation_id,
            course_id,
            len(modules),
        )
        return modules


class GetPracticeTaskStateUseCase:
    """Load current practice task and history for selected module."""

    def __init__(self, uow_factory: PracticeUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def execute(self, module_id: str) -> PracticeTaskState:
        """Return current task and history for module."""
        if not module_id:
            raise ValueError("module_id is required")

        correlation_id = str(uuid4())
        with self._uow_factory() as uow:
            current_task = uow.practice.get_current_task(module_id)
            history = uow.practice.list_task_history(module_id)

        LOGGER.info(
            (
                "event=practice_state_loaded correlation_id=%s course_id=- module_id=%s "
                "llm_call_id=- current_exists=%s history_count=%s"
            ),
            correlation_id,
            module_id,
            current_task is not None,
            len(history),
        )
        return PracticeTaskState(current_task=current_task, history=history)


def _build_candidate_drafts(
    *,
    response: LLMResponse[PracticeGenerationV1],
    candidate_count: int,
) -> list[PracticeTaskDraft] | None:
    if len(response.parsed.candidates) < candidate_count:
        return None

    drafts: list[PracticeTaskDraft] = []
    for index, candidate in enumerate(response.parsed.candidates[:candidate_count], start=1):
        drafts.append(
            PracticeTaskDraft(
                candidate_index=index,
                statement=candidate.statement,
                expected_outline=candidate.expected_outline,
            )
        )

    return drafts
