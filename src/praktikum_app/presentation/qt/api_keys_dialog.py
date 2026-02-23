"""Dialog for configuring provider API keys in OS keyring."""

from __future__ import annotations

import logging
from uuid import uuid4

from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from praktikum_app.application.llm import LLMKeyStore, LLMServiceProvider

LOGGER = logging.getLogger(__name__)


class ApiKeysDialog(QDialog):
    """Dialog for saving and deleting API keys for supported providers."""

    def __init__(self, key_store: LLMKeyStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._key_store = key_store
        self._anthropic_input = QLineEdit(self)
        self._openrouter_input = QLineEdit(self)
        self._anthropic_status = QLabel(self)
        self._openrouter_status = QLabel(self)
        self._message_label = QLabel(self)
        self._build_ui()
        self._load_initial_state()

    def _build_ui(self) -> None:
        self.setWindowTitle("Ключи LLM")
        self.resize(680, 320)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(12)

        hint = QLabel(
            (
                "Сохраните API-ключи в системном keyring. "
                "Ключи не сохраняются в файлах приложения и не пишутся в БД."
            ),
            self,
        )
        hint.setWordWrap(True)
        root_layout.addWidget(hint)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.addWidget(QLabel("Провайдер", self), 0, 0)
        grid.addWidget(QLabel("Ключ", self), 0, 1)
        grid.addWidget(QLabel("Статус", self), 0, 2)
        grid.addWidget(QLabel("Действия", self), 0, 3)

        self._setup_row(
            grid,
            row=1,
            provider=LLMServiceProvider.ANTHROPIC,
            provider_title="Anthropic",
            input_widget=self._anthropic_input,
            status_widget=self._anthropic_status,
        )
        self._setup_row(
            grid,
            row=2,
            provider=LLMServiceProvider.OPENROUTER,
            provider_title="OpenRouter",
            input_widget=self._openrouter_input,
            status_widget=self._openrouter_status,
        )
        root_layout.addLayout(grid)

        self._message_label.setObjectName("apiKeysMessageLabel")
        self._message_label.setWordWrap(True)
        root_layout.addWidget(self._message_label)
        root_layout.addStretch(1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        close_button = QPushButton("Закрыть", self)
        close_button.setObjectName("apiKeysCloseButton")
        close_button.clicked.connect(self.accept)
        actions.addWidget(close_button)
        root_layout.addLayout(actions)

    def _setup_row(
        self,
        layout: QGridLayout,
        *,
        row: int,
        provider: LLMServiceProvider,
        provider_title: str,
        input_widget: QLineEdit,
        status_widget: QLabel,
    ) -> None:
        layout.addWidget(QLabel(provider_title, self), row, 0)

        input_widget.setEchoMode(QLineEdit.EchoMode.Password)
        input_widget.setPlaceholderText("Введите API-ключ")
        input_widget.setObjectName(f"{provider.value}ApiKeyInput")
        layout.addWidget(input_widget, row, 1)

        status_widget.setObjectName(f"{provider.value}ApiKeyStatus")
        status_widget.setText("Не задан")
        layout.addWidget(status_widget, row, 2)

        buttons = QHBoxLayout()
        save_button = QPushButton("Сохранить", self)
        save_button.setObjectName(f"{provider.value}SaveButton")
        save_button.clicked.connect(
            lambda: self._save_provider_key(
                provider=provider,
                provider_title=provider_title,
                input_widget=input_widget,
                status_widget=status_widget,
            )
        )
        delete_button = QPushButton("Удалить", self)
        delete_button.setObjectName(f"{provider.value}DeleteButton")
        delete_button.clicked.connect(
            lambda: self._delete_provider_key(
                provider=provider,
                provider_title=provider_title,
                input_widget=input_widget,
                status_widget=status_widget,
            )
        )
        buttons.addWidget(save_button)
        buttons.addWidget(delete_button)
        layout.addLayout(buttons, row, 3)

    def _load_initial_state(self) -> None:
        self._load_provider_state(
            provider=LLMServiceProvider.ANTHROPIC,
            provider_title="Anthropic",
            status_widget=self._anthropic_status,
        )
        self._load_provider_state(
            provider=LLMServiceProvider.OPENROUTER,
            provider_title="OpenRouter",
            status_widget=self._openrouter_status,
        )

    def _load_provider_state(
        self,
        *,
        provider: LLMServiceProvider,
        provider_title: str,
        status_widget: QLabel,
    ) -> None:
        correlation_id = str(uuid4())
        try:
            key = self._key_store.get_key(provider)
        except Exception as exc:
            status_widget.setText("Ошибка keyring")
            LOGGER.exception(
                (
                    "event=llm_key_load_failed correlation_id=%s course_id=- module_id=- "
                    "llm_call_id=- provider=%s error_type=%s"
                ),
                correlation_id,
                provider.value,
                exc.__class__.__name__,
            )
            QMessageBox.warning(
                self,
                "Ошибка keyring",
                f"Не удалось прочитать ключ {provider_title}. Проверьте настройки keyring.",
            )
            return

        has_key = key is not None and bool(key.strip())
        status_widget.setText("Сохранён" if has_key else "Не задан")

    def _save_provider_key(
        self,
        *,
        provider: LLMServiceProvider,
        provider_title: str,
        input_widget: QLineEdit,
        status_widget: QLabel,
    ) -> None:
        key_value = input_widget.text().strip()
        if not key_value:
            QMessageBox.warning(
                self,
                "Ключ не задан",
                f"Введите API-ключ для {provider_title} перед сохранением.",
            )
            return

        correlation_id = str(uuid4())
        try:
            self._key_store.set_key(provider, key_value)
        except Exception as exc:
            LOGGER.exception(
                (
                    "event=llm_key_save_failed correlation_id=%s course_id=- module_id=- "
                    "llm_call_id=- provider=%s error_type=%s"
                ),
                correlation_id,
                provider.value,
                exc.__class__.__name__,
            )
            QMessageBox.warning(
                self,
                "Ошибка keyring",
                f"Не удалось сохранить ключ {provider_title}. Проверьте настройки keyring.",
            )
            return

        input_widget.clear()
        status_widget.setText("Сохранён")
        self._message_label.setText(f"{provider_title}: ключ сохранён в системном keyring.")
        LOGGER.info(
            (
                "event=llm_key_saved correlation_id=%s course_id=- module_id=- "
                "llm_call_id=- provider=%s"
            ),
            correlation_id,
            provider.value,
        )

    def _delete_provider_key(
        self,
        *,
        provider: LLMServiceProvider,
        provider_title: str,
        input_widget: QLineEdit,
        status_widget: QLabel,
    ) -> None:
        correlation_id = str(uuid4())
        try:
            self._key_store.delete_key(provider)
        except Exception as exc:
            LOGGER.exception(
                (
                    "event=llm_key_delete_failed correlation_id=%s course_id=- module_id=- "
                    "llm_call_id=- provider=%s error_type=%s"
                ),
                correlation_id,
                provider.value,
                exc.__class__.__name__,
            )
            QMessageBox.warning(
                self,
                "Ошибка keyring",
                f"Не удалось удалить ключ {provider_title}. Проверьте настройки keyring.",
            )
            return

        input_widget.clear()
        status_widget.setText("Не задан")
        self._message_label.setText(f"{provider_title}: ключ удалён из системного keyring.")
        LOGGER.info(
            (
                "event=llm_key_deleted correlation_id=%s course_id=- module_id=- "
                "llm_call_id=- provider=%s"
            ),
            correlation_id,
            provider.value,
        )
