"""Tests for LLM router policy, schema validation, retries, and audit writes."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from praktikum_app.application.llm import (
    LLMKeyStore,
    LLMProvider,
    LLMRequest,
    LLMRequestRejectedError,
    LLMServiceProvider,
    LLMTaskType,
    ProviderCallRequest,
    ProviderCallResponse,
)
from praktikum_app.application.llm_audit import (
    LLMCallAuditRecord,
    LLMCallAuditRepository,
    LLMCallAuditUnitOfWork,
)
from praktikum_app.infrastructure.llm.config import LLMRouterConfig, TaskRoute, default_routes
from praktikum_app.infrastructure.llm.errors import (
    LLMConfigurationError,
    LLMExecutionError,
    LLMResponseValidationError,
    MissingApiKeyError,
    ProviderRateLimitError,
    ProviderRequestError,
)
from praktikum_app.infrastructure.llm.retry import RetryExecutor, RetryPolicy
from praktikum_app.infrastructure.llm.router import LLMRouter


class ParsedResponseSchema(BaseModel):
    """Expected response schema for router tests."""

    model_config = ConfigDict(extra="forbid")

    answer: str


class InMemoryKeyStore(LLMKeyStore):
    """Simple in-memory key store for tests."""

    def __init__(self, initial: dict[LLMServiceProvider, str] | None = None) -> None:
        self._keys = dict(initial or {})

    def set_key(self, provider: LLMServiceProvider, api_key: str) -> None:
        self._keys[provider] = api_key

    def get_key(self, provider: LLMServiceProvider) -> str | None:
        return self._keys.get(provider)

    def delete_key(self, provider: LLMServiceProvider) -> None:
        self._keys.pop(provider, None)


class InMemoryAuditRepository(LLMCallAuditRepository):
    """Store audit records in-memory for deterministic assertions."""

    def __init__(self) -> None:
        self.records: list[LLMCallAuditRecord] = []

    def save_call(self, record: LLMCallAuditRecord) -> None:
        self.records.append(record)


class InMemoryAuditUnitOfWork(LLMCallAuditUnitOfWork):
    """Minimal UoW wrapper around in-memory audit repository."""

    def __init__(self, repository: InMemoryAuditRepository) -> None:
        self.llm_calls: LLMCallAuditRepository = repository

    def __enter__(self) -> InMemoryAuditUnitOfWork:
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


class SequenceProvider(LLMProvider):
    """Provider stub that returns/raises values from a sequence."""

    def __init__(
        self,
        provider: LLMServiceProvider,
        sequence: list[ProviderCallResponse | Exception],
    ) -> None:
        self._provider = provider
        self._sequence = sequence
        self.calls = 0

    @property
    def provider(self) -> LLMServiceProvider:
        return self._provider

    def generate(self, request: ProviderCallRequest) -> ProviderCallResponse:
        self.calls += 1
        assert request.api_key
        if not self._sequence:
            raise RuntimeError("No scripted responses left")

        step = self._sequence.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def test_router_routes_course_parse_to_anthropic() -> None:
    anthropic = SequenceProvider(
        LLMServiceProvider.ANTHROPIC,
        [ProviderCallResponse('{"answer":"ok"}', 12, 4)],
    )
    openrouter = SequenceProvider(LLMServiceProvider.OPENROUTER, [])
    audit_repo = InMemoryAuditRepository()
    router = _make_router(
        anthropic=anthropic,
        openrouter=openrouter,
        audit_repo=audit_repo,
    )

    response = router.execute(_make_request(task_type=LLMTaskType.COURSE_PARSE))

    assert response.provider is LLMServiceProvider.ANTHROPIC
    assert response.parsed.answer == "ok"
    assert anthropic.calls == 1
    assert openrouter.calls == 0
    assert audit_repo.records[-1].status == "success"
    assert audit_repo.records[-1].task_type is LLMTaskType.COURSE_PARSE


def test_router_routes_curator_msg_to_openrouter() -> None:
    anthropic = SequenceProvider(LLMServiceProvider.ANTHROPIC, [])
    openrouter = SequenceProvider(
        LLMServiceProvider.OPENROUTER,
        [ProviderCallResponse('{"answer":"ok"}', 8, 3)],
    )
    audit_repo = InMemoryAuditRepository()
    router = _make_router(
        anthropic=anthropic,
        openrouter=openrouter,
        audit_repo=audit_repo,
    )

    response = router.execute(_make_request(task_type=LLMTaskType.CURATOR_MSG))

    assert response.provider is LLMServiceProvider.OPENROUTER
    assert response.parsed.answer == "ok"
    assert anthropic.calls == 0
    assert openrouter.calls == 1
    assert audit_repo.records[-1].status == "success"
    assert audit_repo.records[-1].task_type is LLMTaskType.CURATOR_MSG


def test_router_raises_when_provider_key_missing() -> None:
    anthropic = SequenceProvider(
        LLMServiceProvider.ANTHROPIC,
        [ProviderCallResponse('{"answer":"ok"}', 1, 1)],
    )
    openrouter = SequenceProvider(LLMServiceProvider.OPENROUTER, [])
    audit_repo = InMemoryAuditRepository()
    router = _make_router(
        anthropic=anthropic,
        openrouter=openrouter,
        audit_repo=audit_repo,
        key_store=InMemoryKeyStore(initial={}),
    )

    with pytest.raises(MissingApiKeyError):
        router.execute(_make_request(task_type=LLMTaskType.COURSE_PARSE))

    assert audit_repo.records == []


def test_router_rejects_policy_violation_in_config() -> None:
    anthropic = SequenceProvider(LLMServiceProvider.ANTHROPIC, [])
    openrouter = SequenceProvider(LLMServiceProvider.OPENROUTER, [])
    audit_repo = InMemoryAuditRepository()

    bad_routes = default_routes()
    bad_routes[LLMTaskType.COURSE_PARSE] = TaskRoute(
        provider=LLMServiceProvider.OPENROUTER,
        model="openai/gpt-4o-mini",
    )

    with pytest.raises(LLMConfigurationError):
        LLMRouter(
            providers={
                LLMServiceProvider.ANTHROPIC: anthropic,
                LLMServiceProvider.OPENROUTER: openrouter,
            },
            key_store=InMemoryKeyStore(
                initial={
                    LLMServiceProvider.ANTHROPIC: "anthropic-key",
                    LLMServiceProvider.OPENROUTER: "openrouter-key",
                }
            ),
            audit_uow_factory=lambda: InMemoryAuditUnitOfWork(audit_repo),
            config=LLMRouterConfig(routes=bad_routes),
        )


def test_router_marks_schema_invalid_and_exposes_repair_prompt() -> None:
    anthropic = SequenceProvider(
        LLMServiceProvider.ANTHROPIC,
        [ProviderCallResponse('{"unexpected":"field"}', 11, 2)],
    )
    openrouter = SequenceProvider(LLMServiceProvider.OPENROUTER, [])
    audit_repo = InMemoryAuditRepository()
    router = _make_router(
        anthropic=anthropic,
        openrouter=openrouter,
        audit_repo=audit_repo,
    )

    with pytest.raises(LLMResponseValidationError) as exc_info:
        router.execute(_make_request(task_type=LLMTaskType.COURSE_PARSE))

    assert "JSON schema" in exc_info.value.repair_prompt
    assert audit_repo.records[-1].status == "schema_invalid"


def test_router_marks_malformed_json_as_schema_invalid() -> None:
    anthropic = SequenceProvider(
        LLMServiceProvider.ANTHROPIC,
        [ProviderCallResponse("not-json", 11, 2)],
    )
    openrouter = SequenceProvider(LLMServiceProvider.OPENROUTER, [])
    audit_repo = InMemoryAuditRepository()
    router = _make_router(
        anthropic=anthropic,
        openrouter=openrouter,
        audit_repo=audit_repo,
    )

    with pytest.raises(LLMResponseValidationError):
        router.execute(_make_request(task_type=LLMTaskType.COURSE_PARSE))

    assert audit_repo.records[-1].status == "schema_invalid"


def test_router_parses_markdown_fenced_json_output() -> None:
    anthropic = SequenceProvider(
        LLMServiceProvider.ANTHROPIC,
        [ProviderCallResponse('```json\n{"answer":"ok"}\n```', 11, 2)],
    )
    openrouter = SequenceProvider(LLMServiceProvider.OPENROUTER, [])
    audit_repo = InMemoryAuditRepository()
    router = _make_router(
        anthropic=anthropic,
        openrouter=openrouter,
        audit_repo=audit_repo,
    )

    response = router.execute(_make_request(task_type=LLMTaskType.COURSE_PARSE))

    assert response.parsed.answer == "ok"
    assert audit_repo.records[-1].status == "success"
    assert audit_repo.records[-1].output_hash is not None
    assert audit_repo.records[-1].output_length == len('```json\n{"answer":"ok"}\n```')


def test_router_retries_timeout_then_succeeds() -> None:
    anthropic = SequenceProvider(
        LLMServiceProvider.ANTHROPIC,
        [
            httpx.ReadTimeout("timeout"),
            ProviderCallResponse('{"answer":"ok"}', 10, 5),
        ],
    )
    openrouter = SequenceProvider(LLMServiceProvider.OPENROUTER, [])
    audit_repo = InMemoryAuditRepository()
    retry_executor = RetryExecutor(
        RetryPolicy(
            max_attempts=3,
            base_delay_seconds=0.0,
            max_delay_seconds=0.0,
            backoff_multiplier=2.0,
        ),
        sleep=lambda _: None,
    )
    router = _make_router(
        anthropic=anthropic,
        openrouter=openrouter,
        audit_repo=audit_repo,
        retry_executor=retry_executor,
    )

    response = router.execute(_make_request(task_type=LLMTaskType.COURSE_PARSE))

    assert response.parsed.answer == "ok"
    assert anthropic.calls == 2
    assert audit_repo.records[-1].status == "success"


def test_router_returns_user_safe_error_when_429_retries_exhausted() -> None:
    anthropic = SequenceProvider(
        LLMServiceProvider.ANTHROPIC,
        [
            ProviderRateLimitError("429"),
            ProviderRateLimitError("429"),
            ProviderRateLimitError("429"),
        ],
    )
    openrouter = SequenceProvider(LLMServiceProvider.OPENROUTER, [])
    audit_repo = InMemoryAuditRepository()
    retry_executor = RetryExecutor(
        RetryPolicy(
            max_attempts=3,
            base_delay_seconds=0.0,
            max_delay_seconds=0.0,
            backoff_multiplier=2.0,
        ),
        sleep=lambda _: None,
    )
    router = _make_router(
        anthropic=anthropic,
        openrouter=openrouter,
        audit_repo=audit_repo,
        retry_executor=retry_executor,
    )

    with pytest.raises(LLMExecutionError):
        router.execute(_make_request(task_type=LLMTaskType.COURSE_PARSE))

    assert anthropic.calls == 3
    assert audit_repo.records[-1].status == "provider_unavailable"


def test_router_marks_provider_rejected_and_raises_request_rejected() -> None:
    anthropic = SequenceProvider(
        LLMServiceProvider.ANTHROPIC,
        [ProviderRequestError("status=404")],
    )
    openrouter = SequenceProvider(LLMServiceProvider.OPENROUTER, [])
    audit_repo = InMemoryAuditRepository()
    router = _make_router(
        anthropic=anthropic,
        openrouter=openrouter,
        audit_repo=audit_repo,
    )

    with pytest.raises(LLMRequestRejectedError):
        router.execute(_make_request(task_type=LLMTaskType.COURSE_PARSE))

    assert anthropic.calls == 1
    assert audit_repo.records[-1].status == "provider_rejected"


def test_router_surfaces_openrouter_privacy_policy_hint() -> None:
    anthropic = SequenceProvider(LLMServiceProvider.ANTHROPIC, [])
    openrouter = SequenceProvider(
        LLMServiceProvider.OPENROUTER,
        [
            ProviderRequestError(
                "openrouter request failed with status=404. "
                "detail=No endpoints found matching your data policy "
                "(Free model publication)."
            )
        ],
    )
    audit_repo = InMemoryAuditRepository()
    router = _make_router(
        anthropic=anthropic,
        openrouter=openrouter,
        audit_repo=audit_repo,
    )

    with pytest.raises(LLMRequestRejectedError, match="privacy policy"):
        router.execute(_make_request(task_type=LLMTaskType.CURATOR_MSG))

    assert openrouter.calls == 1
    assert audit_repo.records[-1].status == "provider_rejected"
    assert audit_repo.records[-1].task_type is LLMTaskType.CURATOR_MSG


def _make_router(
    *,
    anthropic: SequenceProvider,
    openrouter: SequenceProvider,
    audit_repo: InMemoryAuditRepository,
    key_store: InMemoryKeyStore | None = None,
    retry_executor: RetryExecutor | None = None,
) -> LLMRouter:
    return LLMRouter(
        providers={
            LLMServiceProvider.ANTHROPIC: anthropic,
            LLMServiceProvider.OPENROUTER: openrouter,
        },
        key_store=key_store
        or InMemoryKeyStore(
            initial={
                LLMServiceProvider.ANTHROPIC: "anthropic-key",
                LLMServiceProvider.OPENROUTER: "openrouter-key",
            }
        ),
        audit_uow_factory=lambda: InMemoryAuditUnitOfWork(audit_repo),
        retry_executor=retry_executor,
        now=lambda: datetime(2026, 2, 22, 19, 0, tzinfo=UTC),
    )


def _make_request(task_type: LLMTaskType) -> LLMRequest[ParsedResponseSchema]:
    return LLMRequest(
        task_type=task_type,
        system_prompt="Return JSON.",
        user_prompt="Input payload",
        response_schema=ParsedResponseSchema,
        correlation_id="corr-1",
        course_id="course-1",
        module_id=None,
    )
