"""SQLAlchemy repository for LLM calls audit persistence."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from praktikum_app.application.llm_audit import LLMCallAuditRecord, LLMCallAuditRepository
from praktikum_app.infrastructure.db.models import LlmCallModel


class SqlAlchemyLlmCallAuditRepository(LLMCallAuditRepository):
    """Persist LLM call audit records into llm_calls table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save_call(self, record: LLMCallAuditRecord) -> None:
        model = LlmCallModel(
            id=str(uuid4()),
            llm_call_id=record.llm_call_id,
            course_id=record.course_id,
            module_id=record.module_id,
            provider=record.provider.value,
            model=record.model,
            prompt_hash=record.prompt_hash,
            status=record.status,
            latency_ms=record.latency_ms,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            created_at=record.created_at,
        )
        self._session.add(model)
