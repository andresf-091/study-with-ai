"""Unit tests for keyring API key adapter."""

from __future__ import annotations

import keyring
import pytest
from keyring.errors import KeyringError

from praktikum_app.application.llm import LLMServiceProvider
from praktikum_app.infrastructure.security.keyring_store import (
    KeyringApiKeyStore,
    KeyringStoreError,
)


def test_keyring_store_set_get_delete_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    memory: dict[tuple[str, str], str] = {}

    def fake_set_password(service: str, username: str, password: str) -> None:
        memory[(service, username)] = password

    def fake_get_password(service: str, username: str) -> str | None:
        return memory.get((service, username))

    def fake_delete_password(service: str, username: str) -> None:
        memory.pop((service, username), None)

    monkeypatch.setattr(keyring, "set_password", fake_set_password)
    monkeypatch.setattr(keyring, "get_password", fake_get_password)
    monkeypatch.setattr(keyring, "delete_password", fake_delete_password)

    store = KeyringApiKeyStore(service_name="test-service")
    provider = LLMServiceProvider.ANTHROPIC

    store.set_key(provider, "secret-key")
    assert store.get_key(provider) == "secret-key"

    store.delete_key(provider)
    assert store.get_key(provider) is None


def test_keyring_store_raises_on_backend_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_set_password(_: str, __: str, ___: str) -> None:
        raise KeyringError("backend down")

    monkeypatch.setattr(keyring, "set_password", failing_set_password)

    store = KeyringApiKeyStore(service_name="test-service")
    with pytest.raises(KeyringStoreError):
        store.set_key(LLMServiceProvider.OPENROUTER, "secret")
