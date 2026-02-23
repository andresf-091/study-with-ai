"""Keyring-backed API key storage adapter."""

from __future__ import annotations

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from praktikum_app.application.llm import LLMKeyStore, LLMServiceProvider


class KeyringStoreError(RuntimeError):
    """Raised when keyring backend operation fails."""


class KeyringApiKeyStore(LLMKeyStore):
    """Store provider keys using OS keyring backend."""

    def __init__(self, service_name: str = "study-with-ai") -> None:
        self._service_name = service_name

    def set_key(self, provider: LLMServiceProvider, api_key: str) -> None:
        """Persist API key for provider."""
        normalized = api_key.strip()
        if not normalized:
            raise ValueError("api_key must not be empty")

        username = self._username(provider)
        try:
            keyring.set_password(self._service_name, username, normalized)
        except KeyringError as exc:
            raise KeyringStoreError(
                f"Failed to persist key for provider {provider.value}."
            ) from exc

    def get_key(self, provider: LLMServiceProvider) -> str | None:
        """Load provider API key or return None."""
        username = self._username(provider)
        try:
            secret = keyring.get_password(self._service_name, username)
        except KeyringError as exc:
            raise KeyringStoreError(f"Failed to read key for provider {provider.value}.") from exc

        return secret if secret else None

    def delete_key(self, provider: LLMServiceProvider) -> None:
        """Delete provider key; no-op if key is already absent."""
        username = self._username(provider)
        try:
            keyring.delete_password(self._service_name, username)
        except PasswordDeleteError:
            return
        except KeyringError as exc:
            raise KeyringStoreError(
                f"Failed to delete key for provider {provider.value}."
            ) from exc

    @staticmethod
    def _username(provider: LLMServiceProvider) -> str:
        return f"llm:{provider.value}"
