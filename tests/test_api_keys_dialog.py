"""UI tests for API keys dialog with fake key store."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton

from praktikum_app.application.llm import LLMKeyStore, LLMServiceProvider
from praktikum_app.presentation.qt.api_keys_dialog import ApiKeysDialog


class FakeKeyStore(LLMKeyStore):
    """Simple in-memory key store for UI tests."""

    def __init__(self) -> None:
        self.values: dict[LLMServiceProvider, str] = {}

    def set_key(self, provider: LLMServiceProvider, api_key: str) -> None:
        self.values[provider] = api_key

    def get_key(self, provider: LLMServiceProvider) -> str | None:
        return self.values.get(provider)

    def delete_key(self, provider: LLMServiceProvider) -> None:
        self.values.pop(provider, None)


def test_api_keys_dialog_save_and_delete_flow(application: QApplication) -> None:
    store = FakeKeyStore()
    dialog = ApiKeysDialog(store)

    anthropic_input = dialog.findChild(QLineEdit, "anthropicApiKeyInput")
    anthropic_save = dialog.findChild(QPushButton, "anthropicSaveButton")
    anthropic_delete = dialog.findChild(QPushButton, "anthropicDeleteButton")
    anthropic_status = dialog.findChild(QLabel, "anthropicApiKeyStatus")

    assert anthropic_input is not None
    assert anthropic_save is not None
    assert anthropic_delete is not None
    assert anthropic_status is not None
    assert anthropic_status.text() == "Не задан"

    anthropic_input.setText("secret-anthropic-key")
    anthropic_save.click()

    assert store.get_key(LLMServiceProvider.ANTHROPIC) == "secret-anthropic-key"
    assert anthropic_status.text() == "Сохранён"

    anthropic_delete.click()
    assert store.get_key(LLMServiceProvider.ANTHROPIC) is None
    assert anthropic_status.text() == "Не задан"
