"""LLM router with provider policy, retries, schema validation, and audit logging."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import TypeVar
from uuid import uuid4

import httpx
from pydantic import BaseModel, ValidationError

from praktikum_app.application.llm import (
    LLMKeyStore,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    LLMServiceProvider,
    LLMTaskType,
    ProviderCallRequest,
    ProviderCallResponse,
)
from praktikum_app.application.llm_audit import (
    LLMCallAuditRecord,
    LLMCallAuditUnitOfWorkFactory,
)
from praktikum_app.infrastructure.llm.config import (
    LLMRouterConfig,
    TaskRoute,
    default_router_config,
    validate_routing_policy,
)
from praktikum_app.infrastructure.llm.errors import (
    LLMConfigurationError,
    LLMExecutionError,
    LLMResponseValidationError,
    LLMRetryExhaustedError,
    MissingApiKeyError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderServerError,
)
from praktikum_app.infrastructure.llm.retry import RetryExecutor

LOGGER = logging.getLogger(__name__)

TModel = TypeVar("TModel", bound=BaseModel)


class LLMRouter:
    """Route task types to providers/models with strict policy enforcement."""

    def __init__(
        self,
        *,
        providers: Mapping[LLMServiceProvider, LLMProvider],
        key_store: LLMKeyStore,
        audit_uow_factory: LLMCallAuditUnitOfWorkFactory,
        config: LLMRouterConfig | None = None,
        retry_executor: RetryExecutor | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(tz=UTC),
    ) -> None:
        resolved_config = config or default_router_config()
        validate_routing_policy(resolved_config.routes)

        self._providers = providers
        self._key_store = key_store
        self._audit_uow_factory = audit_uow_factory
        self._config = resolved_config
        self._retry_executor = retry_executor or RetryExecutor(resolved_config.retry_policy)
        self._monotonic = monotonic
        self._now = now

    def execute(self, request: LLMRequest[TModel]) -> LLMResponse[TModel]:
        """Execute routed LLM call and validate output against request schema."""
        route = self._resolve_route(request.task_type)
        provider = self._providers.get(route.provider)
        if provider is None:
            raise LLMConfigurationError(
                f"Provider client is not configured: {route.provider.value}"
            )

        api_key = self._key_store.get_key(route.provider)
        if not api_key:
            raise MissingApiKeyError(f"Missing API key for provider {route.provider.value}.")

        llm_call_id = str(uuid4())
        prompt_hash = _compute_prompt_hash(request.system_prompt, request.user_prompt)
        started = self._monotonic()
        provider_response: ProviderCallResponse | None = None

        try:
            provider_response = self._retry_executor.run(
                lambda: provider.generate(
                    ProviderCallRequest(
                        model=route.model,
                        api_key=api_key,
                        system_prompt=request.system_prompt,
                        user_prompt=request.user_prompt,
                        max_output_tokens=request.max_output_tokens,
                        temperature=request.temperature,
                        timeout_seconds=self._config.timeout_seconds,
                    )
                )
            )
            latency_ms = _compute_latency_ms(started, self._monotonic())
            parsed = _parse_schema(
                request.response_schema,
                provider_response.output_text,
                llm_call_id=llm_call_id,
            )
        except LLMResponseValidationError as exc:
            latency_ms = _compute_latency_ms(started, self._monotonic())
            self._persist_audit(
                llm_call_id=llm_call_id,
                route=route,
                prompt_hash=prompt_hash,
                status="schema_invalid",
                latency_ms=latency_ms,
                input_tokens=provider_response.input_tokens if provider_response else None,
                output_tokens=provider_response.output_tokens if provider_response else None,
                course_id=request.course_id,
                module_id=request.module_id,
                correlation_id=request.correlation_id,
            )
            LOGGER.warning(
                (
                    "event=llm_call_schema_invalid correlation_id=%s course_id=%s module_id=%s "
                    "llm_call_id=%s provider=%s model=%s prompt_hash=%s latency_ms=%s error_type=%s"
                ),
                request.correlation_id,
                request.course_id or "-",
                request.module_id or "-",
                llm_call_id,
                route.provider.value,
                route.model,
                prompt_hash,
                latency_ms,
                exc.__class__.__name__,
            )
            raise
        except (
            LLMRetryExhaustedError,
            ProviderRateLimitError,
            ProviderServerError,
            httpx.TimeoutException,
            httpx.TransportError,
        ) as exc:
            latency_ms = _compute_latency_ms(started, self._monotonic())
            self._persist_audit(
                llm_call_id=llm_call_id,
                route=route,
                prompt_hash=prompt_hash,
                status="provider_unavailable",
                latency_ms=latency_ms,
                input_tokens=provider_response.input_tokens if provider_response else None,
                output_tokens=provider_response.output_tokens if provider_response else None,
                course_id=request.course_id,
                module_id=request.module_id,
                correlation_id=request.correlation_id,
            )
            LOGGER.warning(
                (
                    "event=llm_call_provider_unavailable "
                    "correlation_id=%s course_id=%s module_id=%s "
                    "llm_call_id=%s provider=%s model=%s prompt_hash=%s latency_ms=%s error_type=%s"
                ),
                request.correlation_id,
                request.course_id or "-",
                request.module_id or "-",
                llm_call_id,
                route.provider.value,
                route.model,
                prompt_hash,
                latency_ms,
                exc.__class__.__name__,
            )
            raise LLMExecutionError(
                "LLM сервис временно недоступен. Повторите попытку позже."
            ) from exc
        except ProviderRequestError as exc:
            latency_ms = _compute_latency_ms(started, self._monotonic())
            self._persist_audit(
                llm_call_id=llm_call_id,
                route=route,
                prompt_hash=prompt_hash,
                status="provider_rejected",
                latency_ms=latency_ms,
                input_tokens=provider_response.input_tokens if provider_response else None,
                output_tokens=provider_response.output_tokens if provider_response else None,
                course_id=request.course_id,
                module_id=request.module_id,
                correlation_id=request.correlation_id,
            )
            LOGGER.warning(
                (
                    "event=llm_call_provider_rejected correlation_id=%s course_id=%s module_id=%s "
                    "llm_call_id=%s provider=%s model=%s prompt_hash=%s latency_ms=%s error_type=%s"
                ),
                request.correlation_id,
                request.course_id or "-",
                request.module_id or "-",
                llm_call_id,
                route.provider.value,
                route.model,
                prompt_hash,
                latency_ms,
                exc.__class__.__name__,
            )
            raise LLMExecutionError(
                "LLM-запрос отклонен провайдером. Проверьте модель и API ключ."
            ) from exc

        self._persist_audit(
            llm_call_id=llm_call_id,
            route=route,
            prompt_hash=prompt_hash,
            status="success",
            latency_ms=latency_ms,
            input_tokens=provider_response.input_tokens,
            output_tokens=provider_response.output_tokens,
            course_id=request.course_id,
            module_id=request.module_id,
            correlation_id=request.correlation_id,
        )
        LOGGER.info(
            (
                "event=llm_call_success correlation_id=%s course_id=%s module_id=%s llm_call_id=%s "
                "provider=%s model=%s prompt_hash=%s latency_ms=%s input_tokens=%s output_tokens=%s"
            ),
            request.correlation_id,
            request.course_id or "-",
            request.module_id or "-",
            llm_call_id,
            route.provider.value,
            route.model,
            prompt_hash,
            latency_ms,
            provider_response.input_tokens,
            provider_response.output_tokens,
        )
        return LLMResponse(
            llm_call_id=llm_call_id,
            provider=route.provider,
            model=route.model,
            prompt_hash=prompt_hash,
            latency_ms=latency_ms,
            parsed=parsed,
            output_text=provider_response.output_text,
            input_tokens=provider_response.input_tokens,
            output_tokens=provider_response.output_tokens,
        )

    def _resolve_route(self, task_type: LLMTaskType) -> TaskRoute:
        route = self._config.routes.get(task_type)
        if route is None:
            raise LLMConfigurationError(
                f"Route is not configured for task type {task_type.value}."
            )
        return route

    def _persist_audit(
        self,
        *,
        llm_call_id: str,
        route: TaskRoute,
        prompt_hash: str,
        status: str,
        latency_ms: int | None,
        input_tokens: int | None,
        output_tokens: int | None,
        course_id: str | None,
        module_id: str | None,
        correlation_id: str,
    ) -> None:
        record = LLMCallAuditRecord(
            llm_call_id=llm_call_id,
            provider=route.provider,
            model=route.model,
            prompt_hash=prompt_hash,
            status=status,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            course_id=course_id,
            module_id=module_id,
            created_at=self._now(),
        )
        try:
            with self._audit_uow_factory() as uow:
                uow.llm_calls.save_call(record)
                uow.commit()
        except Exception as exc:
            LOGGER.exception(
                (
                    "event=llm_audit_persist_failed correlation_id=%s course_id=%s module_id=%s "
                    "llm_call_id=%s provider=%s model=%s prompt_hash=%s status=%s error_type=%s"
                ),
                correlation_id,
                course_id or "-",
                module_id or "-",
                llm_call_id,
                route.provider.value,
                route.model,
                prompt_hash,
                status,
                exc.__class__.__name__,
            )


def _compute_prompt_hash(system_prompt: str, user_prompt: str) -> str:
    digest = hashlib.sha256()
    digest.update(system_prompt.encode("utf-8"))
    digest.update(b"\n---\n")
    digest.update(user_prompt.encode("utf-8"))
    return digest.hexdigest()


def _compute_latency_ms(started: float, now: float) -> int:
    return max(0, int((now - started) * 1000))


def _parse_schema(
    schema: type[TModel],
    output_text: str,
    *,
    llm_call_id: str,
) -> TModel:
    try:
        return schema.model_validate_json(output_text)
    except ValidationError as exc:
        repair_prompt = _build_repair_prompt(
            schema=schema,
            invalid_output=output_text,
            validation_error=exc,
        )
        raise LLMResponseValidationError(
            "LLM output failed schema validation.",
            repair_prompt=repair_prompt,
            llm_call_id=llm_call_id,
        ) from exc


def _build_repair_prompt(
    *,
    schema: type[BaseModel],
    invalid_output: str,
    validation_error: ValidationError,
) -> str:
    schema_json = json.dumps(
        schema.model_json_schema(),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    return (
        "Исправь ответ строго под JSON-схему.\n"
        "Верни только валидный JSON без пояснений.\n\n"
        "JSON schema:\n"
        f"{schema_json}\n\n"
        "Validation errors:\n"
        f"{validation_error}\n\n"
        "Original invalid output:\n"
        f"{invalid_output}"
    )
