"""Factory helpers for default LLM router wiring."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from praktikum_app.application.llm import LLMKeyStore, LLMServiceProvider
from praktikum_app.infrastructure.db.llm_audit_uow import SqlAlchemyLlmCallAuditUnitOfWork
from praktikum_app.infrastructure.db.session import create_default_session_factory
from praktikum_app.infrastructure.llm.clients import AnthropicClient, OpenRouterClient
from praktikum_app.infrastructure.llm.config import LLMRouterConfig, default_router_config
from praktikum_app.infrastructure.llm.router import LLMRouter
from praktikum_app.infrastructure.security.keyring_store import KeyringApiKeyStore


def create_default_llm_router(
    *,
    key_store: LLMKeyStore | None = None,
    session_factory: sessionmaker[Session] | None = None,
    config: LLMRouterConfig | None = None,
) -> LLMRouter:
    """Construct router with default clients, config, key store, and audit UoW."""
    resolved_session_factory = session_factory or create_default_session_factory()
    providers = {
        LLMServiceProvider.ANTHROPIC: AnthropicClient(),
        LLMServiceProvider.OPENROUTER: OpenRouterClient(),
    }
    return LLMRouter(
        providers=providers,
        key_store=key_store or KeyringApiKeyStore(),
        audit_uow_factory=lambda: SqlAlchemyLlmCallAuditUnitOfWork(resolved_session_factory),
        config=config or default_router_config(),
    )
