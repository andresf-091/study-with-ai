"""Application use-cases for LLM course decomposition and plan persistence."""

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
from praktikum_app.domain.course_plan import CoursePlanV1

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CourseRawTextRecord:
    """Minimal raw text payload required for LLM decomposition."""

    course_id: str
    raw_text_id: str
    content: str
    content_hash: str
    length: int


@dataclass(frozen=True)
class SaveCoursePlanStats:
    """Persistence counters for one plan save operation."""

    modules_count: int
    deadlines_count: int


class CoursePlanRepository(Protocol):
    """Repository port for reading raw text and persisting/reloading plans."""

    def get_raw_text(
        self,
        course_id: str,
        raw_text_id: str | None = None,
    ) -> CourseRawTextRecord | None:
        """Return raw text payload for selected course and optional raw text id."""
        ...

    def load_course_plan(self, course_id: str) -> CoursePlanV1 | None:
        """Load saved plan for review/edit, or None when not found."""
        ...

    def replace_course_plan(
        self,
        course_id: str,
        plan: CoursePlanV1,
        saved_at: datetime,
    ) -> SaveCoursePlanStats:
        """Replace persisted modules/deadlines for course in one transaction."""
        ...


class CoursePlanUnitOfWork(Protocol):
    """Unit-of-work port for course decomposition flows."""

    plans: CoursePlanRepository

    def __enter__(self) -> CoursePlanUnitOfWork:
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
        """Commit current transaction."""
        ...

    def rollback(self) -> None:
        """Rollback current transaction."""
        ...


CoursePlanUnitOfWorkFactory = Callable[[], CoursePlanUnitOfWork]
CourseParseUserPromptBuilder = Callable[[str], str]


class CourseParseRepairPromptBuilder(Protocol):
    """Build repair prompt from invalid output and validation diagnostics."""

    def __call__(self, *, invalid_output: str, validation_errors: str) -> str:
        """Return user prompt for next repair attempt."""
        ...


class LLMRouterPort(Protocol):
    """Protocol used by parse use-case for routed LLM invocations."""

    def execute(self, request: LLMRequest[CoursePlanV1]) -> LLMResponse[CoursePlanV1]:
        """Execute routed request and return validated schema payload."""
        ...


@dataclass(frozen=True)
class ParseCourseCommand:
    """Input contract for parsing selected imported course."""

    course_id: str
    raw_text_id: str | None = None
    max_repair_attempts: int = 2


@dataclass(frozen=True)
class ParseCourseResult:
    """Output of parse flow with validated plan payload."""

    course_id: str
    raw_text_id: str
    plan: CoursePlanV1
    llm_call_id: str
    attempts: int


class ParseCourseUseCase:
    """Parse imported raw text into CoursePlan v1 with bounded repair loop."""

    def __init__(
        self,
        uow_factory: CoursePlanUnitOfWorkFactory,
        llm_router: LLMRouterPort,
        *,
        system_prompt: str,
        response_schema: type[CoursePlanV1],
        build_user_prompt: CourseParseUserPromptBuilder,
        build_repair_prompt: CourseParseRepairPromptBuilder,
    ) -> None:
        self._uow_factory = uow_factory
        self._llm_router = llm_router
        self._system_prompt = system_prompt
        self._response_schema = response_schema
        self._build_user_prompt = build_user_prompt
        self._build_repair_prompt = build_repair_prompt

    def execute(self, command: ParseCourseCommand) -> ParseCourseResult:
        """Run parse flow and return validated CoursePlan."""
        if not command.course_id:
            raise ValueError("course_id is required")
        if command.max_repair_attempts < 0:
            raise ValueError("max_repair_attempts must be >= 0")

        correlation_id = str(uuid4())
        with self._uow_factory() as uow:
            raw_text = uow.plans.get_raw_text(command.course_id, command.raw_text_id)

        if raw_text is None:
            raise ValueError(
                "Не удалось найти импортированный текст "
                "выбранного курса."
            )

        LOGGER.info(
            (
                "event=course_parse_started correlation_id=%s course_id=%s "
                "module_id=- llm_call_id=- "
                "raw_text_id=%s content_hash=%s length=%s max_repair_attempts=%s"
            ),
            correlation_id,
            command.course_id,
            raw_text.raw_text_id,
            raw_text.content_hash,
            raw_text.length,
            command.max_repair_attempts,
        )

        prompt_for_attempt = self._build_user_prompt(raw_text.content)
        max_attempts = command.max_repair_attempts + 1

        for attempt_index in range(max_attempts):
            attempt_number = attempt_index + 1
            try:
                response = self._llm_router.execute(
                    LLMRequest(
                        task_type=LLMTaskType.COURSE_PARSE,
                        system_prompt=self._system_prompt,
                        user_prompt=prompt_for_attempt,
                        response_schema=self._response_schema,
                        correlation_id=correlation_id,
                        course_id=command.course_id,
                        module_id=None,
                        max_output_tokens=4096,
                        temperature=0.1,
                    )
                )
            except MissingApiKeyLLMError as exc:
                LOGGER.warning(
                    (
                        "event=course_parse_missing_key correlation_id=%s course_id=%s module_id=- "
                        "llm_call_id=- raw_text_id=%s error_type=%s"
                    ),
                    correlation_id,
                    command.course_id,
                    raw_text.raw_text_id,
                    exc.__class__.__name__,
                )
                raise ValueError(
                    "Не найден API-ключ LLM. "
                    "Откройте «Ключи LLM...» и сохраните ключ."
                ) from exc
            except LLMRequestRejectedError as exc:
                LOGGER.warning(
                    (
                        "event=course_parse_request_rejected correlation_id=%s course_id=%s "
                        "module_id=- llm_call_id=- raw_text_id=%s error_type=%s"
                    ),
                    correlation_id,
                    command.course_id,
                    raw_text.raw_text_id,
                    exc.__class__.__name__,
                )
                raise ValueError(str(exc)) from exc
            except LLMTemporaryError as exc:
                LOGGER.warning(
                    (
                        "event=course_parse_execution_failed correlation_id=%s course_id=%s "
                        "module_id=- "
                        "llm_call_id=- raw_text_id=%s error_type=%s"
                    ),
                    correlation_id,
                    command.course_id,
                    raw_text.raw_text_id,
                    exc.__class__.__name__,
                )
                raise ValueError(str(exc)) from exc
            except LLMResponseSchemaError as exc:
                LOGGER.warning(
                    (
                        "event=course_parse_schema_invalid correlation_id=%s course_id=%s "
                        "module_id=- "
                        "llm_call_id=%s raw_text_id=%s attempt=%s/%s error_type=%s"
                    ),
                    correlation_id,
                    command.course_id,
                    exc.llm_call_id,
                    raw_text.raw_text_id,
                    attempt_number,
                    max_attempts,
                    exc.__class__.__name__,
                )
                if attempt_number >= max_attempts:
                    raise ValueError(
                        "Не удалось сформировать корректный план курса. "
                        "Уточните текст курса и попробуйте снова."
                    ) from exc

                prompt_for_attempt = self._build_repair_prompt(
                    invalid_output=exc.invalid_output,
                    validation_errors=exc.validation_errors,
                )
                continue

            LOGGER.info(
                (
                    "event=course_parse_completed correlation_id=%s course_id=%s module_id=- "
                    "llm_call_id=%s raw_text_id=%s attempt=%s modules_count=%s deadlines_count=%s"
                ),
                correlation_id,
                command.course_id,
                response.llm_call_id,
                raw_text.raw_text_id,
                attempt_number,
                len(response.parsed.modules),
                len(response.parsed.deadlines),
            )
            return ParseCourseResult(
                course_id=command.course_id,
                raw_text_id=raw_text.raw_text_id,
                plan=response.parsed,
                llm_call_id=response.llm_call_id,
                attempts=attempt_number,
            )

        raise AssertionError("Unreachable parse loop termination")


@dataclass(frozen=True)
class SaveCoursePlanCommand:
    """Input contract for saving edited plan into database."""

    course_id: str
    plan: CoursePlanV1


@dataclass(frozen=True)
class SaveCoursePlanResult:
    """Result contract for save plan operation."""

    course_id: str
    modules_count: int
    deadlines_count: int


class SaveCoursePlanUseCase:
    """Persist CoursePlan into modules/deadlines tables transactionally."""

    def __init__(self, uow_factory: CoursePlanUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def execute(self, command: SaveCoursePlanCommand) -> SaveCoursePlanResult:
        """Replace current saved plan for selected course."""
        if not command.course_id:
            raise ValueError("course_id is required")

        correlation_id = str(uuid4())
        try:
            with self._uow_factory() as uow:
                stats = uow.plans.replace_course_plan(
                    course_id=command.course_id,
                    plan=command.plan,
                    saved_at=datetime.now(tz=UTC),
                )
                uow.commit()
        except Exception as exc:
            LOGGER.exception(
                (
                    "event=course_plan_save_failed correlation_id=%s course_id=%s "
                    "module_id=- llm_call_id=- "
                    "modules_count=%s deadlines_count=%s error_type=%s"
                ),
                correlation_id,
                command.course_id,
                len(command.plan.modules),
                len(command.plan.deadlines),
                exc.__class__.__name__,
            )
            raise

        LOGGER.info(
            (
                "event=course_plan_saved correlation_id=%s course_id=%s module_id=- llm_call_id=- "
                "modules_count=%s deadlines_count=%s"
            ),
            correlation_id,
            command.course_id,
            stats.modules_count,
            stats.deadlines_count,
        )
        return SaveCoursePlanResult(
            course_id=command.course_id,
            modules_count=stats.modules_count,
            deadlines_count=stats.deadlines_count,
        )


class GetCoursePlanUseCase:
    """Load persisted plan for selected course to prefill review screen."""

    def __init__(self, uow_factory: CoursePlanUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def execute(self, course_id: str) -> CoursePlanV1 | None:
        """Return persisted course plan for selected course."""
        if not course_id:
            raise ValueError("course_id is required")

        correlation_id = str(uuid4())
        with self._uow_factory() as uow:
            plan = uow.plans.load_course_plan(course_id)

        LOGGER.info(
            (
                "event=course_plan_loaded correlation_id=%s course_id=%s module_id=- llm_call_id=- "
                "found=%s"
            ),
            correlation_id,
            course_id,
            plan is not None,
        )
        return plan

