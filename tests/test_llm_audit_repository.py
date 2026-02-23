"""Repository tests for llm_calls SQLAlchemy persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from praktikum_app.application.llm import LLMServiceProvider
from praktikum_app.application.llm_audit import LLMCallAuditRecord
from praktikum_app.infrastructure.db.base import Base
from praktikum_app.infrastructure.db.llm_audit_uow import SqlAlchemyLlmCallAuditUnitOfWork
from praktikum_app.infrastructure.db.models import LlmCallModel
from praktikum_app.infrastructure.db.session import create_session_factory, create_sqlite_engine


def test_llm_audit_record_is_persisted_to_sqlite() -> None:
    db_path = Path("tests") / f"_runtime_llm_audit_{uuid4().hex}.db"
    session_factory, engine = _create_test_session_factory(db_path)
    try:
        record = LLMCallAuditRecord(
            llm_call_id="call-123",
            provider=LLMServiceProvider.ANTHROPIC,
            model="claude-3-5-sonnet-latest",
            prompt_hash="abc123",
            status="success",
            latency_ms=321,
            input_tokens=111,
            output_tokens=55,
            course_id="course-1",
            module_id=None,
            created_at=datetime(2026, 2, 22, 18, 0, tzinfo=UTC),
        )

        with SqlAlchemyLlmCallAuditUnitOfWork(session_factory) as uow:
            uow.llm_calls.save_call(record)
            uow.commit()

        with session_factory() as session:
            row = session.execute(
                select(LlmCallModel).where(LlmCallModel.llm_call_id == "call-123")
            ).scalar_one()

        assert row.provider == "anthropic"
        assert row.model == "claude-3-5-sonnet-latest"
        assert row.prompt_hash == "abc123"
        assert row.status == "success"
        assert row.latency_ms == 321
        assert row.input_tokens == 111
        assert row.output_tokens == 55
        assert row.course_id == "course-1"
        assert row.module_id is None
    finally:
        engine.dispose()
        db_path.unlink(missing_ok=True)


def _create_test_session_factory(database_path: Path) -> tuple[sessionmaker[Session], Engine]:
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    return create_session_factory(engine), engine
