"""Use-case tests for practice generation with repair loop and safety checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType

import pytest

from praktikum_app.application.llm import (
    LLMRequest,
    LLMResponse,
    LLMResponseSchemaError,
    LLMServiceProvider,
    LLMTemporaryError,
    MissingApiKeyLLMError,
)
from praktikum_app.application.practice_generation import (
    GeneratePracticeCommand,
    GeneratePracticeUseCase,
    LLMRouterPort,
    PracticeModuleContext,
    PracticeModuleSummary,
    PracticeRepository,
    PracticeTaskDraft,
    PracticeUnitOfWork,
)
from praktikum_app.domain.practice import (
    PracticeDifficulty,
    PracticeGenerationCandidateV1,
    PracticeGenerationV1,
    PracticeTask,
)

SYSTEM_PROMPT = "practice-system"


class FakePracticeRepository(PracticeRepository):
    """Practice repository fake with in-memory generated task history."""

    def __init__(self, module_context: PracticeModuleContext | None) -> None:
        self._module_context = module_context
        self._history: list[PracticeTask] = []

    def get_module_context(self, module_id: str) -> PracticeModuleContext | None:
        if self._module_context is None:
            return None
        if self._module_context.module_id != module_id:
            return None
        return self._module_context

    def list_modules_for_course(self, course_id: str) -> list[PracticeModuleSummary]:
        if self._module_context is None:
            return []
        if self._module_context.course_id != course_id:
            return []
        return [
            PracticeModuleSummary(
                module_id=self._module_context.module_id,
                course_id=self._module_context.course_id,
                module_order=self._module_context.module_order,
                module_title=self._module_context.module_title,
            )
        ]

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
        saved_tasks: list[PracticeTask] = []
        for candidate in candidates:
            task = PracticeTask(
                id=f"task-{generation_id}-{candidate.candidate_index}",
                course_id=module_context.course_id,
                module_id=module_context.module_id,
                difficulty=difficulty,
                statement=candidate.statement,
                expected_outline=candidate.expected_outline,
                candidate_index=candidate.candidate_index,
                created_at=created_at,
                generation_id=generation_id,
                llm_call_id=llm_call_id,
            )
            saved_tasks.append(task)

        self._history.extend(saved_tasks)
        return saved_tasks

    def get_current_task(self, module_id: str) -> PracticeTask | None:
        history = [task for task in self._history if task.module_id == module_id]
        if not history:
            return None

        latest_generation_id = history[-1].generation_id
        latest_batch = [task for task in history if task.generation_id == latest_generation_id]
        latest_batch.sort(key=lambda task: task.candidate_index)
        return latest_batch[0]

    def list_task_history(self, module_id: str) -> list[PracticeTask]:
        history = [task for task in self._history if task.module_id == module_id]
        return sorted(
            history,
            key=lambda task: (task.created_at, -task.candidate_index),
            reverse=True,
        )


class FakePracticeUnitOfWork(PracticeUnitOfWork):
    """Minimal UoW fake for practice use-case tests."""

    def __init__(self, repository: PracticeRepository) -> None:
        self.practice = repository
        self.committed = False

    def __enter__(self) -> FakePracticeUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        return None


@dataclass
class FakeRouter(LLMRouterPort):
    """Scripted router that returns responses/exceptions in sequence."""

    scripted: list[LLMResponse[PracticeGenerationV1] | Exception]

    def __post_init__(self) -> None:
        self.requests: list[LLMRequest[PracticeGenerationV1]] = []

    def execute(
        self,
        request: LLMRequest[PracticeGenerationV1],
    ) -> LLMResponse[PracticeGenerationV1]:
        self.requests.append(request)
        step = self.scripted.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def test_generate_practice_use_case_success_path() -> None:
    module_context = _module_context()
    repository = FakePracticeRepository(module_context)
    uow = FakePracticeUnitOfWork(repository)
    router = FakeRouter(scripted=[_success_response(llm_call_id="llm-call-1", count=3)])
    use_case = _make_use_case(uow=uow, router=router)

    result = use_case.execute(
        GeneratePracticeCommand(
            module_id=module_context.module_id,
            difficulty=PracticeDifficulty.MEDIUM,
            candidate_count=3,
        )
    )

    assert result.generated_count == 3
    assert result.history_count == 3
    assert result.current_task.candidate_index == 1
    assert result.current_task.llm_call_id == "llm-call-1"
    assert result.llm_call_id == "llm-call-1"
    assert result.attempts == 1
    assert len(router.requests) == 1


def test_generate_practice_use_case_repairs_invalid_output_then_succeeds() -> None:
    module_context = _module_context()
    repository = FakePracticeRepository(module_context)
    uow = FakePracticeUnitOfWork(repository)
    router = FakeRouter(
        scripted=[
            LLMResponseSchemaError(
                "invalid",
                llm_call_id="llm-call-invalid",
                repair_prompt="repair",
                invalid_output="{}",
                validation_errors="field required",
            ),
            _success_response(llm_call_id="llm-call-2", count=2),
        ]
    )
    use_case = _make_use_case(uow=uow, router=router)

    result = use_case.execute(
        GeneratePracticeCommand(
            module_id=module_context.module_id,
            difficulty=PracticeDifficulty.EASY,
            candidate_count=2,
            max_repair_attempts=2,
        )
    )

    assert result.generated_count == 2
    assert result.attempts == 2
    assert len(router.requests) == 2
    assert "Ошибки валидации" in router.requests[1].user_prompt


def test_generate_practice_use_case_fails_when_repair_budget_exhausted() -> None:
    module_context = _module_context()
    repository = FakePracticeRepository(module_context)
    uow = FakePracticeUnitOfWork(repository)
    router = FakeRouter(
        scripted=[
            LLMResponseSchemaError(
                "invalid",
                llm_call_id="llm-call-invalid-1",
                repair_prompt="repair",
                invalid_output="{}",
                validation_errors="field required",
            ),
            LLMResponseSchemaError(
                "invalid",
                llm_call_id="llm-call-invalid-2",
                repair_prompt="repair",
                invalid_output="{}",
                validation_errors="field required",
            ),
        ]
    )
    use_case = _make_use_case(uow=uow, router=router)

    with pytest.raises(ValueError, match="Не удалось сформировать корректное практическое задание"):
        use_case.execute(
            GeneratePracticeCommand(
                module_id=module_context.module_id,
                difficulty=PracticeDifficulty.HARD,
                candidate_count=2,
                max_repair_attempts=1,
            )
        )

    assert len(router.requests) == 2


def test_generate_practice_use_case_fails_when_module_context_missing() -> None:
    repository = FakePracticeRepository(module_context=None)
    uow = FakePracticeUnitOfWork(repository)
    router = FakeRouter(scripted=[])
    use_case = _make_use_case(uow=uow, router=router)

    with pytest.raises(ValueError, match="Не удалось найти выбранный модуль"):
        use_case.execute(
            GeneratePracticeCommand(
                module_id="missing-module",
                difficulty=PracticeDifficulty.MEDIUM,
                candidate_count=2,
            )
        )


def test_generate_practice_use_case_fails_when_api_key_missing() -> None:
    module_context = _module_context()
    repository = FakePracticeRepository(module_context)
    uow = FakePracticeUnitOfWork(repository)
    router = FakeRouter(scripted=[MissingApiKeyLLMError("no key")])
    use_case = _make_use_case(uow=uow, router=router)

    with pytest.raises(ValueError, match="Не найден API-ключ LLM"):
        use_case.execute(
            GeneratePracticeCommand(
                module_id=module_context.module_id,
                difficulty=PracticeDifficulty.MEDIUM,
                candidate_count=2,
            )
        )


def test_generate_practice_use_case_fails_on_temporary_llm_error() -> None:
    module_context = _module_context()
    repository = FakePracticeRepository(module_context)
    uow = FakePracticeUnitOfWork(repository)
    router = FakeRouter(
        scripted=[LLMTemporaryError("LLM сервис временно недоступен. Повторите попытку позже.")]
    )
    use_case = _make_use_case(uow=uow, router=router)

    with pytest.raises(ValueError, match="LLM сервис временно недоступен"):
        use_case.execute(
            GeneratePracticeCommand(
                module_id=module_context.module_id,
                difficulty=PracticeDifficulty.MEDIUM,
                candidate_count=2,
            )
        )


def test_generate_practice_use_case_fails_when_candidates_count_is_insufficient() -> None:
    module_context = _module_context()
    repository = FakePracticeRepository(module_context)
    uow = FakePracticeUnitOfWork(repository)
    router = FakeRouter(scripted=[_success_response(llm_call_id="llm-call-3", count=1)])
    use_case = _make_use_case(uow=uow, router=router)

    with pytest.raises(ValueError, match="нужное количество вариантов"):
        use_case.execute(
            GeneratePracticeCommand(
                module_id=module_context.module_id,
                difficulty=PracticeDifficulty.MEDIUM,
                candidate_count=2,
                max_repair_attempts=0,
            )
        )


def _make_use_case(*, uow: FakePracticeUnitOfWork, router: FakeRouter) -> GeneratePracticeUseCase:
    return GeneratePracticeUseCase(
        uow_factory=lambda: uow,
        llm_router=router,
        system_prompt=SYSTEM_PROMPT,
        response_schema=PracticeGenerationV1,
        build_user_prompt=_build_user_prompt,
        build_repair_prompt=_build_repair_prompt,
    )


def _build_user_prompt(
    module_context: PracticeModuleContext,
    difficulty: PracticeDifficulty,
    candidate_count: int,
) -> str:
    return (
        f"module={module_context.module_title};"
        f"difficulty={difficulty.value};"
        f"count={candidate_count}"
    )


def _build_repair_prompt(
    *,
    invalid_output: str,
    validation_errors: str,
    candidate_count: int,
) -> str:
    return (
        "Ошибки валидации:\n"
        f"{validation_errors}\n"
        f"Нужно кандидатов: {candidate_count}\n"
        "Невалидный ответ:\n"
        f"{invalid_output}"
    )


def _module_context() -> PracticeModuleContext:
    return PracticeModuleContext(
        module_id="module-1",
        course_id="course-1",
        course_title="Python Advanced",
        module_title="Асинхронность",
        module_order=2,
        goals=["Понять event loop"],
        topics=["async", "await"],
        estimated_hours=6,
    )


def _success_response(llm_call_id: str, count: int) -> LLMResponse[PracticeGenerationV1]:
    candidates: list[PracticeGenerationCandidateV1] = []
    for index in range(1, count + 1):
        candidates.append(
            PracticeGenerationCandidateV1(
                statement=f"Задание {index}",
                expected_outline=f"План решения {index}",
            )
        )

    return LLMResponse(
        llm_call_id=llm_call_id,
        provider=LLMServiceProvider.OPENROUTER,
        model="openai/gpt-4o-mini",
        prompt_hash="hash",
        latency_ms=850,
        parsed=PracticeGenerationV1(
            module_title="Асинхронность",
            difficulty=PracticeDifficulty.MEDIUM,
            candidates=candidates,
        ),
        output_text='{"ok":true}',
        input_tokens=120,
        output_tokens=320,
    )
