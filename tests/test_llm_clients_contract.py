"""Contract tests for provider HTTP clients with mocked transport."""

from __future__ import annotations

import json

import httpx
import pytest

from praktikum_app.application.llm import ProviderCallRequest
from praktikum_app.infrastructure.llm.clients import AnthropicClient, OpenRouterClient
from praktikum_app.infrastructure.llm.errors import ProviderRateLimitError, ProviderRequestError


def test_anthropic_client_parses_messages_response() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        assert request.url.path == "/v1/messages"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["model"] == "claude-3-5-sonnet-latest"
        return httpx.Response(
            status_code=200,
            json={
                "content": [{"type": "text", "text": '{"answer":"ok"}'}],
                "usage": {"input_tokens": 11, "output_tokens": 4},
            },
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://api.anthropic.com")
    client = AnthropicClient(http_client=http_client)
    try:
        response = client.generate(
            ProviderCallRequest(
                model="claude-3-5-sonnet-latest",
                api_key="anthropic-key",
                system_prompt="system",
                user_prompt="user",
                max_output_tokens=512,
                temperature=0.2,
                timeout_seconds=10.0,
            )
        )
    finally:
        http_client.close()

    assert response.output_text == '{"answer":"ok"}'
    assert response.input_tokens == 11
    assert response.output_tokens == 4
    assert len(captured) == 1
    assert captured[0].headers["x-api-key"] == "anthropic-key"


def test_openrouter_client_parses_chat_completions_response() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        assert request.url.path == "/api/v1/chat/completions"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["model"] == "openai/gpt-4o-mini"
        return httpx.Response(
            status_code=200,
            json={
                "choices": [{"message": {"content": '{"answer":"ok"}'}}],
                "usage": {"prompt_tokens": 9, "completion_tokens": 3},
            },
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://openrouter.ai")
    client = OpenRouterClient(http_client=http_client)
    try:
        response = client.generate(
            ProviderCallRequest(
                model="openai/gpt-4o-mini",
                api_key="openrouter-key",
                system_prompt="system",
                user_prompt="user",
                max_output_tokens=512,
                temperature=0.3,
                timeout_seconds=10.0,
            )
        )
    finally:
        http_client.close()

    assert response.output_text == '{"answer":"ok"}'
    assert response.input_tokens == 9
    assert response.output_tokens == 3
    assert len(captured) == 1
    assert captured[0].headers["authorization"] == "Bearer openrouter-key"


def test_openrouter_client_raises_rate_limit_for_429() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=429, json={"error": "rate limit"})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://openrouter.ai")
    client = OpenRouterClient(http_client=http_client)
    try:
        with pytest.raises(ProviderRateLimitError):
            client.generate(
                ProviderCallRequest(
                    model="openai/gpt-4o-mini",
                    api_key="openrouter-key",
                    system_prompt="system",
                    user_prompt="user",
                    max_output_tokens=128,
                    temperature=0.1,
                    timeout_seconds=5.0,
                )
            )
    finally:
        http_client.close()


def test_anthropic_client_includes_error_detail_for_404() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=404,
            json={
                "error": {
                    "type": "not_found_error",
                    "message": "model not found: claude-3-5-sonnet-latest",
                }
            },
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://api.anthropic.com")
    client = AnthropicClient(http_client=http_client)
    try:
        with pytest.raises(ProviderRequestError) as exc_info:
            client.generate(
                ProviderCallRequest(
                    model="claude-3-5-sonnet-latest",
                    api_key="anthropic-key",
                    system_prompt="system",
                    user_prompt="user",
                    max_output_tokens=128,
                    temperature=0.1,
                    timeout_seconds=5.0,
                )
            )
    finally:
        http_client.close()

    assert "status=404" in str(exc_info.value)
    assert "model not found" in str(exc_info.value)
