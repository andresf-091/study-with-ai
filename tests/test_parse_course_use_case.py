"""Use-case tests for course parsing with bounded repair loop."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pytest

from praktikum_app.application.course_decomposition import (
    CoursePlanRepository,
    CoursePlanUnitOfWork,
    CourseRawTextRecord,
    ParseCourseCommand,
    ParseCourseUseCase,
    SaveCoursePlanStats,
)
from praktikum_app.application.llm import (
    LLMRequest,
    LLMRequestRejectedError,
    LLMResponse,
    LLMResponseSchemaError,
    LLMServiceProvider,
    LLMTemporaryError,
    MissingApiKeyLLMError,
)
from praktikum_app.domain.course_plan import (
    CoursePlanCourse,
    CoursePlanModule,
    CoursePlanV1,
)

SYSTEM_PROMPT = "system"


class FakeCoursePlanRepository(CoursePlanRepository):
    """Repository fake with deterministic raw text payload."""

    def __init__(self, raw_text: CourseRawTextRecord | None) -> None:
        self._raw_text = raw_text

    def get_raw_text(
        self,
        course_id: str,
        raw_text_id: str | None = None,
    ) -> CourseRawTextRecord | None:
        if self._raw_text is None:
            return None
        if self._raw_text.course_id != course_id:
            return None
        if raw_text_id is not None and raw_text_id != self._raw_text.raw_text_id:
            return None
        return self._raw_text

    def load_course_plan(self, course_id: str) -> CoursePlanV1 | None:  # noqa: ARG002
        return None

    def replace_course_plan(
        self,
        course_id: str,
        plan: CoursePlanV1,
        saved_at: datetime,
    ) -> SaveCoursePlanStats:  # noqa: ARG002
        return SaveCoursePlanStats(
            modules_count=len(plan.modules),
            deadlines_count=len(plan.deadlines),
        )


class FakeCoursePlanUow(CoursePlanUnitOfWork):
    """UoW fake for parse tests."""

    def __init__(self, repository: CoursePlanRepository) -> None:
        self.plans = repository

    def __enter__(self) -> FakeCoursePlanUow:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


@dataclass
class FakeRouter:
    """Scripted router that returns a sequence of responses/errors."""

    scripted: list[LLMResponse[CoursePlanV1] | Exception]

    def __post_init__(self) -> None:
        self.requests: list[LLMRequest[CoursePlanV1]] = []

    def execute(self, request: LLMRequest[CoursePlanV1]) -> LLMResponse[CoursePlanV1]:
        self.requests.append(request)
        step = self.scripted.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def test_parse_course_use_case_success_first_attempt() -> None:
    raw_text = CourseRawTextRecord(
        course_id="course-1",
        raw_text_id="raw-1",
        content="Course text",
        content_hash="hash",
        length=10,
    )
    router = FakeRouter(scripted=[_success_response(llm_call_id="call-1")])
    use_case = ParseCourseUseCase(
        uow_factory=lambda: FakeCoursePlanUow(FakeCoursePlanRepository(raw_text)),
        llm_router=router,
        system_prompt=SYSTEM_PROMPT,
        response_schema=CoursePlanV1,
        build_user_prompt=_build_user_prompt,
        build_repair_prompt=_build_repair_prompt,
    )

    result = use_case.execute(ParseCourseCommand(course_id="course-1"))

    assert result.course_id == "course-1"
    assert result.raw_text_id == "raw-1"
    assert result.llm_call_id == "call-1"
    assert result.attempts == 1
    assert len(result.plan.modules) == 1
    assert len(router.requests) == 1


def test_parse_course_use_case_repairs_invalid_output_then_succeeds() -> None:
    raw_text = CourseRawTextRecord(
        course_id="course-1",
        raw_text_id="raw-1",
        content="Course text",
        content_hash="hash",
        length=10,
    )
    router = FakeRouter(
        scripted=[
            LLMResponseSchemaError(
                "invalid",
                repair_prompt="repair from router",
                llm_call_id="call-invalid",
                invalid_output="{}",
                validation_errors="field required",
            ),
            _success_response(llm_call_id="call-2"),
        ]
    )
    use_case = ParseCourseUseCase(
        uow_factory=lambda: FakeCoursePlanUow(FakeCoursePlanRepository(raw_text)),
        llm_router=router,
        system_prompt=SYSTEM_PROMPT,
        response_schema=CoursePlanV1,
        build_user_prompt=_build_user_prompt,
        build_repair_prompt=_build_repair_prompt,
    )

    result = use_case.execute(ParseCourseCommand(course_id="course-1", max_repair_attempts=2))

    assert result.attempts == 2
    assert result.llm_call_id == "call-2"
    assert len(router.requests) == 2
    assert "Ошибки валидации" in router.requests[1].user_prompt


def test_parse_course_use_case_fails_when_repair_budget_exhausted() -> None:
    raw_text = CourseRawTextRecord(
        course_id="course-1",
        raw_text_id="raw-1",
        content="Course text",
        content_hash="hash",
        length=10,
    )
    router = FakeRouter(
        scripted=[
            LLMResponseSchemaError(
                "invalid",
                repair_prompt="repair from router",
                llm_call_id="call-invalid-1",
                invalid_output="{}",
                validation_errors="field required",
            ),
            LLMResponseSchemaError(
                "invalid",
                repair_prompt="repair from router",
                llm_call_id="call-invalid-2",
                invalid_output="{}",
                validation_errors="field required",
            ),
        ]
    )
    use_case = ParseCourseUseCase(
        uow_factory=lambda: FakeCoursePlanUow(FakeCoursePlanRepository(raw_text)),
        llm_router=router,
        system_prompt=SYSTEM_PROMPT,
        response_schema=CoursePlanV1,
        build_user_prompt=_build_user_prompt,
        build_repair_prompt=_build_repair_prompt,
    )

    with pytest.raises(
        ValueError,
        match="Не удалось сформировать корректный план курса",
    ):
        use_case.execute(ParseCourseCommand(course_id="course-1", max_repair_attempts=1))

    assert len(router.requests) == 2


def test_parse_course_use_case_shows_user_safe_message_for_missing_key() -> None:
    raw_text = CourseRawTextRecord(
        course_id="course-1",
        raw_text_id="raw-1",
        content="Course text",
        content_hash="hash",
        length=10,
    )
    router = FakeRouter(scripted=[MissingApiKeyLLMError("missing key")])
    use_case = ParseCourseUseCase(
        uow_factory=lambda: FakeCoursePlanUow(FakeCoursePlanRepository(raw_text)),
        llm_router=router,
        system_prompt=SYSTEM_PROMPT,
        response_schema=CoursePlanV1,
        build_user_prompt=_build_user_prompt,
        build_repair_prompt=_build_repair_prompt,
    )

    with pytest.raises(ValueError, match="Не найден API-ключ LLM"):
        use_case.execute(ParseCourseCommand(course_id="course-1"))


def test_parse_course_use_case_surfaces_provider_rejection_message() -> None:
    raw_text = CourseRawTextRecord(
        course_id="course-1",
        raw_text_id="raw-1",
        content="Course text",
        content_hash="hash",
        length=10,
    )
    router = FakeRouter(scripted=[LLMRequestRejectedError("Provider rejected request.")])
    use_case = ParseCourseUseCase(
        uow_factory=lambda: FakeCoursePlanUow(FakeCoursePlanRepository(raw_text)),
        llm_router=router,
        system_prompt=SYSTEM_PROMPT,
        response_schema=CoursePlanV1,
        build_user_prompt=_build_user_prompt,
        build_repair_prompt=_build_repair_prompt,
    )

    with pytest.raises(ValueError, match="Provider rejected request"):
        use_case.execute(ParseCourseCommand(course_id="course-1"))


def test_parse_course_use_case_surfaces_temporary_error_message() -> None:
    raw_text = CourseRawTextRecord(
        course_id="course-1",
        raw_text_id="raw-1",
        content="Course text",
        content_hash="hash",
        length=10,
    )
    router = FakeRouter(scripted=[LLMTemporaryError("LLM service is temporarily unavailable.")])
    use_case = ParseCourseUseCase(
        uow_factory=lambda: FakeCoursePlanUow(FakeCoursePlanRepository(raw_text)),
        llm_router=router,
        system_prompt=SYSTEM_PROMPT,
        response_schema=CoursePlanV1,
        build_user_prompt=_build_user_prompt,
        build_repair_prompt=_build_repair_prompt,
    )

    with pytest.raises(ValueError, match="temporarily unavailable"):
        use_case.execute(ParseCourseCommand(course_id="course-1"))


def _success_response(llm_call_id: str) -> LLMResponse[CoursePlanV1]:
    return LLMResponse(
        llm_call_id=llm_call_id,
        provider=LLMServiceProvider.ANTHROPIC,
        model="claude-3-5-sonnet-latest",
        prompt_hash="hash",
        latency_ms=1200,
        parsed=CoursePlanV1(
            course=CoursePlanCourse(
                title="Python",
                description="Intro",
                start_date=None,
            ),
            modules=[
                CoursePlanModule(
                    order=1,
                    title="Основы",
                    goals=["Понять синтаксис"],
                    topics=["Переменные"],
                    estimated_hours=4,
                )
            ],
            deadlines=[],
        ),
        output_text="{}",
        input_tokens=100,
        output_tokens=200,
    )


def _build_user_prompt(raw_course_text: str) -> str:
    return f"Текст курса:\n{raw_course_text}"


def _build_repair_prompt(*, invalid_output: str, validation_errors: str) -> str:
    return (
        "Ошибки валидации:\n"
        f"{validation_errors}\n"
        "Невалидный ответ:\n"
        f"{invalid_output}"
    )

