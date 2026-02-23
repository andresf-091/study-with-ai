"""HTTP clients for Anthropic and OpenRouter behind a unified DTO contract."""

from __future__ import annotations

from typing import cast

import httpx

from praktikum_app.application.llm import (
    LLMProvider,
    LLMServiceProvider,
    ProviderCallRequest,
    ProviderCallResponse,
)
from praktikum_app.infrastructure.llm.errors import (
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderResponseError,
    ProviderServerError,
)


class AnthropicClient(LLMProvider):
    """Anthropic Messages API adapter."""

    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        base_url: str = "https://api.anthropic.com",
    ) -> None:
        self._http_client = http_client or httpx.Client(base_url=base_url)
        self._owns_client = http_client is None

    @property
    def provider(self) -> LLMServiceProvider:
        """Return provider identity."""
        return LLMServiceProvider.ANTHROPIC

    def close(self) -> None:
        """Close owned HTTP client."""
        if self._owns_client:
            self._http_client.close()

    def generate(self, request: ProviderCallRequest) -> ProviderCallResponse:
        """Execute one Anthropic messages call."""
        payload: dict[str, object] = {
            "model": request.model,
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
            "system": request.system_prompt,
            "messages": [{"role": "user", "content": request.user_prompt}],
        }
        headers = {
            "x-api-key": request.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        response = self._http_client.post(
            "/v1/messages",
            headers=headers,
            json=payload,
            timeout=request.timeout_seconds,
        )
        _raise_for_status(self.provider, response)

        payload_obj = _read_json_object(response, provider=self.provider)
        output_text = _extract_anthropic_text(payload_obj)
        input_tokens, output_tokens = _extract_usage_tokens(
            payload_obj.get("usage"),
            input_key="input_tokens",
            output_key="output_tokens",
        )
        return ProviderCallResponse(
            output_text=output_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


class OpenRouterClient(LLMProvider):
    """OpenRouter chat-completions API adapter."""

    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        base_url: str = "https://openrouter.ai",
    ) -> None:
        self._http_client = http_client or httpx.Client(base_url=base_url)
        self._owns_client = http_client is None

    @property
    def provider(self) -> LLMServiceProvider:
        """Return provider identity."""
        return LLMServiceProvider.OPENROUTER

    def close(self) -> None:
        """Close owned HTTP client."""
        if self._owns_client:
            self._http_client.close()

    def generate(self, request: ProviderCallRequest) -> ProviderCallResponse:
        """Execute one OpenRouter chat-completions call."""
        payload: dict[str, object] = {
            "model": request.model,
            "temperature": request.temperature,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {request.api_key}",
            "content-type": "application/json",
        }
        response = self._http_client.post(
            "/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=request.timeout_seconds,
        )
        _raise_for_status(self.provider, response)

        payload_obj = _read_json_object(response, provider=self.provider)
        output_text = _extract_openrouter_text(payload_obj)
        input_tokens, output_tokens = _extract_usage_tokens(
            payload_obj.get("usage"),
            input_key="prompt_tokens",
            output_key="completion_tokens",
        )
        return ProviderCallResponse(
            output_text=output_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


def _raise_for_status(provider: LLMServiceProvider, response: httpx.Response) -> None:
    status_code = response.status_code
    if status_code < 400:
        return

    message = f"{provider.value} request failed with status={status_code}."
    detail = _extract_error_detail(response)
    if detail:
        message = f"{message} detail={detail}"
    if status_code == 429:
        raise ProviderRateLimitError(message)
    if 500 <= status_code <= 599:
        raise ProviderServerError(message)
    raise ProviderRequestError(message)


def _extract_error_detail(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return _truncate_error_detail(text) if text else None

    if isinstance(payload, dict):
        payload_obj = _normalize_json_object(cast(dict[object, object], payload))
        detail = _read_message_from_error_payload(payload_obj)
        if detail:
            return _truncate_error_detail(detail)

    return None


def _read_message_from_error_payload(payload: dict[str, object]) -> str | None:
    error_obj = payload.get("error")
    if isinstance(error_obj, str) and error_obj.strip():
        return error_obj.strip()

    if isinstance(error_obj, dict):
        normalized_error = _normalize_json_object(cast(dict[object, object], error_obj))
        error_message = normalized_error.get("message")
        if isinstance(error_message, str) and error_message.strip():
            return error_message.strip()
        error_type = normalized_error.get("type")
        if isinstance(error_type, str) and error_type.strip():
            return error_type.strip()

    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()

    return None


def _truncate_error_detail(value: str, *, max_length: int = 300) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[:max_length]}..."


def _read_json_object(
    response: httpx.Response,
    *,
    provider: LLMServiceProvider,
) -> dict[str, object]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderResponseError(f"{provider.value} returned invalid JSON payload.") from exc

    if not isinstance(payload, dict):
        raise ProviderResponseError(f"{provider.value} response root must be a JSON object.")
    return _normalize_json_object(cast(dict[object, object], payload))


def _extract_anthropic_text(payload: dict[str, object]) -> str:
    content = payload.get("content")
    if not isinstance(content, list):
        raise ProviderResponseError("anthropic response is missing content array.")
    content_items = cast(list[object], content)

    text_chunks: list[str] = []
    for item in content_items:
        if not isinstance(item, dict):
            continue
        item_obj = _normalize_json_object(cast(dict[object, object], item))
        item_type = item_obj.get("type")
        text = item_obj.get("text")
        if item_type == "text" and isinstance(text, str):
            text_chunks.append(text)

    combined = "".join(text_chunks).strip()
    if not combined:
        raise ProviderResponseError("anthropic response contains no text content.")
    return combined


def _extract_openrouter_text(payload: dict[str, object]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderResponseError("openrouter response is missing choices.")
    choice_items = cast(list[object], choices)

    first_choice = choice_items[0]
    if not isinstance(first_choice, dict):
        raise ProviderResponseError("openrouter first choice has unexpected type.")
    first_choice_obj = _normalize_json_object(cast(dict[object, object], first_choice))

    message = first_choice_obj.get("message")
    if not isinstance(message, dict):
        raise ProviderResponseError("openrouter first choice is missing message object.")
    message_obj = _normalize_json_object(cast(dict[object, object], message))

    content = message_obj.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ProviderResponseError("openrouter message content is empty or invalid.")
    return content


def _extract_usage_tokens(
    usage_obj: object,
    *,
    input_key: str,
    output_key: str,
) -> tuple[int | None, int | None]:
    if not isinstance(usage_obj, dict):
        return None, None
    usage = _normalize_json_object(cast(dict[object, object], usage_obj))

    return _as_optional_int(usage.get(input_key)), _as_optional_int(usage.get(output_key))


def _as_optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _normalize_json_object(value: dict[object, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for key, item in value.items():
        normalized[str(key)] = item
    return normalized
